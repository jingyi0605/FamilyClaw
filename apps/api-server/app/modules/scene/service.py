from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.household.models import Household
from app.modules.scene import repository
from app.modules.scene.models import SceneExecution, SceneExecutionStep, SceneTemplate
from app.modules.scene.schemas import (
    SceneExecutionCreate,
    SceneExecutionRead,
    SceneExecutionStepCreate,
    SceneExecutionStepRead,
    SceneTemplateRead,
    SceneTemplateUpsert,
)


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


def list_executions(
    db: Session,
    *,
    household_id: str,
    template_id: str | None = None,
    limit: int = 50,
) -> list[SceneExecutionRead]:
    _ensure_household_exists(db, household_id)
    rows = repository.list_executions(
        db,
        household_id=household_id,
        template_id=template_id,
        limit=limit,
    )
    return [_to_execution_read(row) for row in rows]


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
