from __future__ import annotations

import logging
import threading

import app.db.session as db_session_module
from app.core.blocking import BlockingCallKind, BlockingCallPolicy, run_blocking, run_blocking_db
from app.core.config import settings
from app.core.worker_runtime import WorkerRuntime, WorkerRuntimeConfig
from app.modules.channel import repository
from app.modules.channel.polling_service import (
    ChannelPollingServiceError,
    PreparedChannelPollExecution,
    apply_channel_poll_execution,
    mark_channel_account_poll_failed,
    prepare_channel_account_poll_execution,
)
from app.modules.channel.schemas import ChannelPollingBatchRead
from app.modules.plugin.service import PluginExecutionError, execute_prepared_household_plugin

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
            prepared = await run_blocking_db(
                lambda db: _prepare_poll_channel_account_sync(
                    db,
                    household_id=household_id,
                    account_id=account_id,
                ),
                session_factory=db_session_module.SessionLocal,
                policy=_build_polling_policy(
                    label=f"channel.polling.prepare_account.{account_id}",
                    kind="sync_db",
                ),
                logger=logger,
                context={
                    "household_id": household_id,
                    "account_id": account_id,
                    "thread_id": threading.get_ident(),
                },
            )
            result = await run_blocking(
                lambda: _execute_poll_channel_account_sync(prepared),
                policy=_build_polling_policy(
                    label=f"channel.polling.execute_account.{account_id}",
                    kind="plugin_code",
                ),
                logger=logger,
                context={
                    "household_id": household_id,
                    "account_id": account_id,
                    "thread_id": threading.get_ident(),
                },
            )
            result = await run_blocking_db(
                lambda db: _apply_poll_channel_account_sync(
                    db,
                    household_id=household_id,
                    account_id=account_id,
                    execution=result,
                ),
                session_factory=db_session_module.SessionLocal,
                policy=_build_polling_policy(
                    label=f"channel.polling.persist_account.{account_id}",
                    kind="sync_db",
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
        except PluginExecutionError as exc:
            logger.info(
                "通道轮询插件返回失败 household_id=%s account_id=%s error=%s",
                household_id,
                account_id,
                exc,
            )
        except ChannelPollingServiceError as exc:
            logger.warning(
                "通道轮询业务失败 household_id=%s account_id=%s error=%s",
                household_id,
                account_id,
                exc,
            )
            if getattr(exc, "already_recorded", False):
                continue
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


def _prepare_poll_channel_account_sync(
    db,
    *,
    household_id: str,
    account_id: str,
) -> PreparedChannelPollExecution:
    return prepare_channel_account_poll_execution(
        db,
        household_id=household_id,
        account_id=account_id,
    )


def _execute_poll_channel_account_sync(prepared: PreparedChannelPollExecution):
    return execute_prepared_household_plugin(prepared.plugin_execution)


def _apply_poll_channel_account_sync(
    db,
    *,
    household_id: str,
    account_id: str,
    execution,
) -> ChannelPollingBatchRead:
    return apply_channel_poll_execution(
        db,
        household_id=household_id,
        account_id=account_id,
        execution=execution,
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
