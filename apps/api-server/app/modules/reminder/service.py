from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.reminder import repository
from app.modules.reminder.models import ReminderAckEvent, ReminderDeliveryAttempt, ReminderRun, ReminderTask
from app.modules.reminder.schemas import (
    ReminderAckEventCreate,
    ReminderAckEventRead,
    ReminderDeliveryAttemptCreate,
    ReminderDeliveryAttemptRead,
    ReminderRunCreate,
    ReminderRunRead,
    ReminderTaskCreate,
    ReminderTaskRead,
    ReminderTaskUpdate,
)
from app.modules.room.models import Room


def create_task(db: Session, payload: ReminderTaskCreate) -> ReminderTaskRead:
    _ensure_household_exists(db, payload.household_id)
    _validate_member_in_household(db, payload.household_id, payload.owner_member_id, "owner member")
    _validate_member_ids(db, payload.household_id, payload.target_member_ids)
    _validate_room_ids(db, payload.household_id, payload.preferred_room_ids)

    row = ReminderTask(
        id=new_uuid(),
        household_id=payload.household_id,
        owner_member_id=payload.owner_member_id,
        title=payload.title,
        description=payload.description,
        reminder_type=payload.reminder_type,
        target_member_ids_json=dump_json(payload.target_member_ids) or "[]",
        preferred_room_ids_json=dump_json(payload.preferred_room_ids) or "[]",
        schedule_kind=payload.schedule_kind,
        schedule_rule_json=dump_json(payload.schedule_rule) or "{}",
        priority=payload.priority,
        delivery_channels_json=dump_json(payload.delivery_channels) or "[]",
        ack_required=payload.ack_required,
        escalation_policy_json=dump_json(payload.escalation_policy),
        enabled=payload.enabled,
        version=1,
        updated_by=payload.updated_by,
        updated_at=utc_now_iso(),
    )
    repository.add_task(db, row)
    db.flush()
    return _to_task_read(row)


def update_task(db: Session, task_id: str, payload: ReminderTaskUpdate) -> ReminderTaskRead:
    row = repository.get_task(db, task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder task not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _to_task_read(row)

    if "owner_member_id" in data:
        _validate_member_in_household(db, row.household_id, data["owner_member_id"], "owner member")
        row.owner_member_id = data["owner_member_id"]
    if "target_member_ids" in data:
        _validate_member_ids(db, row.household_id, data["target_member_ids"])
        row.target_member_ids_json = dump_json(data["target_member_ids"]) or "[]"
    if "preferred_room_ids" in data:
        _validate_room_ids(db, row.household_id, data["preferred_room_ids"])
        row.preferred_room_ids_json = dump_json(data["preferred_room_ids"]) or "[]"
    if "schedule_rule" in data:
        row.schedule_rule_json = dump_json(data["schedule_rule"]) or "{}"
    if "delivery_channels" in data:
        row.delivery_channels_json = dump_json(data["delivery_channels"]) or "[]"
    if "escalation_policy" in data:
        row.escalation_policy_json = dump_json(data["escalation_policy"])

    simple_fields = [
        "title",
        "description",
        "reminder_type",
        "schedule_kind",
        "priority",
        "ack_required",
        "enabled",
    ]
    for field_name in simple_fields:
        if field_name in data:
            setattr(row, field_name, data[field_name])

    if "updated_by" in data:
        row.updated_by = data["updated_by"]
    row.version += 1
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_task_read(row)


def list_tasks(db: Session, *, household_id: str, enabled: bool | None = None) -> list[ReminderTaskRead]:
    _ensure_household_exists(db, household_id)
    rows = repository.list_tasks(db, household_id=household_id, enabled=enabled)
    return [_to_task_read(row) for row in rows]


def create_run(db: Session, payload: ReminderRunCreate) -> ReminderRunRead:
    row_task = repository.get_task(db, payload.task_id)
    if row_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder task not found")
    if row_task.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run household mismatch")
    if repository.get_run_by_slot(db, task_id=payload.task_id, schedule_slot_key=payload.schedule_slot_key) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="reminder run slot already exists")

    row = ReminderRun(
        id=new_uuid(),
        task_id=payload.task_id,
        household_id=payload.household_id,
        schedule_slot_key=payload.schedule_slot_key,
        trigger_reason=payload.trigger_reason,
        planned_at=payload.planned_at,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        status=payload.status,
        context_snapshot_json=dump_json(payload.context_snapshot),
        result_summary_json=dump_json(payload.result_summary),
    )
    repository.add_run(db, row)
    db.flush()
    return _to_run_read(row)


def list_runs(db: Session, *, household_id: str, task_id: str | None = None, limit: int = 50) -> list[ReminderRunRead]:
    _ensure_household_exists(db, household_id)
    rows = repository.list_runs(db, household_id=household_id, task_id=task_id, limit=limit)
    return [_to_run_read(row) for row in rows]


