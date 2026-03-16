from __future__ import annotations

import logging
import threading

import app.db.session as db_session_module
from app.core.blocking import BlockingCallKind, BlockingCallPolicy, run_blocking_db
from app.core.config import settings
from app.core.worker_runtime import WorkerRuntime, WorkerRuntimeConfig
from app.modules.channel import repository
from app.modules.channel.schemas import ChannelPollingBatchRead
from app.modules.channel.polling_service import mark_channel_account_poll_failed, poll_channel_account

logger = logging.getLogger(__name__)


class ChannelPollingWorker:
    def __init__(self) -> None:
        self._runtime = WorkerRuntime(
            config=WorkerRuntimeConfig(
                worker_name="channel-polling-worker",
                interval_seconds=max(settings.channel_polling_worker_poll_interval_seconds, 0.1),
                tick_timeout_seconds=max(settings.channel_polling_worker_poll_interval_seconds * 4, 30.0),
                max_consecutive_failures=3,
                degrade_interval_seconds=max(settings.channel_polling_worker_poll_interval_seconds * 2, 0.2),
            ),
            logger=logger,
        )
        self.worker_id = self._runtime.worker_id

    async def start(self) -> None:
        await self._runtime.start(run_channel_polling_worker_cycle)

    async def stop(self) -> None:
        await self._runtime.stop()

    async def run_forever(self) -> None:
        await self._runtime.run_forever(run_channel_polling_worker_cycle)

    def get_health_snapshot(self):
        return self._runtime.get_health_snapshot()


async def run_channel_polling_worker_cycle() -> bool:
    account_refs = await run_blocking_db(
        _load_polling_accounts_sync,
        session_factory=db_session_module.SessionLocal,
        policy=_build_polling_policy(label="channel.polling.load_accounts", kind="sync_db"),
        logger=logger,
    )
    if not account_refs:
        return False

    processed = False
    for household_id, account_id in account_refs:
        try:
            result = await run_blocking_db(
                lambda db: _poll_channel_account_sync(
                    db,
                    household_id=household_id,
                    account_id=account_id,
                ),
                session_factory=db_session_module.SessionLocal,
                policy=_build_polling_policy(
                    label=f"channel.polling.poll_account.{account_id}",
                    kind="plugin_code",
                ),
                commit=True,
                logger=logger,
                context={
                    "household_id": household_id,
                    "account_id": account_id,
                    "thread_id": threading.get_ident(),
                },
            )
            if result.recorded_event_count > 0 or result.duplicate_event_count > 0:
                processed = True
        except Exception as exc:
            logger.exception("通道轮询失败 household_id=%s account_id=%s", household_id, account_id)
            try:
                await run_blocking_db(
                    lambda db: _persist_poll_failure_sync(
                        db,
                        household_id=household_id,
                        account_id=account_id,
                        error_message=str(exc) or "channel polling failed",
                    ),
                    session_factory=db_session_module.SessionLocal,
                    policy=_build_polling_policy(
                        label=f"channel.polling.persist_failure.{account_id}",
                        kind="sync_db",
                    ),
                    commit=True,
                    logger=logger,
                    context={
                        "household_id": household_id,
                        "account_id": account_id,
                    },
                )
            except Exception:
                logger.exception("通道轮询失败状态写回失败 household_id=%s account_id=%s", household_id, account_id)
    return processed


def _load_polling_accounts_sync(db) -> list[tuple[str, str]]:
    accounts = repository.list_polling_channel_plugin_accounts(
        db,
        limit=max(settings.channel_polling_worker_batch_size, 1),
    )
    return [(item.household_id, item.id) for item in accounts]


def _poll_channel_account_sync(
    db,
    *,
    household_id: str,
    account_id: str,
) -> ChannelPollingBatchRead:
    return poll_channel_account(
        db,
        household_id=household_id,
        account_id=account_id,
    )


def _persist_poll_failure_sync(
    db,
    *,
    household_id: str,
    account_id: str,
    error_message: str,
) -> None:
    mark_channel_account_poll_failed(
        db,
        household_id=household_id,
        account_id=account_id,
        error_code="channel_poll_failed",
        error_message=error_message,
    )


def _build_polling_policy(*, label: str, kind: BlockingCallKind) -> BlockingCallPolicy:
    return BlockingCallPolicy(
        label=label,
        kind=kind,
        timeout_seconds=max(settings.channel_polling_worker_poll_interval_seconds * 4, 30.0),
    )
