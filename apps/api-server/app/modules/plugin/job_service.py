from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso

from . import repository
from .models import PluginJob, PluginJobAttempt, PluginJobNotification, PluginJobResponse
from .schemas import (
    PluginJobAttemptRead,
    PluginJobCreate,
    PluginJobNotificationChannel,
    PluginJobNotificationRead,
    PluginJobNotificationType,
    PluginJobRead,
    PluginJobResponseAction,
    PluginJobResponseCreate,
    PluginJobResponseRead,
    PluginJobStatus,
)

TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}
RUNNABLE_JOB_STATUSES = {"queued", "retry_waiting"}
WAITING_RESPONSE_ACTIONS = {"retry", "confirm", "cancel", "provide_input"}
FAILED_RESPONSE_ACTIONS = {"retry", "cancel"}
ALLOWED_JOB_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"retry_waiting", "waiting_response", "succeeded", "failed", "cancelled"},
    "retry_waiting": {"queued", "cancelled"},
    "waiting_response": {"queued", "cancelled"},
    "succeeded": set(),
    "failed": {"queued", "cancelled"},
    "cancelled": set(),
}


class PluginJobError(RuntimeError):
    pass


class PluginJobNotFoundError(PluginJobError):
    pass


class PluginJobStateError(PluginJobError):
    pass


