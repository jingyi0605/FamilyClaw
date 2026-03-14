from copy import deepcopy

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.ai_gateway.gateway_service import ainvoke_capability, invoke_capability
from app.modules.ai_gateway.schemas import AiGatewayInvokeRequest
from app.modules.context.service import get_context_overview
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_action.service import aexecute_device_action, execute_device_action
from app.modules.household.models import Household
from app.modules.memory.schemas import EventRecordCreate
from app.modules.memory.service import ingest_event_record_best_effort
from app.modules.reminder.service import build_reminder_overview, trigger_task
from app.modules.scene import repository
from app.modules.scene.engine import can_start_scene_execution, scene_execution_lock
from app.modules.scene.models import SceneExecution, SceneExecutionStep, SceneTemplate
from app.modules.scene.schemas import (
    SceneExecutionCreate,
    SceneExecutionDetailRead,
    SceneExecutionRead,
    SceneExecutionStepCreate,
    SceneExecutionStepRead,
    ScenePreviewRequest,
    ScenePreviewResponse,
    ScenePreviewStep,
    SceneTemplatePresetItem,
    SceneTemplateRead,
    SceneTemplateUpsert,
    SceneTriggerRequest,
)

DEFAULT_SCENE_TEMPLATE_CODES = {"smart_homecoming", "child_bedtime", "elder_care"}


def _write_scene_memory_event(
    db: Session,
    *,
    execution_id: str,
    household_id: str,
    template: SceneTemplateRead,
    final_status: str,
    summary: dict[str, object],
    occurred_at: str,
) -> None:
    ingest_event_record_best_effort(
        db,
        EventRecordCreate(
            household_id=household_id,
            event_type="scene_executed",
            source_type="scene",
            source_ref=execution_id,
            payload={
                "memory_type": "event",
                "title": f"场景执行：{template.name}",
                "summary": f"场景《{template.name}》执行完成，结果是 {final_status}。",
                "visibility": "family",
                "importance": 3 if final_status == "success" else 2,
                "confidence": 0.96 if final_status == "success" else 0.75,
                "content": {
                    "template_code": template.template_code,
                    "template_name": template.name,
                    "execution_id": execution_id,
                    "status": final_status,
                    "summary": summary,
                },
                "card_dedupe_key": f"scene:{template.template_code}:{final_status}",
            },
            dedupe_key=f"scene-execution:{execution_id}",
            generate_memory_card=final_status in {"success", "partial", "blocked"},
            occurred_at=occurred_at,
        ),
    )


