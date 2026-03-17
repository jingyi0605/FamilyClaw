from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent.service import AgentNotFoundError, resolve_effective_agent
from app.modules.scheduler.models import ScheduledTaskDefinition, ScheduledTaskDelivery
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import PluginExecutionError, enqueue_household_plugin_job
from app.modules.scheduler.models import ScheduledTaskRun
from app.modules.scheduler.runtime import finalize_task_run


def dispatch_task_run(db: Session, *, task_run_id: str) -> ScheduledTaskRun:
    run = db.get(ScheduledTaskRun, task_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scheduled task run not found")
    if run.status != "queued":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="scheduled task run is not queued")
    definition = db.get(ScheduledTaskDefinition, run.task_definition_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scheduled task definition not found")

    run.status = "dispatching"
    run.started_at = run.started_at or utc_now_iso()
    db.add(run)
    db.flush()

    try:
        dispatch_payload = _dispatch_run_by_target(db, run=run)
        run.status = "succeeded"
        run.target_run_id = dispatch_payload.get("target_run_id")
        run.dispatch_payload_json = dump_json(dispatch_payload)
        run.error_code = None
        run.error_message = None
        run.finished_at = utc_now_iso()
        db.add(run)
        db.flush()
        finalize_task_run(db, definition=definition, run=run)
        return run
    except PluginExecutionError as exc:
        run.status = "failed"
        run.error_code = exc.error_code
        run.error_message = exc.detail
        run.finished_at = utc_now_iso()
        db.add(run)
        db.flush()
        finalize_task_run(db, definition=definition, run=run)
        return run
    except (AgentNotFoundError, HTTPException) as exc:
        run.status = "failed"
        run.error_code = "scheduled_task_dispatch_failed"
        run.error_message = _resolve_dispatch_error_message(exc)
        run.finished_at = utc_now_iso()
        db.add(run)
        db.flush()
        finalize_task_run(db, definition=definition, run=run)
        return run


def _dispatch_run_by_target(db: Session, *, run: ScheduledTaskRun) -> dict[str, str | None]:
    if run.target_type == "plugin_job":
        plugin_job = _dispatch_plugin_job(db, run=run)
        return {
            "target_run_id": plugin_job.id,
            "plugin_job_id": plugin_job.id,
            "plugin_id": plugin_job.plugin_id,
            "trigger": plugin_job.trigger,
        }
    if run.target_type == "agent_reminder":
        delivery = _dispatch_agent_reminder(db, run=run)
        return {
            "target_run_id": delivery.id,
            "delivery_id": delivery.id,
            "agent_id": delivery.recipient_ref,
            "channel": delivery.channel,
        }
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported scheduled task target type")


def _dispatch_plugin_job(db: Session, *, run: ScheduledTaskRun):
    if not run.target_ref_id:
        raise PluginExecutionError("计划任务缺少插件标识")
    return enqueue_household_plugin_job(
        db,
        household_id=run.household_id,
        request=PluginExecutionRequest(
            plugin_id=run.target_ref_id,
            plugin_type="connector",
            payload={
                "scheduled_task_definition_id": run.task_definition_id,
                "scheduled_task_run_id": run.id,
                "owner_scope": run.owner_scope,
                "owner_member_id": run.owner_member_id,
                "scheduled_for": run.scheduled_for,
            },
            trigger="schedule",
        ),
        idempotency_key=run.idempotency_key,
        payload_summary={
            "source": "scheduled_task",
            "scheduled_task_definition_id": run.task_definition_id,
            "scheduled_task_run_id": run.id,
        },
        source_task_definition_id=run.task_definition_id,
        source_task_run_id=run.id,
    )


def _dispatch_agent_reminder(db: Session, *, run: ScheduledTaskRun) -> ScheduledTaskDelivery:
    agent = resolve_effective_agent(db, household_id=run.household_id, agent_id=run.target_ref_id)
    evaluation_snapshot = load_json(run.evaluation_snapshot_json) if run.evaluation_snapshot_json else {}
    payload = {
        "source": "scheduled_task",
        "scheduled_task_definition_id": run.task_definition_id,
        "scheduled_task_run_id": run.id,
        "owner_scope": run.owner_scope,
        "owner_member_id": run.owner_member_id,
        "scheduled_for": run.scheduled_for,
        "agent": {
            "id": agent.id,
            "name": agent.display_name,
            "type": agent.agent_type,
        },
        "reminder": _build_agent_reminder_payload(run=run, evaluation_snapshot=evaluation_snapshot if isinstance(evaluation_snapshot, dict) else {}),
    }
    delivery = ScheduledTaskDelivery(
        id=new_uuid(),
        task_run_id=run.id,
        channel="in_app",
        recipient_type="agent",
        recipient_ref=agent.id,
        status="queued",
        payload_json=dump_json(payload),
        delivered_at=utc_now_iso(),
        error_message=None,
    )
    db.add(delivery)
    db.flush()
    delivery.status = "delivered"
    db.add(delivery)
    db.flush()
    return delivery


def _resolve_dispatch_error_message(exc: AgentNotFoundError | HTTPException) -> str:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict):
            detail = exc.detail.get("detail")
            return str(detail) if detail is not None else str(exc.detail)
        return str(exc.detail)
    return str(exc)


def _build_agent_reminder_payload(*, run: ScheduledTaskRun, evaluation_snapshot: dict[str, object]) -> dict[str, object]:
    summary = f"计划任务 {run.task_definition_id} 命中，需要主动提醒。"
    if isinstance(evaluation_snapshot.get("rule_input"), dict):
        summary = f"计划任务命中规则，准备生成主动提醒。"
    return {
        "title": "计划任务提醒",
        "summary": summary,
        "evaluation_snapshot": evaluation_snapshot,
    }
