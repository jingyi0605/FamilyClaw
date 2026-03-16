from __future__ import annotations

import asyncio
import logging

import app.db.session as db_session_module
from app.core.config import settings
from app.modules.channel import repository
from app.modules.channel.polling_service import mark_channel_account_poll_failed, poll_channel_account

logger = logging.getLogger(__name__)


class ChannelPollingWorker:
    def __init__(self) -> None:
        self.worker_id = f"channel-polling-worker-{id(self)}"
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self.run_forever(), name=self.worker_id)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = await run_channel_polling_worker_cycle()
            except Exception:
                logger.exception("通道轮询 worker 周期执行失败")
                processed = False

            if processed:
                continue

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(settings.channel_polling_worker_poll_interval_seconds, 0.1),
                )
            except TimeoutError:
                continue


async def run_channel_polling_worker_cycle() -> bool:
    account_refs = _load_polling_accounts()
    if not account_refs:
        return False

    processed = False
    for household_id, account_id in account_refs:
        with db_session_module.SessionLocal() as db:
            try:
                result = poll_channel_account(
                    db,
                    household_id=household_id,
                    account_id=account_id,
                )
                db.commit()
                if result.recorded_event_count > 0 or result.duplicate_event_count > 0:
                    processed = True
            except Exception as exc:
                db.rollback()
                logger.exception("通道轮询失败 household_id=%s account_id=%s", household_id, account_id)
                _persist_poll_failure(
                    household_id=household_id,
                    account_id=account_id,
                    error_message=str(exc) or "channel polling failed",
                )
    return processed


def _load_polling_accounts() -> list[tuple[str, str]]:
    with db_session_module.SessionLocal() as db:
        accounts = repository.list_polling_channel_plugin_accounts(
            db,
            limit=max(settings.channel_polling_worker_batch_size, 1),
        )
        return [(item.household_id, item.id) for item in accounts]


def _persist_poll_failure(*, household_id: str, account_id: str, error_message: str) -> None:
    with db_session_module.SessionLocal() as db:
        try:
            mark_channel_account_poll_failed(
                db,
                household_id=household_id,
                account_id=account_id,
                error_code="channel_poll_failed",
                error_message=error_message,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("通道轮询失败状态写回失败 household_id=%s account_id=%s", household_id, account_id)