def create_delivery_attempt(db: Session, payload: ReminderDeliveryAttemptCreate) -> ReminderDeliveryAttemptRead:
    run = repository.get_run(db, payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    _validate_member_in_household(db, run.household_id, payload.target_member_id, "target member")
    _validate_room_in_household(db, run.household_id, payload.target_room_id)

    row = ReminderDeliveryAttempt(
        id=new_uuid(),
        run_id=payload.run_id,
        target_member_id=payload.target_member_id,
        target_room_id=payload.target_room_id,
        channel=payload.channel,
        attempt_index=payload.attempt_index,
        planned_at=payload.planned_at,
        sent_at=payload.sent_at,
        status=payload.status,
        provider_result_json=dump_json(payload.provider_result),
        failure_reason=payload.failure_reason,
    )
    repository.add_delivery_attempt(db, row)
    db.flush()
    return _to_delivery_attempt_read(row)


def list_delivery_attempts(db: Session, *, run_id: str) -> list[ReminderDeliveryAttemptRead]:
    run = repository.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    return [_to_delivery_attempt_read(row) for row in repository.list_delivery_attempts(db, run_id=run_id)]


def create_ack_event(db: Session, payload: ReminderAckEventCreate) -> ReminderAckEventRead:
    run = repository.get_run(db, payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    _validate_member_in_household(db, run.household_id, payload.member_id, "ack member")

    row = ReminderAckEvent(
        id=new_uuid(),
        run_id=payload.run_id,
        member_id=payload.member_id,
        action=payload.action,
        note=payload.note,
        created_at=utc_now_iso(),
    )
    repository.add_ack_event(db, row)
    db.flush()
    return _to_ack_event_read(row)


def list_ack_events(db: Session, *, run_id: str) -> list[ReminderAckEventRead]:
    run = repository.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    return [_to_ack_event_read(row) for row in repository.list_ack_events(db, run_id=run_id)]


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")


def _validate_member_in_household(
    db: Session,
    household_id: str,
    member_id: str | None,
    field_label: str,
) -> None:
    if member_id is None:
        return

    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_label} not found")
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_label} must belong to the same household",
        )


def _validate_member_ids(db: Session, household_id: str, member_ids: list[str]) -> None:
    for member_id in member_ids:
        _validate_member_in_household(db, household_id, member_id, "target member")


def _validate_room_ids(db: Session, household_id: str, room_ids: list[str]) -> None:
    for room_id in room_ids:
        _validate_room_in_household(db, household_id, room_id)


def _validate_room_in_household(db: Session, household_id: str, room_id: str | None) -> None:
    if room_id is None:
        return

    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="room not found")
    if room.household_id != household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="room must belong to the same household")


def _to_task_read(row: ReminderTask) -> ReminderTaskRead:
    return ReminderTaskRead(
        id=row.id,
        household_id=row.household_id,
        owner_member_id=row.owner_member_id,
        title=row.title,
        description=row.description,
        reminder_type=row.reminder_type,
        target_member_ids=load_json(row.target_member_ids_json) or [],
        preferred_room_ids=load_json(row.preferred_room_ids_json) or [],
        schedule_kind=row.schedule_kind,
        schedule_rule=load_json(row.schedule_rule_json) or {},
        priority=row.priority,
        delivery_channels=load_json(row.delivery_channels_json) or [],
        ack_required=row.ack_required,
        escalation_policy=load_json(row.escalation_policy_json) or {},
        enabled=row.enabled,
        version=row.version,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _to_run_read(row: ReminderRun) -> ReminderRunRead:
    return ReminderRunRead(
        id=row.id,
        task_id=row.task_id,
        household_id=row.household_id,
        schedule_slot_key=row.schedule_slot_key,
        trigger_reason=row.trigger_reason,
        planned_at=row.planned_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=row.status,
        context_snapshot=load_json(row.context_snapshot_json) or {},
        result_summary=load_json(row.result_summary_json) or {},
    )


def _to_delivery_attempt_read(row: ReminderDeliveryAttempt) -> ReminderDeliveryAttemptRead:
    return ReminderDeliveryAttemptRead(
        id=row.id,
        run_id=row.run_id,
        target_member_id=row.target_member_id,
        target_room_id=row.target_room_id,
        channel=row.channel,
        attempt_index=row.attempt_index,
        planned_at=row.planned_at,
        sent_at=row.sent_at,
        status=row.status,
        provider_result=load_json(row.provider_result_json) or {},
        failure_reason=row.failure_reason,
    )


def _to_ack_event_read(row: ReminderAckEvent) -> ReminderAckEventRead:
    return ReminderAckEventRead(
        id=row.id,
        run_id=row.run_id,
        member_id=row.member_id,
        action=row.action,
        note=row.note,
        created_at=row.created_at,
    )
