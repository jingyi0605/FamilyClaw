from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy.orm import Session

from app.modules.reminder import repository as reminder_repository
from app.modules.reminder.schemas import ReminderTaskRead
from app.modules.reminder_scheduler.schemas import ReminderRunDraft, ReminderScheduleSlot


def build_schedule_slot(
    task: ReminderTaskRead,
    *,
    planned_at: str | None = None,
    trigger_reason: str = "schedule",
    reference_time: datetime | None = None,
) -> ReminderScheduleSlot:
    resolved_planned_at = planned_at or _resolve_planned_at(task, reference_time=reference_time)
    payload = {
        "task_id": task.id,
        "version": task.version,
        "schedule_kind": task.schedule_kind,
        "schedule_rule": task.schedule_rule,
        "planned_at": resolved_planned_at,
        "trigger_reason": trigger_reason,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return ReminderScheduleSlot(
        task_id=task.id,
        household_id=task.household_id,
        planned_at=resolved_planned_at,
        trigger_reason=trigger_reason,
        schedule_slot_key=f"{task.id}:{digest}",
    )


def build_run_draft(
    db: Session,
    *,
    task: ReminderTaskRead,
    planned_at: str | None = None,
    trigger_reason: str = "schedule",
    reference_time: datetime | None = None,
) -> ReminderRunDraft:
    slot = build_schedule_slot(
        task,
        planned_at=planned_at,
        trigger_reason=trigger_reason,
        reference_time=reference_time,
    )
    if not task.enabled:
        return ReminderRunDraft(
            can_create_run=False,
            slot=slot,
            skip_reason="提醒任务已禁用，不创建新运行",
        )

    existing_run = reminder_repository.get_run_by_slot(
        db,
        task_id=task.id,
        schedule_slot_key=slot.schedule_slot_key,
    )
    if existing_run is not None:
        return ReminderRunDraft(
            can_create_run=False,
            slot=slot,
            skip_reason="同一提醒槽位已存在运行，不重复创建",
        )

    return ReminderRunDraft(
        can_create_run=True,
        slot=slot,
    )


def _resolve_planned_at(
    task: ReminderTaskRead,
    *,
    reference_time: datetime | None = None,
) -> str:
    if "run_at" in task.schedule_rule:
        return str(task.schedule_rule["run_at"])
    if "planned_at" in task.schedule_rule:
        return str(task.schedule_rule["planned_at"])
    if "next_at" in task.schedule_rule:
        return str(task.schedule_rule["next_at"])
    if reference_time is None:
        reference_time = datetime.now(timezone.utc).replace(microsecond=0)
    return reference_time.isoformat().replace("+00:00", "Z")