def list_builtin_scene_templates(
    household_id: str,
    *,
    updated_by: str | None = None,
) -> list[SceneTemplatePresetItem]:
    templates = [
        SceneTemplateUpsert(
            household_id=household_id,
            template_code="smart_homecoming",
            name="智能回家",
            description="成员回家后自动做一组欢迎动作。",
            enabled=True,
            priority=200,
            cooldown_seconds=600,
            trigger={"type": "manual_or_presence", "member_arrived": True},
            conditions=[{"code": "home_has_active_member", "label": "当前家庭有在家成员"}],
            guards=[
                {"code": "quiet_hours", "label": "静默时段保护"},
                {"code": "child_protection", "label": "儿童保护优先"},
            ],
            actions=[
                {"type": "device_action", "target_ref": "welcome_light", "device_type": "light", "action": "turn_on", "params": {"brightness": 70}},
                {"type": "broadcast", "target_ref": "speaker", "message": "欢迎回家"},
            ],
            rollout_policy={"audience": "household"},
            updated_by=updated_by,
        ),
        SceneTemplateUpsert(
            household_id=household_id,
            template_code="child_bedtime",
            name="儿童睡前",
            description="睡前关闭高干扰设备，并触发提醒。",
            enabled=True,
            priority=250,
            cooldown_seconds=1800,
            trigger={"type": "manual_or_schedule", "time_range": "20:00-22:00"},
            conditions=[{"code": "child_present", "label": "家里有儿童成员"}],
            guards=[
                {"code": "child_protection", "label": "儿童保护优先"},
                {"code": "sensitive_room", "label": "私密房间保护"},
            ],
            actions=[
                {"type": "device_action", "target_ref": "bedroom_speaker", "device_type": "speaker", "action": "set_volume", "params": {"volume": 20}},
                {"type": "broadcast", "target_ref": "bedroom_speaker", "message": "睡前时间到了"},
            ],
            rollout_policy={"audience": "child_related"},
            updated_by=updated_by,
        ),
        SceneTemplateUpsert(
            household_id=household_id,
            template_code="elder_care",
            name="老人关怀",
            description="给老人相关提醒和保守广播。",
            enabled=True,
            priority=220,
            cooldown_seconds=1200,
            trigger={"type": "manual_or_schedule", "elder_care": True},
            conditions=[{"code": "elder_present", "label": "家里有老人成员"}],
            guards=[
                {"code": "quiet_hours", "label": "静默时段保护"},
                {"code": "public_broadcast_privacy", "label": "公共广播隐私保护"},
            ],
            actions=[
                {"type": "broadcast", "target_ref": "living_room_speaker", "message": "请关注老人状态"},
                {"type": "context_update", "target_ref": "service_center", "payload": {"note": "elder care checkin"}},
            ],
            rollout_policy={"audience": "elder_related"},
            updated_by=updated_by,
        ),
    ]
    return [
        SceneTemplatePresetItem(
            template_code=item.template_code,
            name=item.name,
            description=item.description or "",
            payload=item,
        )
        for item in templates
    ]


def upsert_template(db: Session, payload: SceneTemplateUpsert) -> SceneTemplateRead:
    _ensure_household_exists(db, payload.household_id)
    row = repository.get_template_by_code(
        db,
        household_id=payload.household_id,
        template_code=payload.template_code,
    )

    if row is None:
        row = SceneTemplate(
            id=new_uuid(),
            household_id=payload.household_id,
            template_code=payload.template_code,
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            priority=payload.priority,
            cooldown_seconds=payload.cooldown_seconds,
            trigger_json=dump_json(payload.trigger) or "{}",
            conditions_json=dump_json(payload.conditions) or "[]",
            guards_json=dump_json(payload.guards) or "[]",
            actions_json=dump_json(payload.actions) or "[]",
            rollout_policy_json=dump_json(payload.rollout_policy),
            version=1,
            updated_by=payload.updated_by,
            updated_at=utc_now_iso(),
        )
        repository.add_template(db, row)
    else:
        row.name = payload.name
        row.description = payload.description
        row.enabled = payload.enabled
        row.priority = payload.priority
        row.cooldown_seconds = payload.cooldown_seconds
        row.trigger_json = dump_json(payload.trigger) or "{}"
        row.conditions_json = dump_json(payload.conditions) or "[]"
        row.guards_json = dump_json(payload.guards) or "[]"
        row.actions_json = dump_json(payload.actions) or "[]"
        row.rollout_policy_json = dump_json(payload.rollout_policy)
        row.updated_by = payload.updated_by
        row.version += 1
        row.updated_at = utc_now_iso()

    db.flush()
    return _to_template_read(row)


def list_templates(db: Session, *, household_id: str, enabled: bool | None = None) -> list[SceneTemplateRead]:
    _ensure_household_exists(db, household_id)
    rows = repository.list_templates(db, household_id=household_id, enabled=enabled)
    return [_to_template_read(row) for row in rows]


