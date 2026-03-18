from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    ActorContext,
    ensure_actor_can_access_household,
    pagination_params,
    require_admin_actor,
    require_bound_member_actor,
)
from app.api.errors import translate_integrity_error
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import utc_now_iso
from app.modules.audit.service import write_audit_log
from app.modules.device.schemas import (
    DeviceActionLogListResponse,
    DeviceDetailViewRead,
    DeviceEntityFavoriteUpdateRequest,
    DeviceEntityListResponse,
    DeviceListResponse,
    DeviceRead,
    DeviceStatus,
    DeviceType,
    DeviceUpdate,
)
from app.modules.device.service import (
    delete_device,
    disable_device,
    get_device_or_404,
    get_device_detail_view,
    list_device_action_logs,
    list_device_entities,
    list_devices,
    set_device_entity_favorite,
    update_device,
)
from app.modules.household.service import get_household_or_404

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=DeviceListResponse)
def list_devices_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    room_id: str | None = None,
    device_type: Annotated[DeviceType | None, Query()] = None,
    status_value: Annotated[DeviceStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceListResponse:
    ensure_actor_can_access_household(actor, household_id)
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


@router.get("/{device_id}/detail-view", response_model=DeviceDetailViewRead)
def get_device_detail_view_endpoint(
    device_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceDetailViewRead:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    return get_device_detail_view(db, device_id=device_id)


@router.get("/{device_id}/entities", response_model=DeviceEntityListResponse)
def list_device_entities_endpoint(
    device_id: str,
    view: Annotated[Literal["favorites", "all"], Query()] = "favorites",
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceEntityListResponse:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    return list_device_entities(db, device_id=device_id, view=view)


@router.put("/{device_id}/entities/{entity_id:path}/favorite", response_model=DeviceEntityListResponse)
def update_device_entity_favorite_endpoint(
    device_id: str,
    entity_id: str,
    payload: DeviceEntityFavoriteUpdateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceEntityListResponse:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    result = set_device_entity_favorite(
        db,
        device_id=device_id,
        entity_id=entity_id,
        favorite=payload.favorite,
        created_by=actor.actor_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    return result


@router.post("/{device_id}/disable", response_model=DeviceRead)
def disable_device_endpoint(
    device_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> DeviceRead:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    device, changed = disable_device(db, device)
    if changed:
        write_audit_log(
            db,
            household_id=device.household_id,
            actor=actor,
            action="device.disable",
            target_type="device",
            target_id=device.id,
            result="success",
            details={"status": device.status},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
    db.refresh(device)
    return DeviceRead.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device_endpoint(
    device_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> None:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    device_snapshot = {
        "device_id": device.id,
        "name": device.name,
        "status": device.status,
        "device_type": device.device_type,
    }
    write_audit_log(
        db,
        household_id=device.household_id,
        actor=actor,
        action="device.delete",
        target_type="device",
        target_id=device.id,
        result="success",
        details=device_snapshot,
    )
    delete_device(db, device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/{device_id}/action-logs", response_model=DeviceActionLogListResponse)
def list_device_action_logs_endpoint(
    device_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> DeviceActionLogListResponse:
    device = get_device_or_404(db, device_id)
    ensure_actor_can_access_household(actor, device.household_id)
    page, page_size = pagination
    return list_device_action_logs(db, device_id=device_id, page=page, page_size=page_size)

