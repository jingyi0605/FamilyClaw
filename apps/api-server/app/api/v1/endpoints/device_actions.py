from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.device_action.schemas import DeviceActionExecuteRequest, DeviceActionExecuteResponse
from app.modules.device_action.service import aexecute_device_action

router = APIRouter(prefix="/device-actions", tags=["device-actions"])


def _write_device_action_audit_best_effort(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext,
    payload: DeviceActionExecuteRequest,
    result: str,
    details: dict,
) -> None:
    try:
        write_audit_log(
            db,
            household_id=household_id,
            actor=actor,
            action="device_action.execute",
            target_type="device_action",
            target_id=payload.device_id,
            result=result,
            details={
                **payload.model_dump(mode="json"),
                **details,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()


@router.post("/execute", response_model=DeviceActionExecuteResponse, status_code=status.HTTP_200_OK)
async def execute_device_action_endpoint(
    payload: DeviceActionExecuteRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> DeviceActionExecuteResponse:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        response, audit_context = await aexecute_device_action(db, payload=payload)
        _write_device_action_audit_best_effort(
            db,
            household_id=payload.household_id,
            actor=actor,
            result="success",
            payload=payload,
            details=audit_context.details,
        )
        return response
    except HTTPException as exc:
        db.rollback()
        _write_device_action_audit_best_effort(
            db,
            household_id=payload.household_id,
            actor=actor,
            result="fail",
            payload=payload,
            details={"error": exc.detail},
        )
        raise
    except IntegrityError as exc:
        db.rollback()
        _write_device_action_audit_best_effort(
            db,
            household_id=payload.household_id,
            actor=actor,
            result="fail",
            payload=payload,
            details={"error": "database integrity error"},
        )
        raise translate_integrity_error(exc) from exc
