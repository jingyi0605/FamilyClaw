from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.plugin.models import (
    PluginJob,
    PluginJobAttempt,
    PluginJobNotification,
    PluginJobResponse,
    PluginMount,
    PluginRawRecord,
    PluginRun,
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


def list_plugin_mounts(db: Session, *, household_id: str) -> list[PluginMount]:
    stmt: Select[tuple[PluginMount]] = (
        select(PluginMount)
        .where(PluginMount.household_id == household_id)
        .order_by(PluginMount.created_at.desc(), PluginMount.id.desc())
    )
    return list(db.scalars(stmt).all())


def delete_plugin_mount(db: Session, row: PluginMount) -> None:
    db.delete(row)
