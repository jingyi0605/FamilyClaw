from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.scheduler.models import ScheduledTaskDefinition, ScheduledTaskDelivery, ScheduledTaskRun


def finalize_task_run(
    db: Session,
    *,
    definition: ScheduledTaskDefinition,
    run: ScheduledTaskRun,
) -> None:
    definition.last_run_at = run.finished_at or run.scheduled_for or run.created_at
    definition.last_result = run.status

    if run.status in {"queued", "dispatching", "succeeded"}:
        definition.consecutive_failures = 0
        if definition.status == "error":
            definition.status = "active"
    elif run.status == "failed":
        definition.consecutive_failures += 1
        if _is_dependency_failure(run.error_code, run.error_message):
            definition.status = "invalid_dependency"
        elif definition.consecutive_failures >= settings.scheduler_definition_failure_threshold:
            definition.status = "error"

    definition.updated_at = utc_now_iso()
    db.add(definition)
    db.flush()

    if run.status in {"succeeded", "failed", "suppressed"}:
        create_task_status_delivery(db, definition=definition, run=run)


def create_task_status_delivery(
    db: Session,
    *,
    definition: ScheduledTaskDefinition,
    run: ScheduledTaskRun,
) -> ScheduledTaskDelivery:
    recipient_type = "member" if definition.owner_scope == "member" else "household"
    recipient_ref = definition.owner_member_id if definition.owner_scope == "member" else definition.household_id
    payload = {
        "event_type": "scheduled_task.run.updated",
        "task_definition_id": definition.id,
        "task_name": definition.name,
        "task_run_id": run.id,
        "status": run.status,
        "target_type": run.target_type,
        "target_ref_id": run.target_ref_id,
        "scheduled_for": run.scheduled_for,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "result_summary": _build_run_result_summary(definition=definition, run=run),
    }
    delivery = ScheduledTaskDelivery(
        id=new_uuid(),
        task_run_id=run.id,
        channel="in_app",
        recipient_type=recipient_type,
        recipient_ref=recipient_ref,
        status="delivered",
        payload_json=dump_json(payload),
        delivered_at=utc_now_iso(),
        error_message=None,
    )
    db.add(delivery)
    db.flush()
    return delivery


def _is_dependency_failure(error_code: str | None, error_message: str | None) -> bool:
    normalized = f"{error_code or ''} {error_message or ''}".lower()
    return any(
        token in normalized
        for token in [
            "not found",
            "缺少",
            "已禁用",
            "does not support schedule",
            "dependency",
            "agent",
            "plugin",
        ]
    )


def _build_run_result_summary(*, definition: ScheduledTaskDefinition, run: ScheduledTaskRun) -> str:
    if run.status == "succeeded":
        return f"{definition.name} 已按计划完成"
    if run.status == "suppressed":
        return f"{definition.name} 这次没有发出提醒"
    if run.status == "failed":
        return f"{definition.name} 这次没有成功，你可以稍后再试"
    return f"{definition.name} 状态已更新"
