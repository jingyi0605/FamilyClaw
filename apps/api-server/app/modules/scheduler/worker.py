from __future__ import annotations

import logging

import app.db.session as db_session_module
from app.core.blocking import BlockingCallPolicy, run_blocking_db
from app.core.config import settings
from app.core.worker_runtime import WorkerRuntime, WorkerRuntimeConfig
from app.modules.scheduler.service import process_due_heartbeat_tick, process_due_schedule_tick

logger = logging.getLogger(__name__)


class ScheduledTaskWorker:
    def __init__(self) -> None:
        self._runtime = WorkerRuntime(
            config=WorkerRuntimeConfig(
                worker_name="scheduled-task-worker",
                interval_seconds=max(settings.scheduler_worker_poll_interval_seconds, 0.1),
                tick_timeout_seconds=max(settings.scheduler_worker_poll_interval_seconds * 4, 30.0),
                max_consecutive_failures=3,
                degrade_interval_seconds=max(settings.scheduler_worker_poll_interval_seconds * 2, 0.2),
            ),
            logger=logger,
        )
        self.worker_id = self._runtime.worker_id

    async def start(self) -> None:
        await self._runtime.start(run_scheduled_task_worker_cycle)

    async def stop(self) -> None:
        await self._runtime.stop()

    async def run_forever(self) -> None:
        await self._runtime.run_forever(run_scheduled_task_worker_cycle)

    def get_health_snapshot(self):
        return self._runtime.get_health_snapshot()


async def run_scheduled_task_worker_cycle() -> bool:
    return await run_blocking_db(
        _run_scheduled_task_worker_cycle_sync,
        session_factory=db_session_module.SessionLocal,
        policy=BlockingCallPolicy(
            label="scheduler.worker.tick",
            kind="sync_db",
            timeout_seconds=max(settings.scheduler_worker_poll_interval_seconds * 4, 30.0),
        ),
        commit=True,
        logger=logger,
    )


def _run_scheduled_task_worker_cycle_sync(db) -> bool:
    schedule_runs = process_due_schedule_tick(db, limit=settings.scheduler_worker_batch_size)
    heartbeat_runs = process_due_heartbeat_tick(db, limit=settings.scheduler_worker_batch_size)
    return bool(schedule_runs or heartbeat_runs)
