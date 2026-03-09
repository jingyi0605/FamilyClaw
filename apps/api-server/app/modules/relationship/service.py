from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.relationship.models import MemberRelationship
from app.modules.relationship.schemas import MemberRelationshipCreate


def _ensure_household_exists(db: Session, household_id: str) -> None:
    household = db.get(Household, household_id)
    if household is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )


def _get_member_in_household_or_400(db: Session, member_id: str, household_id: str, field_name: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} not found",
        )
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must belong to the same household",
        )
    return member


def create_relationship(db: Session, payload: MemberRelationshipCreate) -> MemberRelationship:
    _ensure_household_exists(db, payload.household_id)
    if payload.source_member_id == payload.target_member_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source member and target member must be different",
        )

    _get_member_in_household_or_400(
        db,
        payload.source_member_id,
        payload.household_id,
        "source member",
    )
    _get_member_in_household_or_400(
        db,
        payload.target_member_id,
        payload.household_id,
        "target member",
    )

    relationship = MemberRelationship(
        id=new_uuid(),
        household_id=payload.household_id,
        source_member_id=payload.source_member_id,
        target_member_id=payload.target_member_id,
        relation_type=payload.relation_type,
        visibility_scope=payload.visibility_scope,
        delegation_scope=payload.delegation_scope,
    )
    db.add(relationship)
    return relationship


def list_relationships(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    source_member_id: str | None = None,
    target_member_id: str | None = None,
    relation_type: str | None = None,
) -> tuple[list[MemberRelationship], int]:
    _ensure_household_exists(db, household_id)

    filters = [MemberRelationship.household_id == household_id]
    if source_member_id:
        filters.append(MemberRelationship.source_member_id == source_member_id)
    if target_member_id:
        filters.append(MemberRelationship.target_member_id == target_member_id)
    if relation_type:
        filters.append(MemberRelationship.relation_type == relation_type)

    total = db.scalar(select(func.count()).select_from(MemberRelationship).where(*filters)) or 0
    statement = (
        select(MemberRelationship)
        .where(*filters)
        .order_by(MemberRelationship.created_at.desc(), MemberRelationship.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.scalars(statement).all())
    return items, total

