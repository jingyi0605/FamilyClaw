from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import load_json, new_uuid, utc_now_iso
import app.db.session as db_session_module

from . import repository
from .job_notifier import publish_plugin_job_updates
from .job_service import (
    PluginJobNotFoundError,
    create_plugin_job,
    get_plugin_job_or_raise,
    mark_plugin_job_attempt_failed,
    mark_plugin_job_attempt_succeeded,
    mark_plugin_job_attempt_timed_out,
    requeue_plugin_job,
)
from .schemas import PluginExecutionRequest, PluginJobCreate, PluginJobRead, PluginType
from .service import run_plugin_sync_pipeline

logger = logging.getLogger(__name__)


class PluginJobWorker:
    def __init__(self) -> None:
        self.worker_id = f"plugin-worker-{id(self)}"
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
                processed = await run_plugin_job_worker_cycle(worker_id=self.worker_id)
            except Exception:
                logger.exception("插件后台任务 worker 周期执行失败")
                processed = False

            if processed:
                continue

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(settings.plugin_job_worker_poll_interval_seconds, 0.1),
                )
            except TimeoutError:
                continue


def enqueue_plugin_execution_job(
    db: Session,
    *,
    household_id: str,
    request: PluginExecutionRequest,
    idempotency_key: str | None = None,
    payload_summary: dict[str, Any] | None = None,
    max_attempts: int | None = None,
) -> PluginJobRead:
    return create_plugin_job(
        db,
        payload=PluginJobCreate(
            household_id=household_id,
            plugin_id=request.plugin_id,
            plugin_type=request.plugin_type,
            trigger=request.trigger,
            request_payload=request.payload,
            payload_summary=payload_summary,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts or _default_max_attempts_for_plugin_type(request.plugin_type),
        ),
    )


async def run_plugin_job_worker_cycle(*, worker_id: str) -> bool:
    with db_session_module.SessionLocal() as db:
        recovered_job_ids = recover_plugin_jobs(db)
        claimed = claim_next_plugin_job(db, worker_id=worker_id)
        db.commit()

    for recovered_job_id, household_id in recovered_job_ids:
        with db_session_module.SessionLocal() as db:
            await publish_plugin_job_updates(db, household_id=household_id, job_id=recovered_job_id)

    if claimed is None:
        return len(recovered_job_ids) > 0

    with db_session_module.SessionLocal() as db:
        await publish_plugin_job_updates(db, household_id=claimed.household_id, job_id=claimed.id)
    await execute_plugin_job(claimed.id, worker_id=worker_id)
    return True


async def execute_plugin_job(job_id: str, *, worker_id: str) -> None:
    await asyncio.to_thread(_execute_plugin_job_sync, job_id, worker_id)
    with db_session_module.SessionLocal() as db:
        job = get_plugin_job_or_raise(db, job_id=job_id)
        await publish_plugin_job_updates(db, household_id=job.household_id, job_id=job_id)


def claim_next_plugin_job(db: Session, *, worker_id: str) -> PluginJobRead | None:
    now = utc_now_iso()
    candidates = repository.list_runnable_plugin_jobs(db, now=now)
    for candidate in candidates:
        expected_status = candidate.status
        claimed = repository.claim_plugin_job_for_running(
            db,
            job_id=candidate.id,
            expected_status=expected_status,
            updated_at=now,
        )
        if not claimed:
            db.rollback()
            continue
        db.flush()
        job = get_plugin_job_or_raise(db, job_id=candidate.id)
        attempt_no = job.current_attempt + 1
        job.current_attempt = attempt_no
        if job.started_at is None:
            job.started_at = now
        repository.add_plugin_job_attempt(
            db,
            row=_build_running_attempt(job_id=job.id, attempt_no=attempt_no, worker_id=worker_id, started_at=now),
        )
        db.flush()
        return _to_job_read(job)
    return None


def recover_plugin_jobs(db: Session) -> list[tuple[str, str]]:
    recovered_job_ids: list[tuple[str, str]] = []
    now = utc_now_iso()

    retry_jobs = repository.list_runnable_plugin_jobs(db, now=now)
    for job in retry_jobs:
        if job.status == "retry_waiting" and job.retry_after_at is not None and job.retry_after_at <= now:
            requeue_plugin_job(db, job_id=job.id)
            recovered_job_ids.append((job.id, job.household_id))

    stale_before = _subtract_seconds(now, settings.plugin_job_running_stale_after_seconds)
    for job in repository.list_stale_running_plugin_jobs(db, heartbeat_before=stale_before):
        attempt = repository.get_latest_plugin_job_attempt(db, job_id=job.id)
        if attempt is None or attempt.finished_at is not None:
            continue
        mark_plugin_job_attempt_failed(
            db,
            attempt_id=attempt.id,
            error_code="job_recovery_failed",
            error_message="服务重启或 worker 中断，任务已按恢复规则收口",
            retryable=job.current_attempt < job.max_attempts,
            retry_after_at=_add_seconds(now, settings.plugin_job_default_retry_delay_seconds),
        )
        recovered_job_ids.append((job.id, job.household_id))

    if recovered_job_ids:
        db.flush()
    return recovered_job_ids


