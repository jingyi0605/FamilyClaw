from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
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
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.room.schemas import PrivacyLevel, RoomCreate, RoomListResponse, RoomRead, RoomType, RoomUpdate
from app.modules.room.service import create_room, delete_room, get_room_or_404, list_rooms, update_room

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room_endpoint(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> RoomRead:
    ensure_actor_can_access_household(actor, payload.household_id)
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
    actor: ActorContext = Depends(require_bound_member_actor),
) -> RoomListResponse:
    ensure_actor_can_access_household(actor, household_id)
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


@router.patch("/{room_id}", response_model=RoomRead)
def update_room_endpoint(
    room_id: str,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> RoomRead:
    room = get_room_or_404(db, room_id)
    ensure_actor_can_access_household(actor, room.household_id)
    room, changed_fields = update_room(db, room, payload)
    if changed_fields:
        write_audit_log(
            db,
            household_id=room.household_id,
            actor=actor,
            action="room.update",
            target_type="room",
            target_id=room.id,
            result="success",
            details={"changed_fields": changed_fields},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(room)
    return RoomRead.model_validate(room)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room_endpoint(
    room_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> Response:
    room = get_room_or_404(db, room_id)
    ensure_actor_can_access_household(actor, room.household_id)
    details = delete_room(db, room)
    write_audit_log(
        db,
        household_id=room.household_id,
        actor=actor,
        action="room.delete",
        target_type="room",
        target_id=room.id,
        result="success",
        details=details,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

