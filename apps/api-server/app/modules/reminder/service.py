from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.delivery.service import build_delivery_plan
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.reminder import repository
from app.modules.reminder.models import ReminderAckEvent, ReminderDeliveryAttempt, ReminderRun, ReminderTask
from app.modules.reminder.schemas import (
    ReminderAckEventCreate,
    ReminderAckEventRead,
    ReminderAckResponse,
    ReminderDeliveryAttemptCreate,
    ReminderDeliveryAttemptRead,
    ReminderOverviewItem,
    ReminderOverviewRead,
    ReminderRunCreate,
    ReminderRunRead,
    ReminderSchedulerDispatchResponse,
    ReminderTaskCreate,
    ReminderTaskRead,
    ReminderTriggerResponse,
    ReminderTaskUpdate,
)
from app.modules.reminder_scheduler.service import build_run_draft, build_schedule_slot
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


def get_task_read_or_404(db: Session, task_id: str) -> ReminderTaskRead:
    row = repository.get_task(db, task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder task not found")
    return _to_task_read(row)


def delete_task(
    db: Session,
    *,
    task_id: str,
    updated_by: str | None,
) -> ReminderTaskRead:
    row = repository.get_task(db, task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder task not found")
    row.enabled = False
    row.version += 1
    row.updated_by = updated_by
    row.updated_at = utc_now_iso()
    db.flush()
    return _to_task_read(row)


def get_run_read_or_404(db: Session, run_id: str) -> ReminderRunRead:
    run = repository.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    return _to_run_read(run)


def build_reminder_overview(db: Session, *, household_id: str) -> ReminderOverviewRead:
    tasks = list_tasks(db, household_id=household_id)
    runs = list_runs(db, household_id=household_id, limit=200)
    latest_run_by_task_id: dict[str, ReminderRunRead] = {}
    for run in runs:
        if run.task_id not in latest_run_by_task_id:
            latest_run_by_task_id[run.task_id] = run

    latest_ack_by_run_id: dict[str, ReminderAckEventRead] = {}
    for run in runs:
        ack_events = list_ack_events(db, run_id=run.id)
        if ack_events:
            latest_ack_by_run_id[run.id] = ack_events[-1]

    items: list[ReminderOverviewItem] = []
    for task in tasks:
        latest_run = latest_run_by_task_id.get(task.id)
        latest_ack = latest_ack_by_run_id.get(latest_run.id) if latest_run is not None else None
        next_trigger_at = _resolve_next_trigger_at(task)
        items.append(
            ReminderOverviewItem(
                task_id=task.id,
                title=task.title,
                reminder_type=task.reminder_type,
                enabled=task.enabled,
                next_trigger_at=next_trigger_at,
                latest_run_status=latest_run.status if latest_run else None,
                latest_run_planned_at=latest_run.planned_at if latest_run else None,
                latest_ack_action=latest_ack.action if latest_ack else None,
            )
        )
    return ReminderOverviewRead(
        household_id=household_id,
        total_tasks=len(tasks),
        enabled_tasks=sum(1 for task in tasks if task.enabled),
        pending_runs=sum(1 for run in runs if run.status in {"pending", "delivering"}),
        ack_required_tasks=sum(1 for task in tasks if task.ack_required),
        items=items,
    )


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


def trigger_task(
    db: Session,
    *,
    task_id: str,
    trigger_reason: str = "manual",
    now_iso: str | None = None,
) -> ReminderTriggerResponse:
    task = get_task_read_or_404(db, task_id)
    slot = build_schedule_slot(
        task,
        planned_at=now_iso or utc_now_iso(),
        trigger_reason=trigger_reason,
    )
    run = create_run(
        db,
        ReminderRunCreate(
            task_id=task.id,
            household_id=task.household_id,
            schedule_slot_key=slot.schedule_slot_key,
            trigger_reason=slot.trigger_reason,
            planned_at=slot.planned_at,
            started_at=utc_now_iso(),
            status="pending",
            context_snapshot={
                "task_title": task.title,
                "trigger_reason": trigger_reason,
            },
            result_summary={},
        ),
    )
    delivery_attempts = _dispatch_delivery_attempts(db, task=task, run=run, escalated=False)
    updated_run = _finalize_run_after_delivery(
        db,
        run_id=run.id,
        ack_required=task.ack_required,
        auto_ack_reason="ack not required",
    )
    return ReminderTriggerResponse(
        run=updated_run,
        delivery_attempts=delivery_attempts,
        escalated=False,
    )


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


def acknowledge_run(
    db: Session,
    *,
    payload: ReminderAckEventCreate,
) -> ReminderAckResponse:
    ack_event = create_ack_event(db, payload)
    run = repository.get_run(payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")

    result_summary = load_json(run.result_summary_json) or {}
    result_summary["latest_ack_action"] = ack_event.action
    result_summary["latest_ack_at"] = ack_event.created_at

    if ack_event.action == "done":
        run.status = "acked"
        run.finished_at = ack_event.created_at
    elif ack_event.action == "dismissed":
        run.status = "cancelled"
        run.finished_at = ack_event.created_at
    else:
        run.status = "delivering"
    run.result_summary_json = dump_json(result_summary)
    db.flush()
    return ReminderAckResponse(
        run=_to_run_read(run),
        ack_event=ack_event,
        delivery_attempts=list_delivery_attempts(db, run_id=payload.run_id),
    )


def dispatch_due_reminders(
    db: Session,
    *,
    household_id: str,
    now_iso: str | None = None,
) -> ReminderSchedulerDispatchResponse:
    tasks = list_tasks(db, household_id=household_id, enabled=True)
    created_runs: list[ReminderRunRead] = []
    escalated_runs: list[ReminderRunRead] = []
    current_time = now_iso or utc_now_iso()

    for task in tasks:
        draft = build_run_draft(
            db,
            task=task,
            planned_at=_resolve_next_trigger_at(task, fallback_now=current_time),
            trigger_reason="schedule",
        )
        if not draft.can_create_run:
            continue
        run = create_run(
            db,
            ReminderRunCreate(
                task_id=task.id,
                household_id=task.household_id,
                schedule_slot_key=draft.slot.schedule_slot_key,
                trigger_reason=draft.slot.trigger_reason,
                planned_at=draft.slot.planned_at,
                started_at=current_time,
                status="pending",
                context_snapshot={"scheduled": True, "task_title": task.title},
                result_summary={},
            ),
        )
        _dispatch_delivery_attempts(db, task=task, run=run, escalated=False)
        created_runs.append(
            _finalize_run_after_delivery(
                db,
                run_id=run.id,
                ack_required=task.ack_required,
                auto_ack_reason="ack not required",
            )
        )

    for escalated_run in process_reminder_escalations(db, household_id=household_id, now_iso=current_time):
        escalated_runs.append(escalated_run)

    return ReminderSchedulerDispatchResponse(
        household_id=household_id,
        created_runs=created_runs,
        escalated_runs=escalated_runs,
    )


def process_reminder_escalations(
    db: Session,
    *,
    household_id: str,
    now_iso: str | None = None,
) -> list[ReminderRunRead]:
    current_time = now_iso or utc_now_iso()
    runs = list_runs(db, household_id=household_id, limit=200)
    task_cache = {task.id: task for task in list_tasks(db, household_id=household_id)}
    escalated_runs: list[ReminderRunRead] = []

    for run in runs:
        if run.status not in {"pending", "delivering"}:
            continue
        task = task_cache.get(run.task_id)
        if task is None or not task.ack_required:
            continue
        latest_ack = _get_latest_ack_for_run(db, run.id)
        if latest_ack is not None and latest_ack.action in {"done", "dismissed"}:
            continue

        existing_attempts = list_delivery_attempts(db, run_id=run.id)
        escalation_policy = task.escalation_policy or {}
        max_attempts = int(escalation_policy.get("max_attempts") or 2)
        if len(existing_attempts) >= max_attempts:
            row = repository.get_run(db, run.id)
            if row is not None:
                row.status = "expired"
                row.finished_at = current_time
                result_summary = load_json(row.result_summary_json) or {}
                result_summary["expired"] = True
                row.result_summary_json = dump_json(result_summary)
                db.flush()
                escalated_runs.append(_to_run_read(row))
            continue

        if existing_attempts:
            _create_escalation_attempt(db, task=task, run=run, attempt_index=len(existing_attempts), now_iso=current_time)
            row = repository.get_run(db, run.id)
            if row is not None:
                row.status = "delivering"
                result_summary = load_json(row.result_summary_json) or {}
                result_summary["escalated"] = True
                result_summary["last_escalation_at"] = current_time
                row.result_summary_json = dump_json(result_summary)
                db.flush()
                escalated_runs.append(_to_run_read(row))

    return escalated_runs


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


def _dispatch_delivery_attempts(
    db: Session,
    *,
    task: ReminderTaskRead,
    run: ReminderRunRead,
    escalated: bool,
) -> list[ReminderDeliveryAttemptRead]:
    active_member_id = task.target_member_ids[0] if task.target_member_ids else None
    delivery_plan = build_delivery_plan(task, active_member_id=active_member_id)
    attempts: list[ReminderDeliveryAttemptRead] = []
    for index, target in enumerate(delivery_plan.targets):
        attempts.append(
            create_delivery_attempt(
                db,
                ReminderDeliveryAttemptCreate(
                    run_id=run.id,
                    target_member_id=target.member_id,
                    target_room_id=target.room_id,
                    channel=target.channels[0] if target.channels else "admin_web",
                    attempt_index=index,
                    planned_at=run.planned_at,
                    sent_at=utc_now_iso(),
                    status="sent",
                    provider_result={"strategy": delivery_plan.strategy, "escalated": escalated},
                ),
            )
        )
    return attempts


def _finalize_run_after_delivery(
    db: Session,
    *,
    run_id: str,
    ack_required: bool,
    auto_ack_reason: str,
) -> ReminderRunRead:
    row = repository.get_run(db, run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder run not found")
    result_summary = load_json(row.result_summary_json) or {}
    if ack_required:
        row.status = "delivering"
    else:
        row.status = "acked"
        row.finished_at = utc_now_iso()
        result_summary["auto_ack_reason"] = auto_ack_reason
    row.result_summary_json = dump_json(result_summary)
    db.flush()
    return _to_run_read(row)


def _get_latest_ack_for_run(db: Session, run_id: str) -> ReminderAckEventRead | None:
    ack_events = list_ack_events(db, run_id=run_id)
    if not ack_events:
        return None
    return ack_events[-1]


def _create_escalation_attempt(
    db: Session,
    *,
    task: ReminderTaskRead,
    run: ReminderRunRead,
    attempt_index: int,
    now_iso: str,
) -> ReminderDeliveryAttemptRead:
    escalation_channels = task.escalation_policy.get("channels") or task.delivery_channels or ["admin_web"]
    target_member_id = task.owner_member_id or (task.target_member_ids[0] if task.target_member_ids else None)
    target_room_id = task.preferred_room_ids[0] if task.preferred_room_ids else None
    return create_delivery_attempt(
        db,
        ReminderDeliveryAttemptCreate(
            run_id=run.id,
            target_member_id=target_member_id,
            target_room_id=target_room_id,
            channel=escalation_channels[0],
            attempt_index=attempt_index,
            planned_at=run.planned_at,
            sent_at=now_iso,
            status="sent",
            provider_result={"escalation": True},
        ),
    )


def _resolve_next_trigger_at(task: ReminderTaskRead, fallback_now: str | None = None) -> str | None:
    if not task.enabled:
        return None
    if "next_at" in task.schedule_rule:
        return str(task.schedule_rule["next_at"])
    if "run_at" in task.schedule_rule:
        return str(task.schedule_rule["run_at"])
    if "planned_at" in task.schedule_rule:
        return str(task.schedule_rule["planned_at"])
    return fallback_now