def preview_template(
    db: Session,
    *,
    household_id: str,
    template_code: str,
    payload: ScenePreviewRequest,
) -> ScenePreviewResponse:
    template = _get_template_by_code_or_404(db, household_id=household_id, template_code=template_code)
    context_overview = get_context_overview(db, household_id)
    reminder_overview = build_reminder_overview(db, household_id=household_id)
    can_start, conflict_reason, trigger_key, _lock_key = can_start_scene_execution(
        db,
        template=template,
        trigger_source=payload.trigger_source,
        trigger_payload=payload.trigger_payload,
    )

    matched_conditions = _evaluate_conditions(template, context_overview)
    blocked_guards = _evaluate_guards(template, context_overview, payload.confirm_high_risk)
    if not can_start and conflict_reason is not None:
        blocked_guards.append(conflict_reason)

    preview_steps = _build_preview_steps(
        template=template,
        context_household_id=household_id,
        reminder_overview_count=reminder_overview.pending_runs,
        confirm_high_risk=payload.confirm_high_risk,
        blocked=bool(blocked_guards),
    )
    explanation, degraded = _build_scene_explanation(
        db,
        household_id=household_id,
        template=template,
        trigger_key=trigger_key,
        blocked_guards=blocked_guards,
        step_count=len(preview_steps),
    )
    return ScenePreviewResponse(
        household_id=household_id,
        template=template,
        trigger_key=trigger_key,
        matched_conditions=matched_conditions,
        blocked_guards=blocked_guards,
        requires_confirmation=any(step.status == "blocked" for step in preview_steps),
        steps=preview_steps,
        explanation=explanation,
        degraded=degraded,
    )


async def apreview_template(
    db: Session,
    *,
    household_id: str,
    template_code: str,
    payload: ScenePreviewRequest,
) -> ScenePreviewResponse:
    template = _get_template_by_code_or_404(db, household_id=household_id, template_code=template_code)
    context_overview = get_context_overview(db, household_id)
    reminder_overview = build_reminder_overview(db, household_id=household_id)
    can_start, conflict_reason, trigger_key, _lock_key = can_start_scene_execution(
        db,
        template=template,
        trigger_source=payload.trigger_source,
        trigger_payload=payload.trigger_payload,
    )

    matched_conditions = _evaluate_conditions(template, context_overview)
    blocked_guards = _evaluate_guards(template, context_overview, payload.confirm_high_risk)
    if not can_start and conflict_reason is not None:
        blocked_guards.append(conflict_reason)

    preview_steps = _build_preview_steps(
        template=template,
        context_household_id=household_id,
        reminder_overview_count=reminder_overview.pending_runs,
        confirm_high_risk=payload.confirm_high_risk,
        blocked=bool(blocked_guards),
    )
    explanation, degraded = await _abuild_scene_explanation(
        db,
        household_id=household_id,
        template=template,
        trigger_key=trigger_key,
        blocked_guards=blocked_guards,
        step_count=len(preview_steps),
    )
    return ScenePreviewResponse(
        household_id=household_id,
        template=template,
        trigger_key=trigger_key,
        matched_conditions=matched_conditions,
        blocked_guards=blocked_guards,
        requires_confirmation=any(step.status == "blocked" for step in preview_steps),
        steps=preview_steps,
        explanation=explanation,
        degraded=degraded,
    )


def trigger_template(
    db: Session,
    *,
    household_id: str,
    template_code: str,
    payload: SceneTriggerRequest,
) -> SceneExecutionDetailRead:
    preview = preview_template(
        db,
        household_id=household_id,
        template_code=template_code,
        payload=ScenePreviewRequest.model_validate(payload.model_dump(mode="json")),
    )
    template = preview.template
    can_start, conflict_reason, trigger_key, lock_key = can_start_scene_execution(
        db,
        template=template,
        trigger_source=payload.trigger_source,
        trigger_payload=payload.trigger_payload,
    )
    if not can_start:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_reason or "scene conflict")

    with scene_execution_lock(lock_key) as acquired:
        if not acquired:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="scene execution lock busy")
        execution = create_execution(
            db,
            SceneExecutionCreate(
                template_id=template.id,
                household_id=household_id,
                trigger_key=trigger_key,
                trigger_source=payload.trigger_source,
                started_at=utc_now_iso(),
                status="running",
                guard_result={"blocked_guards": preview.blocked_guards},
                conflict_result={},
                context_snapshot={"trigger_payload": payload.trigger_payload},
                summary={"template_code": template.template_code},
            ),
        )
        step_rows: list[SceneExecutionStepRead] = []
        blocked_guards = list(preview.blocked_guards)
        if blocked_guards:
            row = repository.get_execution(db, execution.id)
            if row is not None:
                row.status = "blocked"
                row.finished_at = utc_now_iso()
                row.summary_json = dump_json({"blocked_guards": blocked_guards, "template_code": template.template_code})
                db.flush()
                _write_scene_memory_event(
                    db,
                    execution_id=execution.id,
                    household_id=household_id,
                    template=template,
                    final_status="blocked",
                    summary={"blocked_guards": blocked_guards, "template_code": template.template_code},
                    occurred_at=row.finished_at,
                )
    return get_execution_detail(db, execution.id)