def create_plugin_job(db: Session, *, payload: PluginJobCreate) -> PluginJobRead:
    if payload.idempotency_key is not None:
        existing = repository.get_plugin_job_by_idempotency_key(
            db,
            household_id=payload.household_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            return _to_plugin_job_read(existing)

    now = utc_now_iso()
    row = PluginJob(
        id=new_uuid(),
        household_id=payload.household_id,
        plugin_id=payload.plugin_id,
        plugin_type=payload.plugin_type,
        trigger=payload.trigger,
        status=payload.initial_status,
        request_payload_json=dump_json(payload.request_payload) or "{}",
        payload_summary_json=dump_json(payload.payload_summary),
        idempotency_key=payload.idempotency_key,
        current_attempt=0,
        max_attempts=payload.max_attempts,
        retry_after_at=payload.retry_after_at,
        response_deadline_at=payload.response_deadline_at,
        started_at=None,
        finished_at=None,
        updated_at=now,
        created_at=now,
    )
    repository.add_plugin_job(db, row)
    db.flush()
    return _to_plugin_job_read(row)


def get_plugin_job_or_raise(db: Session, *, job_id: str) -> PluginJob:
    row = repository.get_plugin_job(db, job_id)
    if row is None:
        raise PluginJobNotFoundError(f"插件任务不存在: {job_id}")
    return row


def list_allowed_plugin_job_actions(db: Session, *, job_id: str) -> list[PluginJobResponseAction]:
    row = get_plugin_job_or_raise(db, job_id=job_id)
    return _allowed_actions_for_job(row)


def start_plugin_job_attempt(db: Session, *, job_id: str, worker_id: str | None = None) -> PluginJobAttemptRead:
    job = get_plugin_job_or_raise(db, job_id=job_id)
    if job.status not in RUNNABLE_JOB_STATUSES:
        raise PluginJobStateError(f"任务当前状态不能开始执行: {job.status}")

    latest_attempt = repository.get_latest_plugin_job_attempt(db, job_id=job.id)
    if latest_attempt is not None and latest_attempt.status == "running" and latest_attempt.finished_at is None:
        raise PluginJobStateError("任务已经有正在执行的尝试，不能重复开始")

    now = utc_now_iso()
    next_attempt_no = job.current_attempt + 1
    _transition_job(job, "running", now=now)
    job.current_attempt = next_attempt_no
    if job.started_at is None:
        job.started_at = now
    job.finished_at = None
    job.retry_after_at = None

    attempt = PluginJobAttempt(
        id=new_uuid(),
        job_id=job.id,
        attempt_no=next_attempt_no,
        status="running",
        worker_id=worker_id,
        started_at=now,
        finished_at=None,
        error_code=None,
        error_message=None,
        output_summary_json=None,
    )
    repository.add_plugin_job_attempt(db, attempt)
    db.flush()
    return _to_plugin_job_attempt_read(attempt)


def mark_plugin_job_attempt_succeeded(
    db: Session,
    *,
    attempt_id: str,
    output_summary: dict[str, Any] | None = None,
) -> PluginJobRead:
    attempt = _get_running_attempt_or_raise(db, attempt_id=attempt_id)
    job = get_plugin_job_or_raise(db, job_id=attempt.job_id)
    now = utc_now_iso()

    attempt.status = "succeeded"
    attempt.finished_at = now
    attempt.error_code = None
    attempt.error_message = None
    attempt.output_summary_json = dump_json(output_summary)

    _transition_job(job, "succeeded", now=now)
    job.last_error_code = None
    job.last_error_message = None
    job.response_deadline_at = None
    job.finished_at = now
    db.flush()
    return _to_plugin_job_read(job)


def mark_plugin_job_attempt_failed(
    db: Session,
    *,
    attempt_id: str,
    error_code: str,
    error_message: str,
    retryable: bool = False,
    retry_after_at: str | None = None,
    response_required: bool = False,
    response_deadline_at: str | None = None,
    output_summary: dict[str, Any] | None = None,
) -> PluginJobRead:
    attempt = _get_running_attempt_or_raise(db, attempt_id=attempt_id)
    job = get_plugin_job_or_raise(db, job_id=attempt.job_id)
    now = utc_now_iso()

    attempt.status = "failed"
    attempt.finished_at = now
    attempt.error_code = error_code
    attempt.error_message = error_message
    attempt.output_summary_json = dump_json(output_summary)

    job.last_error_code = error_code
    job.last_error_message = error_message

    if response_required:
        _transition_job(job, "waiting_response", now=now)
        job.retry_after_at = None
        job.response_deadline_at = response_deadline_at
        job.finished_at = None
    elif retryable and job.current_attempt < job.max_attempts:
        _transition_job(job, "retry_waiting", now=now)
        job.retry_after_at = retry_after_at or now
        job.response_deadline_at = None
        job.finished_at = None
    else:
        _transition_job(job, "failed", now=now)
        job.retry_after_at = None
        job.response_deadline_at = None
        job.finished_at = now

    db.flush()
    return _to_plugin_job_read(job)


def mark_plugin_job_attempt_timed_out(
    db: Session,
    *,
    attempt_id: str,
    error_message: str,
    retryable: bool = False,
    retry_after_at: str | None = None,
    response_required: bool = False,
    response_deadline_at: str | None = None,
) -> PluginJobRead:
    attempt = _get_running_attempt_or_raise(db, attempt_id=attempt_id)
    now = utc_now_iso()
    attempt.status = "timed_out"
    attempt.error_code = "job_timeout"
    attempt.error_message = error_message
    attempt.finished_at = now
    db.flush()

    job = get_plugin_job_or_raise(db, job_id=attempt.job_id)
    job.last_error_code = "job_timeout"
    job.last_error_message = error_message

    if response_required:
        _transition_job(job, "waiting_response", now=now)
        job.retry_after_at = None
        job.response_deadline_at = response_deadline_at
        job.finished_at = None
    elif retryable and job.current_attempt < job.max_attempts:
        _transition_job(job, "retry_waiting", now=now)
        job.retry_after_at = retry_after_at or now
        job.response_deadline_at = None
        job.finished_at = None
    else:
        _transition_job(job, "failed", now=now)
        job.retry_after_at = None
        job.response_deadline_at = None
        job.finished_at = now
    db.flush()
    return _to_plugin_job_read(job)


def requeue_plugin_job(db: Session, *, job_id: str) -> PluginJobRead:
    job = get_plugin_job_or_raise(db, job_id=job_id)
    _transition_job(job, "queued")
    job.finished_at = None
    job.retry_after_at = None
    job.response_deadline_at = None
    db.flush()
    return _to_plugin_job_read(job)


def cancel_plugin_job(db: Session, *, job_id: str) -> PluginJobRead:
    job = get_plugin_job_or_raise(db, job_id=job_id)
    now = utc_now_iso()
    _transition_job(job, "cancelled", now=now)
    job.finished_at = now
    job.retry_after_at = None
    job.response_deadline_at = None
    db.flush()
    return _to_plugin_job_read(job)


def record_plugin_job_response(
    db: Session,
    *,
    job_id: str,
    payload: PluginJobResponseCreate,
) -> tuple[PluginJobResponseRead, PluginJobRead]:
    job = get_plugin_job_or_raise(db, job_id=job_id)
    allowed_actions = _allowed_actions_for_job(job)
    if payload.action not in allowed_actions:
        raise PluginJobStateError(f"任务当前不能执行响应动作: {payload.action}")

    now = utc_now_iso()
    response = PluginJobResponse(
        id=new_uuid(),
        job_id=job.id,
        action=payload.action,
        actor_type=payload.actor_type,
        actor_id=payload.actor_id,
        payload_json=dump_json(payload.payload),
        created_at=now,
    )
    repository.add_plugin_job_response(db, response)

    if payload.action == "cancel":
        _transition_job(job, "cancelled", now=now)
        job.finished_at = now
        job.retry_after_at = None
        job.response_deadline_at = None
    else:
        _transition_job(job, "queued", now=now)
        job.finished_at = None
        job.retry_after_at = None
        job.response_deadline_at = None
        if payload.action in {"retry", "confirm", "provide_input"}:
            job.last_error_code = None
            job.last_error_message = None

    db.flush()
    return _to_plugin_job_response_read(response), _to_plugin_job_read(job)


def create_plugin_job_notification(
    db: Session,
    *,
    job_id: str,
    notification_type: PluginJobNotificationType,
    channel: PluginJobNotificationChannel,
    payload: dict[str, Any],
    delivered_at: str | None = None,
) -> PluginJobNotificationRead:
    get_plugin_job_or_raise(db, job_id=job_id)
    row = PluginJobNotification(
        id=new_uuid(),
        job_id=job_id,
        notification_type=notification_type,
        channel=channel,
        payload_json=dump_json(payload) or "{}",
        delivered_at=delivered_at,
        created_at=utc_now_iso(),
    )
    repository.add_plugin_job_notification(db, row)
    db.flush()
    return _to_plugin_job_notification_read(row)


def _get_running_attempt_or_raise(db: Session, *, attempt_id: str) -> PluginJobAttempt:
    attempt = repository.get_plugin_job_attempt(db, attempt_id)
    if attempt is None:
        raise PluginJobNotFoundError(f"插件任务尝试不存在: {attempt_id}")
    if attempt.status != "running" or attempt.finished_at is not None:
        raise PluginJobStateError("只有运行中的尝试才能被收口")
    return attempt


def _allowed_actions_for_job(job: PluginJob) -> list[PluginJobResponseAction]:
    if job.status == "waiting_response":
        actions: list[PluginJobResponseAction] = ["retry", "confirm", "cancel", "provide_input"]
        return actions
    if job.status == "failed" and job.current_attempt < job.max_attempts:
        actions = cast(list[PluginJobResponseAction], ["retry", "cancel"])
        return actions
    return []


def _transition_job(job: PluginJob, next_status: PluginJobStatus, *, now: str | None = None) -> None:
    allowed_next = ALLOWED_JOB_TRANSITIONS[job.status]
    if next_status not in allowed_next:
        raise PluginJobStateError(f"非法任务状态流转: {job.status} -> {next_status}")
    job.status = next_status
    job.updated_at = now or utc_now_iso()


def _to_plugin_job_read(row: PluginJob) -> PluginJobRead:
    return PluginJobRead.model_validate(
        {
            "id": row.id,
            "household_id": row.household_id,
            "plugin_id": row.plugin_id,
            "plugin_type": row.plugin_type,
            "trigger": row.trigger,
            "status": row.status,
            "request_payload": load_json(row.request_payload_json),
            "payload_summary": load_json(row.payload_summary_json),
            "idempotency_key": row.idempotency_key,
            "current_attempt": row.current_attempt,
            "max_attempts": row.max_attempts,
            "last_error_code": row.last_error_code,
            "last_error_message": row.last_error_message,
            "retry_after_at": row.retry_after_at,
            "response_deadline_at": row.response_deadline_at,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "updated_at": row.updated_at,
            "created_at": row.created_at,
        }
    )


def _to_plugin_job_attempt_read(row: PluginJobAttempt) -> PluginJobAttemptRead:
    return PluginJobAttemptRead.model_validate(
        {
            "id": row.id,
            "job_id": row.job_id,
            "attempt_no": row.attempt_no,
            "status": row.status,
            "worker_id": row.worker_id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "output_summary": load_json(row.output_summary_json),
        }
    )


def _to_plugin_job_notification_read(row: PluginJobNotification) -> PluginJobNotificationRead:
    return PluginJobNotificationRead.model_validate(
        {
            "id": row.id,
            "job_id": row.job_id,
            "notification_type": row.notification_type,
            "channel": row.channel,
            "payload": load_json(row.payload_json),
            "delivered_at": row.delivered_at,
            "created_at": row.created_at,
        }
    )


def _to_plugin_job_response_read(row: PluginJobResponse) -> PluginJobResponseRead:
    return PluginJobResponseRead.model_validate(
        {
            "id": row.id,
            "job_id": row.job_id,
            "action": row.action,
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "payload": load_json(row.payload_json),
            "created_at": row.created_at,
        }
    )
