from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.device.schemas import DeviceListResponse, DeviceRead, DeviceStatus, DeviceType, DeviceUpdate
from app.modules.device.service import get_device_or_404, list_devices, update_device
from app.modules.ha_integration.client import HomeAssistantClientError
from app.modules.ha_integration.schemas import (
    HomeAssistantSyncFailure,
    HomeAssistantSyncRequest,
    HomeAssistantSyncResponse,
)
from app.modules.ha_integration.service import sync_home_assistant_devices

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=DeviceListResponse)
def list_devices_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    room_id: str | None = None,
    device_type: Annotated[DeviceType | None, Query()] = None,
    status_value: Annotated[DeviceStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
) -> DeviceListResponse:
    page, page_size = pagination
    devices, total = list_devices(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        room_id=room_id,
        device_type=device_type,
        status_value=status_value,
    )
    return DeviceListResponse(
        items=[DeviceRead.model_validate(device) for device in devices],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/{device_id}", response_model=DeviceRead)
def update_device_endpoint(
    device_id: str,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> DeviceRead:
    device = get_device_or_404(db, device_id)
    device, changed_fields = update_device(db, device, payload)
    if changed_fields:
        write_audit_log(
            db,
            household_id=device.household_id,
            actor=actor,
            action="device.update",
            target_type="device",
            target_id=device.id,
            result="success",
            details={"changed_fields": changed_fields},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(device)
    return DeviceRead.model_validate(device)


@router.post("/sync/ha", response_model=HomeAssistantSyncResponse, status_code=status.HTTP_200_OK)
def sync_home_assistant_devices_endpoint(
    payload: HomeAssistantSyncRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantSyncResponse:
    try:
        summary = sync_home_assistant_devices(
            db,
            household_id=payload.household_id,
        )
        audit_result = "success" if summary.failed_entities == 0 else "fail"
        write_audit_log(
            db,
            household_id=summary.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=summary.household_id,
            result=audit_result,
            details={
                "created_devices": summary.created_devices,
                "updated_devices": summary.updated_devices,
                "created_bindings": summary.created_bindings,
                "skipped_entities": summary.skipped_entities,
                "failed_entities": summary.failed_entities,
            },
        )
        db.commit()
    except HomeAssistantClientError as exc:
        db.rollback()
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=payload.household_id,
            result="fail",
            details={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="device.sync.home_assistant",
            target_type="device_sync",
            target_id=payload.household_id,
            result="fail",
            details={"error": "database integrity error"},
        )
        db.commit()
        raise translate_integrity_error(exc) from exc

    return HomeAssistantSyncResponse(
        household_id=summary.household_id,
        created_devices=summary.created_devices,
        updated_devices=summary.updated_devices,
        created_bindings=summary.created_bindings,
        skipped_entities=summary.skipped_entities,
        failed_entities=summary.failed_entities,
        devices=[DeviceRead.model_validate(device) for device in summary.devices],
        failures=[
            HomeAssistantSyncFailure(entity_id=failure.entity_id, reason=failure.reason)
            for failure in summary.failures
        ],
    )
