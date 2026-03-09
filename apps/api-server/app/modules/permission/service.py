from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.member.models import Member
from app.modules.permission.models import MemberPermission
from app.modules.permission.schemas import MemberPermissionReplaceRequest


def get_member_or_404(db: Session, member_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    return member


def replace_member_permissions(
    db: Session,
    *,
    member_id: str,
    payload: MemberPermissionReplaceRequest,
) -> tuple[Member, list[MemberPermission]]:
    member = get_member_or_404(db, member_id)
    db.execute(delete(MemberPermission).where(MemberPermission.member_id == member_id))

    permissions: list[MemberPermission] = []
    for rule in payload.rules:
        permission = MemberPermission(
            id=new_uuid(),
            household_id=member.household_id,
            member_id=member_id,
            resource_type=rule.resource_type,
            resource_scope=rule.resource_scope,
            action=rule.action,
            effect=rule.effect,
        )
        db.add(permission)
        permissions.append(permission)

    return member, permissions


def list_member_permissions(db: Session, member_id: str) -> tuple[Member, list[MemberPermission]]:
    member = get_member_or_404(db, member_id)
    statement = (
        select(MemberPermission)
        .where(MemberPermission.member_id == member_id)
        .order_by(
            MemberPermission.resource_type.asc(),
            MemberPermission.action.asc(),
            MemberPermission.id.asc(),
        )
    )
    permissions = list(db.scalars(statement).all())
    return member, permissions
