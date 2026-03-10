from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.member.schemas import MemberCreate, MemberUpdate


def _ensure_household_exists(db: Session, household_id: str) -> None:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )


def _validate_guardian(
    db: Session,
    *,
    household_id: str,
    guardian_member_id: str | None,
    member_id: str | None = None,
) -> None:
    if guardian_member_id is None:
        return

    if member_id is not None and guardian_member_id == member_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guardian member cannot be self",
        )

    guardian = db.get(Member, guardian_member_id)
    if guardian is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guardian member not found",
        )

    if guardian.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guardian member must belong to the same household",
        )


def create_member(db: Session, payload: MemberCreate) -> Member:
    _ensure_household_exists(db, payload.household_id)
    _validate_guardian(
        db,
        household_id=payload.household_id,
        guardian_member_id=payload.guardian_member_id,
    )

    member = Member(
        id=new_uuid(),
        household_id=payload.household_id,
        name=payload.name,
        nickname=payload.nickname,
        gender=payload.gender,
        role=payload.role,
        age_group=payload.age_group,
        birthday=payload.birthday.isoformat() if payload.birthday else None,
        phone=payload.phone,
        status="active",
        guardian_member_id=payload.guardian_member_id,
    )
    db.add(member)
    return member


def get_member_or_404(db: Session, member_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    return member


def list_members(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    status_value: str | None = None,
) -> tuple[list[Member], int]:
    _ensure_household_exists(db, household_id)

    filters = [Member.household_id == household_id]
    if status_value:
        filters.append(Member.status == status_value)

    total = db.scalar(select(func.count()).select_from(Member).where(*filters)) or 0
    statement = (
        select(Member)
        .where(*filters)
        .order_by(Member.created_at.desc(), Member.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    members = list(db.scalars(statement).all())
    return members, total


def update_member(db: Session, member: Member, payload: MemberUpdate) -> tuple[Member, dict]:
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return member, {}

    if "guardian_member_id" in update_data:
        _validate_guardian(
            db,
            household_id=member.household_id,
            guardian_member_id=update_data["guardian_member_id"],
            member_id=member.id,
        )

    if "birthday" in update_data:
        update_data["birthday"] = (
            update_data["birthday"].isoformat() if update_data["birthday"] else None
        )

    for field_name, field_value in update_data.items():
        setattr(member, field_name, field_value)

    db.add(member)
    return member, update_data
