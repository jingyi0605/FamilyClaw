from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.household.service import get_household_or_404
from app.modules.room.models import Room


def create_room(
    db: Session,
    *,
    household_id: str,
    name: str,
    room_type: str,
    privacy_level: str,
) -> Room:
    get_household_or_404(db, household_id)

    room = Room(
        id=new_uuid(),
        household_id=household_id,
        name=name,
        room_type=room_type,
        privacy_level=privacy_level,
    )
    db.add(room)
    return room


def get_room_or_404(db: Session, room_id: str) -> Room:
    from fastapi import HTTPException, status

    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="room not found",
        )
    return room


def list_rooms(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    room_type: str | None = None,
    privacy_level: str | None = None,
) -> tuple[list[Room], int]:
    get_household_or_404(db, household_id)

    filters = [Room.household_id == household_id]
    if room_type:
        filters.append(Room.room_type == room_type)
    if privacy_level:
        filters.append(Room.privacy_level == privacy_level)

    total = db.scalar(select(func.count()).select_from(Room).where(*filters)) or 0
    statement = (
        select(Room)
        .where(*filters)
        .order_by(Room.created_at.desc(), Room.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rooms = list(db.scalars(statement).all())
    return rooms, total

