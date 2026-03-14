from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.account.service import AuthenticatedActor
from app.modules.audit.service import write_audit_log
from app.modules.scheduler.schemas import (
    ScheduledTaskDefinitionCreate,
    ScheduledTaskDefinitionRead,
    ScheduledTaskDraftConfirmRequest,
    ScheduledTaskDraftFromConversationRequest,
    ScheduledTaskDraftRead,
    ScheduledTaskDefinitionUpdate,
    ScheduledTaskRunRead,
)
from app.modules.scheduler.draft_service import confirm_draft_from_conversation, create_draft_from_conversation
from app.modules.scheduler.service import (
    create_task_definition,
    delete_task_definition,
    get_task_definition_read_or_404,
    list_task_definitions,
    list_task_runs,
    set_task_enabled,
    update_task_definition,
)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])
run_router = APIRouter(prefix="/scheduled-task-runs", tags=["scheduled-tasks"])
draft_router = APIRouter(prefix="/scheduled-task-drafts", tags=["scheduled-tasks"])


def _to_authenticated_actor(actor: ActorContext) -> AuthenticatedActor:
    return AuthenticatedActor(
        account_id=actor.account_id or "",
        username=actor.username or "",
        account_type=actor.account_type,
        account_status=actor.account_status,
        household_id=actor.household_id,
        member_id=actor.member_id,
        member_role=actor.member_role,
        must_change_password=actor.must_change_password,
    )


@router.post("", response_model=ScheduledTaskDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_scheduled_task_endpoint(
    payload: ScheduledTaskDefinitionCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDefinitionRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = create_task_definition(db, actor=_to_authenticated_actor(actor), payload=payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="scheduled_task.create",
            target_type="scheduled_task_definition",
            target_id=result.id,
            result="success",
            details=payload.model_dump(mode="json"),
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> None:
    try:
        task = get_task_definition_read_or_404(db, actor=_to_authenticated_actor(actor), task_id=task_id)
        delete_task_definition(db, actor=_to_authenticated_actor(actor), task_id=task_id)
        write_audit_log(
            db,
            household_id=task.household_id,
            actor=actor,
            action="scheduled_task.delete",
            target_type="scheduled_task_definition",
            target_id=task_id,
            result="success",
            details={"task_id": task_id},
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("", response_model=list[ScheduledTaskDefinitionRead])
def list_scheduled_tasks_endpoint(
    household_id: str = Query(min_length=1),
    owner_scope: str | None = Query(default=None),
    owner_member_id: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    trigger_type: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> list[ScheduledTaskDefinitionRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_task_definitions(
        db,
        actor=_to_authenticated_actor(actor),
        household_id=household_id,
        owner_scope=owner_scope,
        owner_member_id=owner_member_id,
        enabled=enabled,
        trigger_type=trigger_type,
        target_type=target_type,
        status_value=status_value,
    )


@router.get("/{task_id}", response_model=ScheduledTaskDefinitionRead)
def get_scheduled_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDefinitionRead:
    return get_task_definition_read_or_404(db, actor=_to_authenticated_actor(actor), task_id=task_id)


@router.patch("/{task_id}", response_model=ScheduledTaskDefinitionRead)
def update_scheduled_task_endpoint(
    task_id: str,
    payload: ScheduledTaskDefinitionUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDefinitionRead:
    try:
        result = update_task_definition(db, actor=_to_authenticated_actor(actor), task_id=task_id, payload=payload)
        write_audit_log(
            db,
            household_id=result.household_id,
            actor=actor,
            action="scheduled_task.update",
            target_type="scheduled_task_definition",
            target_id=task_id,
            result="success",
            details=payload.model_dump(mode="json", exclude_unset=True),
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/{task_id}/enable", response_model=ScheduledTaskDefinitionRead)
def enable_scheduled_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDefinitionRead:
    try:
        result = set_task_enabled(db, actor=_to_authenticated_actor(actor), task_id=task_id, enabled=True)
        write_audit_log(
            db,
            household_id=result.household_id,
            actor=actor,
            action="scheduled_task.enable",
            target_type="scheduled_task_definition",
            target_id=task_id,
            result="success",
            details={"enabled": True},
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise


@router.post("/{task_id}/disable", response_model=ScheduledTaskDefinitionRead)
def disable_scheduled_task_endpoint(
    task_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDefinitionRead:
    try:
        result = set_task_enabled(db, actor=_to_authenticated_actor(actor), task_id=task_id, enabled=False)
        write_audit_log(
            db,
            household_id=result.household_id,
            actor=actor,
            action="scheduled_task.disable",
            target_type="scheduled_task_definition",
            target_id=task_id,
            result="success",
            details={"enabled": False},
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise


@run_router.get("", response_model=list[ScheduledTaskRunRead])
def list_scheduled_task_runs_endpoint(
    household_id: str = Query(min_length=1),
    task_definition_id: str | None = Query(default=None),
    owner_scope: str | None = Query(default=None),
    owner_member_id: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> list[ScheduledTaskRunRead]:
    ensure_actor_can_access_household(actor, household_id)
    return list_task_runs(
        db,
        actor=_to_authenticated_actor(actor),
        household_id=household_id,
        task_definition_id=task_definition_id,
        owner_scope=owner_scope,
        owner_member_id=owner_member_id,
        status_value=status_value,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )


@draft_router.post("/from-conversation", response_model=ScheduledTaskDraftRead)
def create_scheduled_task_draft_from_conversation_endpoint(
    payload: ScheduledTaskDraftFromConversationRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ScheduledTaskDraftRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = create_draft_from_conversation(db, actor=_to_authenticated_actor(actor), payload=payload)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise


@draft_router.post("/{draft_id}/confirm")
def confirm_scheduled_task_draft_endpoint(
    draft_id: str,
    payload: ScheduledTaskDraftConfirmRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> dict[str, object]:
    try:
        draft, task_id = confirm_draft_from_conversation(db, actor=_to_authenticated_actor(actor), draft_id=draft_id, payload=payload)
        db.commit()
        return {"draft": draft.model_dump(mode="json"), "task_id": task_id}
    except HTTPException:
        db.rollback()
        raise