def _execute_plugin_job_sync(job_id: str, worker_id: str) -> None:
    with db_session_module.SessionLocal() as db:
        job = get_plugin_job_or_raise(db, job_id=job_id)
        attempt = repository.get_latest_plugin_job_attempt(db, job_id=job_id)
        if attempt is None or attempt.status != "running" or attempt.finished_at is not None:
            raise PluginJobNotFoundError(f"插件任务缺少运行中的尝试: {job_id}")

        try:
            request = PluginExecutionRequest(
                plugin_id=job.plugin_id,
                plugin_type=cast(PluginType, job.plugin_type),
                payload=_read_request_payload(job),
                trigger=job.trigger,
            )
            result = run_plugin_sync_pipeline(
                db,
                household_id=job.household_id,
                request=request,
            )
            if result.run.status == "success":
                mark_plugin_job_attempt_succeeded(
                    db,
                    attempt_id=attempt.id,
                    output_summary={
                        "pipeline_run_id": result.run.id,
                        "raw_record_count": result.run.raw_record_count,
                        "memory_card_count": result.run.memory_card_count,
                    },
                )
            elif result.run.error_code == "plugin_runner_timeout":
                mark_plugin_job_attempt_timed_out(
                    db,
                    attempt_id=attempt.id,
                    error_message=result.run.error_message or "插件后台任务执行超时",
                    retryable=_is_retryable_error(result.run.error_code, job.plugin_type),
                    retry_after_at=_add_seconds(utc_now_iso(), settings.plugin_job_default_retry_delay_seconds),
                )
            else:
                mark_plugin_job_attempt_failed(
                    db,
                    attempt_id=attempt.id,
                    error_code=result.run.error_code or "job_execution_failed",
                    error_message=result.run.error_message or "插件后台任务执行失败",
                    retryable=_is_retryable_error(result.run.error_code, job.plugin_type),
                    retry_after_at=_add_seconds(utc_now_iso(), settings.plugin_job_default_retry_delay_seconds),
                    output_summary={"pipeline_run_id": result.run.id},
                )
            db.commit()
        except Exception as exc:
            db.rollback()
            recovery_db = db_session_module.SessionLocal()
            try:
                recovery_attempt = repository.get_latest_plugin_job_attempt(recovery_db, job_id=job_id)
                if recovery_attempt is None:
                    raise
                recovery_job = get_plugin_job_or_raise(recovery_db, job_id=job_id)
                mark_plugin_job_attempt_failed(
                    recovery_db,
                    attempt_id=recovery_attempt.id,
                    error_code="job_execution_failed",
                    error_message=str(exc),
                    retryable=_is_retryable_job(plugin_type=recovery_job.plugin_type),
                    retry_after_at=_add_seconds(utc_now_iso(), settings.plugin_job_default_retry_delay_seconds),
                    output_summary={"worker_id": worker_id},
                )
                recovery_db.commit()
            finally:
                recovery_db.close()


def _build_running_attempt(*, job_id: str, attempt_no: int, worker_id: str, started_at: str):
    from .models import PluginJobAttempt

    return PluginJobAttempt(
        id=new_uuid(),
        job_id=job_id,
        attempt_no=attempt_no,
        status="running",
        worker_id=worker_id,
        started_at=started_at,
        finished_at=None,
        error_code=None,
        error_message=None,
        output_summary_json=None,
    )


def _read_request_payload(job) -> dict[str, Any]:
    payload = load_json(job.request_payload_json)
    if not isinstance(payload, dict):
        return {}
    return payload


def _to_job_read(job) -> PluginJobRead:
    return PluginJobRead.model_validate(
        {
            "id": job.id,
            "household_id": job.household_id,
            "plugin_id": job.plugin_id,
            "plugin_type": job.plugin_type,
            "trigger": job.trigger,
            "status": job.status,
            "request_payload": _read_request_payload(job),
            "payload_summary": load_json(job.payload_summary_json),
            "idempotency_key": job.idempotency_key,
            "current_attempt": job.current_attempt,
            "max_attempts": job.max_attempts,
            "last_error_code": job.last_error_code,
            "last_error_message": job.last_error_message,
            "retry_after_at": job.retry_after_at,
            "response_deadline_at": job.response_deadline_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "updated_at": job.updated_at,
            "created_at": job.created_at,
        }
    )


def _default_max_attempts_for_plugin_type(plugin_type: PluginType) -> int:
    if plugin_type == "action":
        return 1
    return max(settings.plugin_job_default_max_attempts, 1)


def _is_retryable_error(error_code: str | None, plugin_type: str) -> bool:
    if plugin_type == "action":
        return False
    return error_code in {None, "job_execution_failed", "plugin_execution_failed", "job_timeout", "plugin_runner_timeout"}


def _is_retryable_job(*, plugin_type: str) -> bool:
    return plugin_type != "action"


def _subtract_seconds(timestamp: str, seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    normalized = timestamp.replace("Z", "+00:00")
    value = datetime.fromisoformat(normalized)
    return (value - timedelta(seconds=max(seconds, 0))).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _add_seconds(timestamp: str, seconds: int) -> str:
    from datetime import datetime, timedelta, timezone

    normalized = timestamp.replace("Z", "+00:00")
    value = datetime.fromisoformat(normalized)
    return (value + timedelta(seconds=max(seconds, 0))).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
