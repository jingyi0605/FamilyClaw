from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Literal

from app.db.utils import utc_now_iso


WorkerState = Literal["starting", "running", "degraded", "paused", "stopped"]


@dataclass(slots=True, frozen=True)
class WorkerRuntimeConfig:
    worker_name: str
    interval_seconds: float
    tick_timeout_seconds: float
    max_consecutive_failures: int = 3
    degrade_interval_seconds: float | None = None
    supports_pause: bool = True

    def __post_init__(self) -> None:
        if not self.worker_name.strip():
            raise ValueError("worker_name 不能为空")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds 必须大于 0")
        if self.tick_timeout_seconds <= 0:
            raise ValueError("tick_timeout_seconds 必须大于 0")
        if self.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures 必须大于等于 1")
        if self.degrade_interval_seconds is not None and self.degrade_interval_seconds <= 0:
            raise ValueError("degrade_interval_seconds 必须大于 0")


@dataclass(slots=True, frozen=True)
class WorkerHealthSnapshot:
    worker_name: str
    state: WorkerState
    last_started_at: str | None = None
    last_succeeded_at: str | None = None
    last_failed_at: str | None = None
    consecutive_failures: int = 0
    last_duration_ms: float | None = None
    last_error_summary: str | None = None


class WorkerTickTimeoutError(TimeoutError):
    def __init__(self, worker_name: str, timeout_seconds: float):
        super().__init__(f"worker tick 超时: {worker_name} ({timeout_seconds}s)")
        self.worker_name = worker_name
        self.timeout_seconds = timeout_seconds


class WorkerRuntime:
    def __init__(self, *, config: WorkerRuntimeConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.worker_id = f"{config.worker_name}-{id(self)}"
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._health = WorkerHealthSnapshot(worker_name=self.worker_id, state="stopped")

    async def start(self, tick_fn: Callable[[], Awaitable[bool]]) -> None:
        if self._task is not None and self._task.done():
            self._task = None
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self.run_forever(tick_fn), name=self.worker_id)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            self._health = replace(self._health, state="stopped")
            return
        await self._task
        self._task = None
        self._health = replace(self._health, state="stopped")

    async def run_once(self, tick_fn: Callable[[], Awaitable[bool]]) -> bool:
        if self.is_running():
            raise RuntimeError(f"worker 已在运行中: {self.worker_id}")
        self._stop_event.clear()
        return await self._run_tick(tick_fn)

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_forever(self, tick_fn: Callable[[], Awaitable[bool]]) -> None:
        self._health = replace(self._health, state="starting")
        while not self._stop_event.is_set():
            processed = await self._run_tick(tick_fn)
            wait_timeout = self._resolve_wait_timeout(processed=processed)
            if wait_timeout <= 0:
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_timeout)
            except TimeoutError:
                continue

    def get_health_snapshot(self) -> WorkerHealthSnapshot:
        return replace(self._health)

    async def _run_tick(self, tick_fn: Callable[[], Awaitable[bool]]) -> bool:
        started_at = utc_now_iso()
        started_perf = time.perf_counter()
        self._health = replace(self._health, last_started_at=started_at)
        try:
            processed = await asyncio.wait_for(tick_fn(), timeout=self.config.tick_timeout_seconds)
        except asyncio.TimeoutError as exc:
            duration_ms = (time.perf_counter() - started_perf) * 1000
            timeout_error = WorkerTickTimeoutError(self.worker_id, self.config.tick_timeout_seconds)
            self.logger.warning(
                "worker tick 超时 worker=%s timeout_seconds=%s",
                self.worker_id,
                self.config.tick_timeout_seconds,
            )
            self._mark_failure(duration_ms=duration_ms, error_summary=str(timeout_error))
            return False
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_perf) * 1000
            self.logger.exception("worker tick 执行失败 worker=%s", self.worker_id)
            self._mark_failure(duration_ms=duration_ms, error_summary=str(exc) or exc.__class__.__name__)
            return False

        duration_ms = (time.perf_counter() - started_perf) * 1000
        self._mark_success(duration_ms=duration_ms)
        return processed

    def _mark_success(self, *, duration_ms: float) -> None:
        self._health = replace(
            self._health,
            state="running",
            last_succeeded_at=utc_now_iso(),
            consecutive_failures=0,
            last_duration_ms=duration_ms,
            last_error_summary=None,
        )

    def _mark_failure(self, *, duration_ms: float, error_summary: str) -> None:
        consecutive_failures = self._health.consecutive_failures + 1
        state: WorkerState = "running"
        if consecutive_failures >= self.config.max_consecutive_failures:
            state = "degraded"
        self._health = replace(
            self._health,
            state=state,
            last_failed_at=utc_now_iso(),
            consecutive_failures=consecutive_failures,
            last_duration_ms=duration_ms,
            last_error_summary=error_summary,
        )

    def _resolve_wait_timeout(self, *, processed: bool) -> float:
        if self._health.state == "degraded":
            return self.config.degrade_interval_seconds or self.config.interval_seconds
        if processed:
            return 0
        return self.config.interval_seconds
