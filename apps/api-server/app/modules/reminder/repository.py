from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.reminder.models import (
    ReminderAckEvent,
    ReminderDeliveryAttempt,
    ReminderRun,
    ReminderTask,
)


def add_task(db: Session, row: ReminderTask) -> ReminderTask:
    db.add(row)
    return row


def get_task(db: Session, task_id: str) -> ReminderTask | None:
    return db.get(ReminderTask, task_id)


def list_tasks(db: Session, *, household_id: str, enabled: bool | None = None) -> Sequence[ReminderTask]:
    stmt: Select[tuple[ReminderTask]] = (
        select(ReminderTask)
        .where(ReminderTask.household_id == household_id)
        .order_by(ReminderTask.updated_at.desc())
    )
    if enabled is not None:
        stmt = stmt.where(ReminderTask.enabled == enabled)
    return list(db.scalars(stmt).all())


def add_run(db: Session, row: ReminderRun) -> ReminderRun:
    db.add(row)
    return row


def get_run(db: Session, run_id: str) -> ReminderRun | None:
    return db.get(ReminderRun, run_id)


def get_run_by_slot(db: Session, *, task_id: str, schedule_slot_key: str) -> ReminderRun | None:
    stmt = select(ReminderRun).where(
        ReminderRun.task_id == task_id,
        ReminderRun.schedule_slot_key == schedule_slot_key,
    )
    return db.scalar(stmt)


def list_runs(db: Session, *, household_id: str, task_id: str | None = None, limit: int = 50) -> Sequence[ReminderRun]:
    stmt: Select[tuple[ReminderRun]] = (
        select(ReminderRun)
        .where(ReminderRun.household_id == household_id)
        .order_by(ReminderRun.planned_at.desc(), ReminderRun.id.desc())
        .limit(limit)
    )
    if task_id is not None:
        stmt = stmt.where(ReminderRun.task_id == task_id)
    return list(db.scalars(stmt).all())


def add_delivery_attempt(db: Session, row: ReminderDeliveryAttempt) -> ReminderDeliveryAttempt:
    db.add(row)
    return row


def list_delivery_attempts(db: Session, *, run_id: str) -> Sequence[ReminderDeliveryAttempt]:
    stmt: Select[tuple[ReminderDeliveryAttempt]] = (
        select(ReminderDeliveryAttempt)
        .where(ReminderDeliveryAttempt.run_id == run_id)
        .order_by(ReminderDeliveryAttempt.attempt_index.asc(), ReminderDeliveryAttempt.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_ack_event(db: Session, row: ReminderAckEvent) -> ReminderAckEvent:
    db.add(row)
    return row


def list_ack_events(db: Session, *, run_id: str) -> Sequence[ReminderAckEvent]:
    stmt: Select[tuple[ReminderAckEvent]] = (
        select(ReminderAckEvent)
        .where(ReminderAckEvent.run_id == run_id)
        .order_by(ReminderAckEvent.created_at.asc(), ReminderAckEvent.id.asc())
    )
    return list(db.scalars(stmt).all())
