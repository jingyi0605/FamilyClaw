from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.scene.schemas import (
    SceneExecutionDetailRead,
    SceneExecutionRead,
    ScenePreviewRequest,
    ScenePreviewResponse,
    SceneTemplatePresetItem,
    SceneTemplateRead,
    SceneTemplateUpsert,
    SceneTriggerRequest,
)
from app.modules.scene.service import (
    get_execution_detail,
    list_builtin_scene_templates,
    list_executions,
    list_templates,
    preview_template,
    trigger_template,
    upsert_template,
)

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("/template-presets", response_model=list[SceneTemplatePresetItem])
def list_scene_template_presets_endpoint(
    household_id: str,
    actor: ActorContext = Depends(require_admin_actor),
) -> list[SceneTemplatePresetItem]:
    ensure_actor_can_access_household(actor, household_id)
    return list_builtin_scene_templates(household_id, updated_by=actor.actor_id or actor.actor_type)


@router.get("/templates", response_model=list[SceneTemplateRead])
def list_scene_templates_endpoint(
    household_id: str,
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> list[SceneTemplateRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_templates(db, household_id=household_id, enabled=enabled)


@router.put("/templates/{template_code}", response_model=SceneTemplateRead)
def upsert_scene_template_endpoint(
    template_code: str,
    payload: SceneTemplateUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> SceneTemplateRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    if payload.template_code != template_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path template_code 与 payload 不一致")
    try:
        result = upsert_template(db, payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="scene_template.upsert",
            target_type="scene_template",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/templates/{template_code}/preview", response_model=ScenePreviewResponse)
def preview_scene_template_endpoint(
    template_code: str,
    payload: ScenePreviewRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScenePreviewResponse:
    ensure_actor_can_access_household(actor, payload.household_id)
    return preview_template(db, household_id=payload.household_id, template_code=template_code, payload=payload)


@router.post("/templates/{template_code}/trigger", response_model=SceneExecutionDetailRead)
def trigger_scene_template_endpoint(
    template_code: str,
    payload: SceneTriggerRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> SceneExecutionDetailRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = trigger_template(db, household_id=payload.household_id, template_code=template_code, payload=payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="scene_template.trigger",
            target_type="scene_execution",
            target_id=result.execution.id,
            result="success",
            details={
                "template_code": template_code,
                "status": result.execution.status,
                "trigger_source": payload.trigger_source,
            },
        )
        for step in result.steps:
            write_audit_log(
                db,
                household_id=payload.household_id,
                actor=actor,
                action="scene_step.execute",
                target_type=step.step_type,
                target_id=step.target_ref,
                result="success" if step.status == "success" else "fail",
                details={
                    "execution_id": result.execution.id,
                    "step_index": step.step_index,
                    "status": step.status,
                    "request": step.request,
                    "result": step.result,
                },
            )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/executions", response_model=list[SceneExecutionRead])
def list_scene_executions_endpoint(
    household_id: str,
    template_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> list[SceneExecutionRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_executions(db, household_id=household_id, template_id=template_id, limit=limit)


@router.get("/executions/{execution_id}", response_model=SceneExecutionDetailRead)
def get_scene_execution_detail_endpoint(
    execution_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> SceneExecutionDetailRead:
    return get_execution_detail(db, execution_id)
