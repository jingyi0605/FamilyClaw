from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.device.models import Device
from app.modules.device.schemas import DeviceUpdate
from app.modules.household.service import get_household_or_404
from app.modules.room.models import Room


def get_device_or_404(db: Session, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device not found",
        )
    return device


def _validate_room_in_household(db: Session, *, room_id: str | None, household_id: str) -> None:
    if room_id is None:
        return

    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room not found",
        )
    if room.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="room must belong to the same household",
        )


def list_devices(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    room_id: str | None = None,
    device_type: str | None = None,
    status_value: str | None = None,
) -> tuple[list[Device], int]:
    get_household_or_404(db, household_id)

    filters = [Device.household_id == household_id]
    if room_id:
        filters.append(Device.room_id == room_id)
    if device_type:
        filters.append(Device.device_type == device_type)
    if status_value:
        filters.append(Device.status == status_value)

    total = db.scalar(select(func.count()).select_from(Device).where(*filters)) or 0
    statement = (
        select(Device)
        .where(*filters)
        .order_by(Device.updated_at.desc(), Device.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    devices = list(db.scalars(statement).all())
    return devices, total


def update_device(db: Session, device: Device, payload: DeviceUpdate) -> tuple[Device, dict]:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return device, {}

    if "room_id" in update_data:
        _validate_room_in_household(
            db,
            room_id=update_data["room_id"],
            household_id=device.household_id,
        )

    if "controllable" in update_data:
        update_data["controllable"] = 1 if update_data["controllable"] else 0

    if "voice_auto_takeover_enabled" in update_data:
        if device.device_type != "speaker" or device.vendor != "xiaomi":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voice takeover settings only support xiaomi speaker devices",
            )
        update_data["voice_auto_takeover_enabled"] = 1 if update_data["voice_auto_takeover_enabled"] else 0

    if "voiceprint_identity_enabled" in update_data:
        if device.device_type != "speaker" or device.vendor != "xiaomi":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voiceprint settings only support xiaomi speaker devices",
            )
        update_data["voiceprint_identity_enabled"] = 1 if update_data["voiceprint_identity_enabled"] else 0

    if "voice_takeover_prefixes" in update_data:
        if device.device_type != "speaker" or device.vendor != "xiaomi":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="voice takeover settings only support xiaomi speaker devices",
            )

    for field_name, field_value in update_data.items():
        setattr(device, field_name, field_value)

    db.add(device)
    return device, update_data

