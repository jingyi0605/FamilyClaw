from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.scene.models import SceneExecution, SceneExecutionStep, SceneTemplate


def add_template(db: Session, row: SceneTemplate) -> SceneTemplate:
    db.add(row)
    return row


def get_template(db: Session, template_id: str) -> SceneTemplate | None:
    return db.get(SceneTemplate, template_id)


def get_template_by_code(db: Session, *, household_id: str, template_code: str) -> SceneTemplate | None:
    stmt = select(SceneTemplate).where(
        SceneTemplate.household_id == household_id,
        SceneTemplate.template_code == template_code,
    )
    return db.scalar(stmt)


def list_templates(db: Session, *, household_id: str, enabled: bool | None = None) -> Sequence[SceneTemplate]:
    stmt: Select[tuple[SceneTemplate]] = (
        select(SceneTemplate)
        .where(SceneTemplate.household_id == household_id)
        .order_by(SceneTemplate.priority.desc(), SceneTemplate.updated_at.desc())
    )
    if enabled is not None:
        stmt = stmt.where(SceneTemplate.enabled == enabled)
    return list(db.scalars(stmt).all())


def add_execution(db: Session, row: SceneExecution) -> SceneExecution:
    db.add(row)
    return row


def get_execution(db: Session, execution_id: str) -> SceneExecution | None:
    return db.get(SceneExecution, execution_id)


def get_execution_by_template_and_trigger(
    db: Session,
    *,
    template_id: str,
    trigger_key: str,
) -> SceneExecution | None:
    stmt = (
        select(SceneExecution)
        .where(SceneExecution.template_id == template_id)
        .where(SceneExecution.trigger_key == trigger_key)
        .order_by(SceneExecution.started_at.desc(), SceneExecution.id.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def list_executions(
    db: Session,
    *,
    household_id: str,
    template_id: str | None = None,
    limit: int = 50,
) -> Sequence[SceneExecution]:
    stmt: Select[tuple[SceneExecution]] = (
        select(SceneExecution)
        .where(SceneExecution.household_id == household_id)
        .order_by(SceneExecution.started_at.desc(), SceneExecution.id.desc())
        .limit(limit)
    )
    if template_id is not None:
        stmt = stmt.where(SceneExecution.template_id == template_id)
    return list(db.scalars(stmt).all())


def get_latest_execution_by_trigger(
    db: Session,
    *,
    template_id: str,
    trigger_key: str,
) -> SceneExecution | None:
    stmt = (
        select(SceneExecution)
        .where(SceneExecution.template_id == template_id)
        .where(SceneExecution.trigger_key == trigger_key)
        .order_by(SceneExecution.started_at.desc(), SceneExecution.id.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def add_execution_step(db: Session, row: SceneExecutionStep) -> SceneExecutionStep:
    db.add(row)
    return row


def list_execution_steps(db: Session, *, execution_id: str) -> Sequence[SceneExecutionStep]:
    stmt: Select[tuple[SceneExecutionStep]] = (
        select(SceneExecutionStep)
        .where(SceneExecutionStep.execution_id == execution_id)
        .order_by(SceneExecutionStep.step_index.asc(), SceneExecutionStep.id.asc())
    )
    return list(db.scalars(stmt).all())
