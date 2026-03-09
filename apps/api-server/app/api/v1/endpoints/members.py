from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, pagination_params, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.member.schemas import MemberCreate, MemberListResponse, MemberRead, MemberStatus, MemberUpdate
from app.modules.member.service import create_member, get_member_or_404, list_members, update_member

router = APIRouter(prefix="/members", tags=["members"])


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def create_member_endpoint(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberRead:
    member = create_member(db, payload)
    db.flush()
    write_audit_log(
        db,
        household_id=member.household_id,
        actor=actor,
        action="member.create",
        target_type="member",
        target_id=member.id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(member)
    return MemberRead.model_validate(member)


@router.get("", response_model=MemberListResponse)
def list_members_endpoint(
    household_id: str,
    pagination: tuple[int, int] = Depends(pagination_params),
    status_value: Annotated[MemberStatus | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
) -> MemberListResponse:
    page, page_size = pagination
    members, total = list_members(
        db,
        household_id=household_id,
        page=page,
        page_size=page_size,
        status_value=status_value,
    )
    return MemberListResponse(
        items=[MemberRead.model_validate(member) for member in members],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.patch("/{member_id}", response_model=MemberRead)
def update_member_endpoint(
    member_id: str,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberRead:
    member = get_member_or_404(db, member_id)
    member, changed_fields = update_member(db, member, payload)
    if changed_fields:
        write_audit_log(
            db,
            household_id=member.household_id,
            actor=actor,
            action="member.update",
            target_type="member",
            target_id=member.id,
            result="success",
            details={"changed_fields": changed_fields},
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    db.refresh(member)
    return MemberRead.model_validate(member)
