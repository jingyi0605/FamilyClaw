from __future__ import annotations

import asyncio
import logging

import app.db.session as db_session_module
from app.core.config import settings
from app.modules.scheduler.service import process_due_heartbeat_tick, process_due_schedule_tick

logger = logging.getLogger(__name__)


class ScheduledTaskWorker:
    def __init__(self) -> None:
        self.worker_id = f"scheduled-task-worker-{id(self)}"
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
                processed = await run_scheduled_task_worker_cycle()
            except Exception:
                logger.exception("计划任务 worker 周期执行失败")
                processed = False

            if processed:
                continue

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(settings.scheduler_worker_poll_interval_seconds, 0.1),
                )
            except TimeoutError:
                continue


async def run_scheduled_task_worker_cycle() -> bool:
    with db_session_module.SessionLocal() as db:
        schedule_runs = process_due_schedule_tick(db, limit=settings.scheduler_worker_batch_size)
        heartbeat_runs = process_due_heartbeat_tick(db, limit=settings.scheduler_worker_batch_size)
        db.commit()
    return bool(schedule_runs or heartbeat_runs)