async def atrigger_template(
    db: Session,
    *,
    household_id: str,
    template_code: str,
    payload: SceneTriggerRequest,
) -> SceneExecutionDetailRead:
    preview = await apreview_template(
        db,
        household_id=household_id,
        template_code=template_code,
        payload=ScenePreviewRequest.model_validate(payload.model_dump(mode="json")),
    )
    template = preview.template
    can_start, conflict_reason, trigger_key, lock_key = can_start_scene_execution(
        db,
        template=template,
        trigger_source=payload.trigger_source,
        trigger_payload=payload.trigger_payload,
    )
    if not can_start:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_reason or "scene conflict")

    with scene_execution_lock(lock_key) as acquired:
        if not acquired:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="scene execution lock busy")
        execution = create_execution(
            db,
            SceneExecutionCreate(
                template_id=template.id,
                household_id=household_id,
                trigger_key=trigger_key,
                trigger_source=payload.trigger_source,
                started_at=utc_now_iso(),
                status="running",
                guard_result={"blocked_guards": preview.blocked_guards},
                conflict_result={},
                context_snapshot={"trigger_payload": payload.trigger_payload},
                summary={"template_code": template.template_code},
            ),
        )
        step_rows: list[SceneExecutionStepRead] = []
        blocked_guards = list(preview.blocked_guards)
        if blocked_guards:
            row = repository.get_execution(db, execution.id)
            if row is not None:
                row.status = "blocked"
                row.finished_at = utc_now_iso()
                row.summary_json = dump_json({"blocked_guards": blocked_guards, "template_code": template.template_code})
                db.flush()
                _write_scene_memory_event(db, execution_id=execution.id, household_id=household_id, template=template, final_status="blocked", summary={"blocked_guards": blocked_guards, "template_code": template.template_code}, occurred_at=row.finished_at or utc_now_iso())
            return get_execution_detail(db, execution.id)

        final_status = "success"
        summary: dict[str, object] = {"template_code": template.template_code, "step_results": []}
        for step_index, action in enumerate(template.actions):
            step_result = await _aexecute_action_step(
                db,
                household_id=household_id,
                template=template,
                execution_id=execution.id,
                action=action,
                step_index=step_index,
                confirm_high_risk=payload.confirm_high_risk,
            )
            step_rows.append(step_result)
            summary["step_results"].append({"step_index": step_result.step_index, "step_type": step_result.step_type, "status": step_result.status, "target_ref": step_result.target_ref})
            if step_result.status in {"failed", "blocked"}:
                final_status = "partial" if final_status == "success" else final_status
                if step_result.status == "blocked":
                    final_status = "blocked"

        row = repository.get_execution(db, execution.id)
        if row is not None:
            row.status = final_status
            row.finished_at = utc_now_iso()
            row.summary_json = dump_json(summary)
            db.flush()
            _write_scene_memory_event(db, execution_id=execution.id, household_id=household_id, template=template, final_status=final_status, summary=summary, occurred_at=row.finished_at or utc_now_iso())
        return get_execution_detail(db, execution.id)

        final_status = "success"
        summary: dict[str, object] = {"template_code": template.template_code, "step_results": []}
        for step_index, action in enumerate(template.actions):
            step_result = _execute_action_step(
                db,
                household_id=household_id,
                template=template,
                execution_id=execution.id,
                action=action,
                step_index=step_index,
                confirm_high_risk=payload.confirm_high_risk,
            )
            step_rows.append(step_result)
            summary["step_results"].append(
                {
                    "step_index": step_result.step_index,
                    "step_type": step_result.step_type,
                    "status": step_result.status,
                    "target_ref": step_result.target_ref,
                }
            )
            if step_result.status in {"failed", "blocked"}:
                final_status = "partial" if final_status == "success" else final_status
                if step_result.status == "blocked":
                    final_status = "blocked"

        row = repository.get_execution(db, execution.id)
        if row is not None:
            row.status = final_status
            row.finished_at = utc_now_iso()
            row.summary_json = dump_json(summary)
            db.flush()
            _write_scene_memory_event(
                db,
                execution_id=execution.id,
                household_id=household_id,
                template=template,
                final_status=final_status,
                summary=summary,
                occurred_at=row.finished_at,
            )
        return get_execution_detail(db, execution.id)


