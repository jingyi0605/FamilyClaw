from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.reminder.schemas import (
    ReminderAckEventCreate,
    ReminderAckResponse,
    ReminderOverviewRead,
    ReminderSchedulerDispatchResponse,
    ReminderTaskCreate,
    ReminderTaskRead,
    ReminderTaskUpdate,
    ReminderTriggerResponse,
)
from app.modules.reminder.service import (
    acknowledge_run,
    build_reminder_overview,
    create_task,
    delete_task,
    dispatch_due_reminders,
    list_tasks,
    trigger_task,
    update_task,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])
run_router = APIRouter(prefix="/reminder-runs", tags=["reminders"])


@router.get("", response_model=list[ReminderTaskRead])
def list_reminders_endpoint(
    household_id: str,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> list[ReminderTaskRead]:
    return list_tasks(db, household_id=household_id, enabled=enabled)


@router.post("", response_model=ReminderTaskRead, status_code=status.HTTP_201_CREATED)
def create_reminder_endpoint(
    payload: ReminderTaskCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ReminderTaskRead:
    try:
        result = create_task(db, payload)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="reminder.create",
            target_type="reminder_task",
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


@router.patch("/{reminder_id}", response_model=ReminderTaskRead)
def update_reminder_endpoint(
    reminder_id: str,
    payload: ReminderTaskUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ReminderTaskRead:
    try:
        result = update_task(db, reminder_id, payload)
        write_audit_log(
            db,
            household_id=result.household_id,
            actor=actor,
            action="reminder.update",
            target_type="reminder_task",
            target_id=reminder_id,
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


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder_endpoint(
    reminder_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> Response:
    try:
        result = delete_task(db, task_id=reminder_id, updated_by=actor.actor_id or actor.actor_type)
        write_audit_log(
            db,
            household_id=result.household_id,
            actor=actor,
            action="reminder.delete",
            target_type="reminder_task",
            target_id=reminder_id,
            result="success",
            details={"soft_deleted": True},
        )
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/overview", response_model=ReminderOverviewRead)
def reminder_overview_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> ReminderOverviewRead:
    return build_reminder_overview(db, household_id=household_id)


@router.post("/{reminder_id}/trigger", response_model=ReminderTriggerResponse)
def trigger_reminder_endpoint(
    reminder_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ReminderTriggerResponse:
    try:
        result = trigger_task(db, task_id=reminder_id, trigger_reason="manual")
        write_audit_log(
            db,
            household_id=result.run.household_id,
            actor=actor,
            action="reminder.trigger",
            target_type="reminder_run",
            target_id=result.run.id,
            result="success",
            details={"task_id": reminder_id, "delivery_attempt_count": len(result.delivery_attempts)},
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/scheduler/dispatch", response_model=ReminderSchedulerDispatchResponse)
def dispatch_reminder_scheduler_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ReminderSchedulerDispatchResponse:
    try:
        result = dispatch_due_reminders(db, household_id=household_id)
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="reminder.scheduler.dispatch",
            target_type="reminder_scheduler",
            target_id=household_id,
            result="success",
            details={
                "created_run_count": len(result.created_runs),
                "escalated_run_count": len(result.escalated_runs),
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


@run_router.post("/{run_id}/ack", response_model=ReminderAckResponse)
def acknowledge_reminder_run_endpoint(
    run_id: str,
    payload: ReminderAckEventCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> ReminderAckResponse:
    if payload.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path run_id 与 payload run_id 不一致")
    try:
        result = acknowledge_run(db, payload=payload)
        write_audit_log(
            db,
            household_id=result.run.household_id,
            actor=actor,
            action="reminder_run.ack",
            target_type="reminder_run",
            target_id=run_id,
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
