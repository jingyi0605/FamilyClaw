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
    HomeAssistantConfigRead,
    HomeAssistantConfigUpsert,
    HomeAssistantRoomCandidate,
    HomeAssistantRoomCandidatesResponse,
    HomeAssistantRoomSyncRequest,
    HomeAssistantRoomSyncResponse,
    HomeAssistantSyncFailure,
    HomeAssistantSyncRequest,
    HomeAssistantSyncResponse,
)
from app.modules.ha_integration.service import (
    get_home_assistant_config_view,
    list_home_assistant_room_candidates,
    sync_home_assistant_devices,
    sync_home_assistant_rooms,
    upsert_household_ha_config,
)

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
                "created_rooms": summary.created_rooms,
                "assigned_rooms": summary.assigned_rooms,
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
        created_rooms=summary.created_rooms,
        assigned_rooms=summary.assigned_rooms,
        skipped_entities=summary.skipped_entities,
        failed_entities=summary.failed_entities,
        devices=[DeviceRead.model_validate(device) for device in summary.devices],
        failures=[
            HomeAssistantSyncFailure(entity_id=failure.entity_id, reason=failure.reason)
            for failure in summary.failures
        ],
    )


@router.get("/ha-config/{household_id}", response_model=HomeAssistantConfigRead)
def get_home_assistant_config_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
) -> HomeAssistantConfigRead:
    return HomeAssistantConfigRead.model_validate(get_home_assistant_config_view(db, household_id))


@router.put("/ha-config/{household_id}", response_model=HomeAssistantConfigRead)
def upsert_home_assistant_config_endpoint(
    household_id: str,
    payload: HomeAssistantConfigUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantConfigRead:
    config = upsert_household_ha_config(
        db,
        household_id=household_id,
        base_url=payload.base_url,
        access_token=payload.access_token,
        clear_access_token=payload.clear_access_token,
        sync_rooms_enabled=payload.sync_rooms_enabled,
    )
    write_audit_log(
        db,
        household_id=household_id,
        actor=actor,
        action="device.home_assistant_config.upsert",
        target_type="home_assistant_config",
        target_id=household_id,
        result="success",
        details={
            "base_url": config.base_url,
            "token_configured": bool(config.access_token),
            "sync_rooms_enabled": config.sync_rooms_enabled,
            "clear_access_token": payload.clear_access_token,
        },
    )
    db.commit()
    return HomeAssistantConfigRead.model_validate(get_home_assistant_config_view(db, household_id))


@router.post("/rooms/sync/ha", response_model=HomeAssistantRoomSyncResponse, status_code=status.HTTP_200_OK)
def sync_home_assistant_rooms_endpoint(
    payload: HomeAssistantRoomSyncRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> HomeAssistantRoomSyncResponse:
    try:
        summary = sync_home_assistant_rooms(
            db,
            household_id=payload.household_id,
            room_names=payload.room_names,
        )
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="room.sync.home_assistant",
            target_type="room_sync",
            target_id=payload.household_id,
            result="success",
            details={
                "created_rooms": summary.created_rooms,
                "matched_entities": summary.matched_entities,
                "skipped_entities": summary.skipped_entities,
                "requested_rooms": payload.room_names,
            },
        )
        db.commit()
    except HomeAssistantClientError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return HomeAssistantRoomSyncResponse(
        household_id=summary.household_id,
        created_rooms=summary.created_rooms,
        matched_entities=summary.matched_entities,
        skipped_entities=summary.skipped_entities,
        rooms=[{"id": room.id, "name": room.name} for room in summary.rooms],
    )


@router.get("/rooms/ha-candidates/{household_id}", response_model=HomeAssistantRoomCandidatesResponse)
def list_home_assistant_room_candidates_endpoint(
    household_id: str,
    db: Session = Depends(get_db),
) -> HomeAssistantRoomCandidatesResponse:
    try:
        items = list_home_assistant_room_candidates(db, household_id=household_id)
    except HomeAssistantClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return HomeAssistantRoomCandidatesResponse(
        household_id=household_id,
        items=[
            HomeAssistantRoomCandidate(
                name=item.name,
                entity_count=item.entity_count,
                exists_locally=item.exists_locally,
                can_sync=item.can_sync,
            )
            for item in items
        ],
    )
