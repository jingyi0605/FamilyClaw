from typing import Any, cast

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from app.modules.plugin.models import (
    PluginJob,
    PluginJobAttempt,
    PluginJobNotification,
    PluginJobResponse,
    PluginMount,
    PluginRawRecord,
    PluginRun,
    PluginStateOverride,
)


def add_plugin_run(db: Session, row: PluginRun) -> PluginRun:
    db.add(row)
    return row


def get_plugin_run(db: Session, run_id: str) -> PluginRun | None:
    return db.get(PluginRun, run_id)


def list_plugin_runs(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
) -> list[PluginRun]:
    filters = [PluginRun.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginRun.plugin_id == plugin_id)

    stmt: Select[tuple[PluginRun]] = (
        select(PluginRun)
        .where(*filters)
        .order_by(PluginRun.started_at.desc(), PluginRun.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_plugin_raw_record(db: Session, row: PluginRawRecord) -> PluginRawRecord:
    db.add(row)
    return row


def list_plugin_raw_records(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    run_id: str | None = None,
) -> list[PluginRawRecord]:
    filters = [PluginRawRecord.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginRawRecord.plugin_id == plugin_id)
    if run_id is not None:
        filters.append(PluginRawRecord.run_id == run_id)

    stmt: Select[tuple[PluginRawRecord]] = (
        select(PluginRawRecord)
        .where(*filters)
        .order_by(PluginRawRecord.captured_at.desc(), PluginRawRecord.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_plugin_mount(db: Session, row: PluginMount) -> PluginMount:
    db.add(row)
    return row


def add_plugin_state_override(db: Session, row: PluginStateOverride) -> PluginStateOverride:
    db.add(row)
    return row


def add_plugin_job(db: Session, row: PluginJob) -> PluginJob:
    db.add(row)
    return row


def get_plugin_job(db: Session, job_id: str) -> PluginJob | None:
    return db.get(PluginJob, job_id)


def get_plugin_job_by_idempotency_key(
    db: Session,
    *,
    household_id: str,
    idempotency_key: str,
) -> PluginJob | None:
    stmt: Select[tuple[PluginJob]] = select(PluginJob).where(
        PluginJob.household_id == household_id,
        PluginJob.idempotency_key == idempotency_key,
    )
    return db.scalar(stmt)


def list_plugin_jobs(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    status: str | None = None,
) -> list[PluginJob]:
    filters = [PluginJob.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginJob.plugin_id == plugin_id)
    if status is not None:
        filters.append(PluginJob.status == status)

    stmt: Select[tuple[PluginJob]] = (
        select(PluginJob)
        .where(*filters)
        .order_by(PluginJob.created_at.desc(), PluginJob.id.desc())
    )
    return list(db.scalars(stmt).all())


def count_plugin_jobs(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> int:
    filters = [PluginJob.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginJob.plugin_id == plugin_id)
    if status is not None:
        filters.append(PluginJob.status == status)
    if created_from is not None:
        filters.append(PluginJob.created_at >= created_from)
    if created_to is not None:
        filters.append(PluginJob.created_at <= created_to)
    stmt = select(PluginJob.id).where(*filters)
    return len(list(db.execute(stmt).all()))


def list_plugin_jobs_page(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    status: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[PluginJob]:
    filters = [PluginJob.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginJob.plugin_id == plugin_id)
    if status is not None:
        filters.append(PluginJob.status == status)
    if created_from is not None:
        filters.append(PluginJob.created_at >= created_from)
    if created_to is not None:
        filters.append(PluginJob.created_at <= created_to)

    stmt: Select[tuple[PluginJob]] = (
        select(PluginJob)
        .where(*filters)
        .order_by(PluginJob.created_at.desc(), PluginJob.id.desc())
        .offset(max(offset, 0))
        .limit(max(limit, 1))
    )
    return list(db.scalars(stmt).all())


def list_runnable_plugin_jobs(db: Session, *, now: str) -> list[PluginJob]:
    stmt: Select[tuple[PluginJob]] = (
        select(PluginJob)
        .where(
            PluginJob.status == "queued",
        )
        .order_by(PluginJob.created_at.asc(), PluginJob.id.asc())
    )
    queued = list(db.scalars(stmt).all())

    retry_stmt: Select[tuple[PluginJob]] = (
        select(PluginJob)
        .where(
            PluginJob.status == "retry_waiting",
            PluginJob.retry_after_at.is_not(None),
            PluginJob.retry_after_at <= now,
        )
        .order_by(PluginJob.retry_after_at.asc(), PluginJob.created_at.asc(), PluginJob.id.asc())
    )
    return [*queued, *list(db.scalars(retry_stmt).all())]


def claim_plugin_job_for_running(
    db: Session,
    *,
    job_id: str,
    expected_status: str,
    updated_at: str,
) -> bool:
    stmt = (
        update(PluginJob)
        .where(PluginJob.id == job_id, PluginJob.status == expected_status)
        .values(status="running", updated_at=updated_at, retry_after_at=None, finished_at=None)
    )
    result = db.execute(stmt)
    return (cast(Any, result).rowcount or 0) == 1


def list_stale_running_plugin_jobs(db: Session, *, heartbeat_before: str) -> list[PluginJob]:
    stmt: Select[tuple[PluginJob]] = (
        select(PluginJob)
        .where(
            PluginJob.status == "running",
            PluginJob.updated_at <= heartbeat_before,
        )
        .order_by(PluginJob.updated_at.asc(), PluginJob.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_plugin_job_attempt(db: Session, row: PluginJobAttempt) -> PluginJobAttempt:
    db.add(row)
    return row


def get_plugin_job_attempt(db: Session, attempt_id: str) -> PluginJobAttempt | None:
    return db.get(PluginJobAttempt, attempt_id)


def get_latest_plugin_job_attempt(db: Session, *, job_id: str) -> PluginJobAttempt | None:
    stmt: Select[tuple[PluginJobAttempt]] = (
        select(PluginJobAttempt)
        .where(PluginJobAttempt.job_id == job_id)
        .order_by(PluginJobAttempt.attempt_no.desc(), PluginJobAttempt.id.desc())
    )
    return db.scalar(stmt)


def list_plugin_job_attempts(db: Session, *, job_id: str) -> list[PluginJobAttempt]:
    stmt: Select[tuple[PluginJobAttempt]] = (
        select(PluginJobAttempt)
        .where(PluginJobAttempt.job_id == job_id)
        .order_by(PluginJobAttempt.attempt_no.asc(), PluginJobAttempt.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_plugin_job_notification(db: Session, row: PluginJobNotification) -> PluginJobNotification:
    db.add(row)
    return row


def list_plugin_job_notifications(db: Session, *, job_id: str) -> list[PluginJobNotification]:
    stmt: Select[tuple[PluginJobNotification]] = (
        select(PluginJobNotification)
        .where(PluginJobNotification.job_id == job_id)
        .order_by(PluginJobNotification.created_at.desc(), PluginJobNotification.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_latest_plugin_job_notifications(db: Session, *, job_id: str, limit: int = 5) -> list[PluginJobNotification]:
    stmt: Select[tuple[PluginJobNotification]] = (
        select(PluginJobNotification)
        .where(PluginJobNotification.job_id == job_id)
        .order_by(PluginJobNotification.created_at.desc(), PluginJobNotification.id.desc())
        .limit(max(limit, 1))
    )
    return list(db.scalars(stmt).all())


def mark_plugin_job_notification_delivered(db: Session, *, notification_id: str, delivered_at: str) -> bool:
    stmt = (
        update(PluginJobNotification)
        .where(PluginJobNotification.id == notification_id)
        .values(delivered_at=delivered_at)
    )
    result = db.execute(stmt)
    return (cast(Any, result).rowcount or 0) == 1


def add_plugin_job_response(db: Session, row: PluginJobResponse) -> PluginJobResponse:
    db.add(row)
    return row


def list_plugin_job_responses(db: Session, *, job_id: str) -> list[PluginJobResponse]:
    stmt: Select[tuple[PluginJobResponse]] = (
        select(PluginJobResponse)
        .where(PluginJobResponse.job_id == job_id)
        .order_by(PluginJobResponse.created_at.desc(), PluginJobResponse.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_plugin_mount(db: Session, *, household_id: str, plugin_id: str) -> PluginMount | None:
    stmt: Select[tuple[PluginMount]] = select(PluginMount).where(
        PluginMount.household_id == household_id,
        PluginMount.plugin_id == plugin_id,
    )
    return db.scalar(stmt)


def get_plugin_state_override(db: Session, *, household_id: str, plugin_id: str) -> PluginStateOverride | None:
    stmt: Select[tuple[PluginStateOverride]] = select(PluginStateOverride).where(
        PluginStateOverride.household_id == household_id,
        PluginStateOverride.plugin_id == plugin_id,
    )
    return db.scalar(stmt)


def list_plugin_mounts(db: Session, *, household_id: str) -> list[PluginMount]:
    stmt: Select[tuple[PluginMount]] = (
        select(PluginMount)
        .where(PluginMount.household_id == household_id)
        .order_by(PluginMount.created_at.desc(), PluginMount.id.desc())
    )
    return list(db.scalars(stmt).all())


def list_plugin_state_overrides(db: Session, *, household_id: str) -> list[PluginStateOverride]:
    stmt: Select[tuple[PluginStateOverride]] = (
        select(PluginStateOverride)
        .where(PluginStateOverride.household_id == household_id)
        .order_by(PluginStateOverride.updated_at.desc(), PluginStateOverride.id.desc())
    )
    return list(db.scalars(stmt).all())


def delete_plugin_mount(db: Session, row: PluginMount) -> None:
    db.delete(row)