def list_executions(
    db: Session,
    *,
    household_id: str,
    template_id: str | None = None,
    limit: int = 50,
) -> list[SceneExecutionRead]:
    _ensure_household_exists(db, household_id)
    rows = repository.list_executions(db, household_id=household_id, template_id=template_id, limit=limit)
    return [_to_execution_read(row) for row in rows]


def get_execution_detail(db: Session, execution_id: str) -> SceneExecutionDetailRead:
    execution = repository.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene execution not found")
    steps = repository.list_execution_steps(db, execution_id=execution_id)
    return SceneExecutionDetailRead(
        execution=_to_execution_read(execution),
        steps=[_to_execution_step_read(step) for step in steps],
    )


def create_execution(db: Session, payload: SceneExecutionCreate) -> SceneExecutionRead:
    template = repository.get_template(db, payload.template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene template not found")
    if template.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scene execution household mismatch")

    row = SceneExecution(
        id=new_uuid(),
        template_id=payload.template_id,
        household_id=payload.household_id,
        trigger_key=payload.trigger_key,
        trigger_source=payload.trigger_source,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        status=payload.status,
        guard_result_json=dump_json(payload.guard_result),
        conflict_result_json=dump_json(payload.conflict_result),
        context_snapshot_json=dump_json(payload.context_snapshot),
        summary_json=dump_json(payload.summary),
    )
    repository.add_execution(db, row)
    db.flush()
    return _to_execution_read(row)


def create_execution_step(db: Session, payload: SceneExecutionStepCreate) -> SceneExecutionStepRead:
    execution = repository.get_execution(db, payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene execution not found")

    row = SceneExecutionStep(
        id=new_uuid(),
        execution_id=payload.execution_id,
        step_index=payload.step_index,
        step_type=payload.step_type,
        target_ref=payload.target_ref,
        request_json=dump_json(payload.request),
        result_json=dump_json(payload.result),
        status=payload.status,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
    )
    repository.add_execution_step(db, row)
    db.flush()
    return _to_execution_step_read(row)


def list_execution_steps(db: Session, *, execution_id: str) -> list[SceneExecutionStepRead]:
    execution = repository.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene execution not found")
    rows = repository.list_execution_steps(db, execution_id=execution_id)
    return [_to_execution_step_read(row) for row in rows]


def _execute_action_step(
    db: Session,
    *,
    household_id: str,
    template: SceneTemplateRead,
    execution_id: str,
    action: dict[str, object],
    step_index: int,
    confirm_high_risk: bool,
) -> SceneExecutionStepRead:
    step_type = str(action.get("type") or "context_update")
    target_ref = str(action.get("target_ref") or "")
    request_payload = deepcopy(action)
    started_at = utc_now_iso()

    if step_type == "device_action":
        device_id = str(action.get("device_id") or "")
        if not device_id:
            return create_execution_step(
                db,
                SceneExecutionStepCreate(
                    execution_id=execution_id,
                    step_index=step_index,
                    step_type="device_action",
                    target_ref=target_ref or "unknown-device",
                    request=request_payload,
                    result={"error": "缺少 device_id"},
                    status="failed",
                    started_at=started_at,
                    finished_at=utc_now_iso(),
                ),
            )
        try:
            response, _audit_context = execute_device_action(
                db,
                payload=DeviceActionExecuteRequest(
                    household_id=household_id,
                    device_id=device_id,
                    action=str(action.get("action") or "turn_on"),
                    params=action.get("params") if isinstance(action.get("params"), dict) else {},
                    reason=f"scene.{template.template_code}",
                    confirm_high_risk=confirm_high_risk,
                ),
            )
            return create_execution_step(
                db,
                SceneExecutionStepCreate(
                    execution_id=execution_id,
                    step_index=step_index,
                    step_type="device_action",
                    target_ref=target_ref or device_id,
                    request=request_payload,
                    result=response.model_dump(mode="json"),
                    status="success",
                    started_at=started_at,
                    finished_at=utc_now_iso(),
                ),
            )
        except HTTPException as exc:
            return create_execution_step(
                db,
                SceneExecutionStepCreate(
                    execution_id=execution_id,
                    step_index=step_index,
                    step_type="device_action",
                    target_ref=target_ref or device_id,
                    request=request_payload,
                    result={"error": exc.detail},
                    status="blocked" if exc.status_code == status.HTTP_403_FORBIDDEN else "failed",
                    started_at=started_at,
                    finished_at=utc_now_iso(),
                ),
            )

    if step_type == "reminder":
        reminder_id = str(action.get("reminder_id") or "")
        if not reminder_id:
            return create_execution_step(
                db,
                SceneExecutionStepCreate(
                    execution_id=execution_id,
                    step_index=step_index,
                    step_type="reminder",
                    target_ref=target_ref or "unknown-reminder",
                    request=request_payload,
                    result={"error": "缺少 reminder_id"},
                    status="failed",
                    started_at=started_at,
                    finished_at=utc_now_iso(),
                ),
            )
        reminder_result = trigger_task(db, task_id=reminder_id, trigger_reason=f"scene:{template.template_code}")
        return create_execution_step(
            db,
            SceneExecutionStepCreate(
                execution_id=execution_id,
                step_index=step_index,
                step_type="reminder",
                target_ref=target_ref or reminder_id,
                request=request_payload,
                result=reminder_result.model_dump(mode="json"),
                status="success",
                started_at=started_at,
                finished_at=utc_now_iso(),
            ),
        )

    if step_type == "broadcast":
        return create_execution_step(
            db,
            SceneExecutionStepCreate(
                execution_id=execution_id,
                step_index=step_index,
                step_type="broadcast",
                target_ref=target_ref or "broadcast",
                request=request_payload,
                result={"message": str(action.get("message") or "")},
                status="success",
                started_at=started_at,
                finished_at=utc_now_iso(),
            ),
        )

    return create_execution_step(
        db,
        SceneExecutionStepCreate(
            execution_id=execution_id,
            step_index=step_index,
            step_type="context_update",
            target_ref=target_ref or "context",
            request=request_payload,
            result={"applied": True},
            status="success",
            started_at=started_at,
            finished_at=utc_now_iso(),
        ),
    )


async def _aexecute_action_step(
    db: Session,
    *,
    household_id: str,
    template: SceneTemplateRead,
    execution_id: str,
    action: dict[str, object],
    step_index: int,
    confirm_high_risk: bool,
) -> SceneExecutionStepRead:
    step_type = str(action.get("type") or "context_update")
    target_ref = str(action.get("target_ref") or "")
    request_payload = deepcopy(action)
    started_at = utc_now_iso()
    if step_type == "device_action":
        device_id = str(action.get("device_id") or "")
        if not device_id:
            return create_execution_step(db, SceneExecutionStepCreate(execution_id=execution_id, step_index=step_index, step_type="device_action", target_ref=target_ref or "unknown-device", request=request_payload, result={"error": "缺少 device_id"}, status="failed", started_at=started_at, finished_at=utc_now_iso()))
        try:
            response, _audit_context = await aexecute_device_action(
                db,
                payload=DeviceActionExecuteRequest(
                    household_id=household_id,
                    device_id=device_id,
                    action=str(action.get("action") or "turn_on"),
                    params=action.get("params") if isinstance(action.get("params"), dict) else {},
                    reason=f"scene.{template.template_code}",
                    confirm_high_risk=confirm_high_risk,
                ),
            )
            return create_execution_step(db, SceneExecutionStepCreate(execution_id=execution_id, step_index=step_index, step_type="device_action", target_ref=target_ref or device_id, request=request_payload, result=response.model_dump(mode="json"), status="success", started_at=started_at, finished_at=utc_now_iso()))
        except HTTPException as exc:
            return create_execution_step(db, SceneExecutionStepCreate(execution_id=execution_id, step_index=step_index, step_type="device_action", target_ref=target_ref or device_id, request=request_payload, result={"error": exc.detail}, status="blocked" if exc.status_code == status.HTTP_403_FORBIDDEN else "failed", started_at=started_at, finished_at=utc_now_iso()))
    return _execute_action_step(db, household_id=household_id, template=template, execution_id=execution_id, action=action, step_index=step_index, confirm_high_risk=confirm_high_risk)


def _evaluate_conditions(template: SceneTemplateRead, context_overview) -> list[str]:
    matched: list[str] = []
    for item in template.conditions:
        code = str(item.get("code") or "")
        if code == "home_has_active_member" and context_overview.active_member is not None:
            matched.append(str(item.get("label") or code))
        elif code == "child_present" and any(member.role == "child" for member in context_overview.member_states):
            matched.append(str(item.get("label") or code))
        elif code == "elder_present" and any(member.role == "elder" for member in context_overview.member_states):
            matched.append(str(item.get("label") or code))
    return matched


def _evaluate_guards(
    template: SceneTemplateRead,
    context_overview,
    confirm_high_risk: bool,
) -> list[str]:
    blocked: list[str] = []
    for item in template.guards:
        code = str(item.get("code") or "")
        label = str(item.get("label") or code)
        if code == "quiet_hours" and context_overview.quiet_hours_enabled:
            blocked.append(f"{label}：当前家庭开启了静默时段")
        if code == "child_protection" and context_overview.child_protection_enabled and any(
            action.get("type") == "device_action" for action in template.actions
        ):
            blocked.append(f"{label}：儿童保护开启时不自动放行场景动作")
        if code == "public_broadcast_privacy" and any(action.get("type") == "broadcast" for action in template.actions):
            blocked.append(f"{label}：公共广播需要避免暴露私密内容")
        if code == "sensitive_room" and any(room.privacy_level == "sensitive" for room in context_overview.room_occupancy):
            blocked.append(f"{label}：存在敏感房间，占位阻断")
    if not confirm_high_risk and any(
        action.get("type") == "device_action" and str(action.get("action")) == "unlock"
        for action in template.actions
    ):
        blocked.append("存在高风险设备动作，但当前没有确认")
    return blocked


def _build_preview_steps(
    *,
    template: SceneTemplateRead,
    context_household_id: str,
    reminder_overview_count: int,
    confirm_high_risk: bool,
    blocked: bool,
) -> list[ScenePreviewStep]:
    steps: list[ScenePreviewStep] = []
    for index, action in enumerate(template.actions):
        step_type = str(action.get("type") or "context_update")
        target_ref = str(action.get("target_ref") or "")
        status_value = "planned"
        summary = "准备执行"
        if blocked:
            status_value = "blocked"
            summary = "当前命中守卫或冲突，暂不执行"
        elif step_type == "broadcast":
            summary = f"准备广播：{action.get('message') or '空消息'}"
        elif step_type == "reminder":
            summary = f"准备触发提醒，当前待处理提醒 {reminder_overview_count} 个"
        elif step_type == "device_action":
            summary = f"准备执行设备动作：{action.get('action') or 'unknown'}"
            if str(action.get("action")) == "unlock" and not confirm_high_risk:
                status_value = "blocked"
                summary = "门锁解锁属于高风险动作，需要确认"
        else:
            summary = "准备更新上下文摘要"
        steps.append(
            ScenePreviewStep(
                step_index=index,
                step_type=step_type,  # type: ignore[arg-type]
                target_ref=target_ref or None,
                status=status_value,  # type: ignore[arg-type]
                summary=summary,
                request=deepcopy(action),
            )
        )
    return steps


def _build_scene_explanation(
    db: Session,
    *,
    household_id: str,
    template: SceneTemplateRead,
    trigger_key: str,
    blocked_guards: list[str],
    step_count: int,
) -> tuple[str | None, bool]:
    try:
        response = invoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="scene_explanation",
                household_id=household_id,
                payload={
                    "scene_name": template.name,
                    "template_code": template.template_code,
                    "trigger_key": trigger_key,
                    "blocked_guards": blocked_guards,
                    "step_count": step_count,
                },
            ),
        )
        return str(response.normalized_output.get("text") or ""), response.degraded
    except HTTPException:
        if blocked_guards:
            return f"{template.name} 当前未执行，原因是：{'；'.join(blocked_guards)}。", True
        return f"{template.name} 将按 {step_count} 个步骤执行。", True


