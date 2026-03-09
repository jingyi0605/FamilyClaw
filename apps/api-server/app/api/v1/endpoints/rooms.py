from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.room.schemas import PrivacyLevel, RoomCreate, RoomListResponse, RoomRead, RoomType
from app.modules.room.service import create_room, list_rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room_endpoint(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> RoomRead:
    room = create_room(
        db,
        household_id=payload.household_id,
        name=payload.name,
        room_type=payload.room_type,
        privacy_level=payload.privacy_level,
    )
    db.flush()
    write_audit_log(
        db,
        household_id=room.household_id,
        actor=actor,
        action="room.create",
        target_type="room",
        target_id=room.id,
        result="success",
        details=payload.model_dump(),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(room)
    return RoomRead.model_validate(room)


@router.get("", response_model=RoomListResponse)
def list_rooms_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    room_type: Annotated[RoomType | None, Query()] = None,
    privacy_level: Annotated[PrivacyLevel | None, Query()] = None,
    db: Session = Depends(get_db),
) -> RoomListResponse:
    page, page_size = pagination
    rooms, total = list_rooms(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        room_type=room_type,
        privacy_level=privacy_level,
    )
    return RoomListResponse(
        items=[RoomRead.model_validate(room) for room in rooms],
        page=page,
        page_size=page_size,
        total=total,
    )