async def _abuild_scene_explanation(
    db: Session,
    *,
    household_id: str,
    template: SceneTemplateRead,
    trigger_key: str,
    blocked_guards: list[str],
    step_count: int,
) -> tuple[str | None, bool]:
    try:
        response = await ainvoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="scene_explanation",
                household_id=household_id,
                payload={
                    "scene_name": template.name,
                    "template_code": template.template_code,
                    "trigger_key": trigger_key,
                    "blocked_guards": blocked_guards,
                    "step_count": step_count,
                },
            ),
        )
        return str(response.normalized_output.get("text") or ""), response.degraded
    except HTTPException:
        if blocked_guards:
            return f"{template.name} 当前未执行，原因是：{'；'.join(blocked_guards)}。", True
        return f"{template.name} 将按 {step_count} 个步骤执行。", True


def _get_template_by_code_or_404(
    db: Session,
    *,
    household_id: str,
    template_code: str,
) -> SceneTemplateRead:
    row = repository.get_template_by_code(db, household_id=household_id, template_code=template_code)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scene template not found")
    return _to_template_read(row)


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")


def _to_template_read(row: SceneTemplate) -> SceneTemplateRead:
    return SceneTemplateRead(
        id=row.id,
        household_id=row.household_id,
        template_code=row.template_code,
        name=row.name,
        description=row.description,
        enabled=row.enabled,
        priority=row.priority,
        cooldown_seconds=row.cooldown_seconds,
        trigger=load_json(row.trigger_json) or {},
        conditions=load_json(row.conditions_json) or [],
        guards=load_json(row.guards_json) or [],
        actions=load_json(row.actions_json) or [],
        rollout_policy=load_json(row.rollout_policy_json) or {},
        version=row.version,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _to_execution_read(row: SceneExecution) -> SceneExecutionRead:
    return SceneExecutionRead(
        id=row.id,
        template_id=row.template_id,
        household_id=row.household_id,
        trigger_key=row.trigger_key,
        trigger_source=row.trigger_source,
        started_at=row.started_at,
        finished_at=row.finished_at,
        status=row.status,
        guard_result=load_json(row.guard_result_json) or {},
        conflict_result=load_json(row.conflict_result_json) or {},
        context_snapshot=load_json(row.context_snapshot_json) or {},
        summary=load_json(row.summary_json) or {},
    )


def _to_execution_step_read(row: SceneExecutionStep) -> SceneExecutionStepRead:
    return SceneExecutionStepRead(
        id=row.id,
        execution_id=row.execution_id,
        step_index=row.step_index,
        step_type=row.step_type,
        target_ref=row.target_ref,
        request=load_json(row.request_json) or {},
        result=load_json(row.result_json) or {},
        status=row.status,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
