from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.permission.schemas import (
    MemberPermissionListResponse,
    MemberPermissionRead,
    MemberPermissionReplaceRequest,
)
from app.modules.permission.service import list_member_permissions, replace_member_permissions

router = APIRouter(prefix="/member-permissions", tags=["member-permissions"])


@router.put("/{member_id}", response_model=MemberPermissionListResponse)
def replace_member_permissions_endpoint(
    member_id: str,
    payload: MemberPermissionReplaceRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberPermissionListResponse:
    member, permissions = replace_member_permissions(db, member_id=member_id, payload=payload)
    db.flush()
    write_audit_log(
        db,
        household_id=member.household_id,
        actor=actor,
        action="member_permission.replace",
        target_type="member_permission",
        target_id=member_id,
        result="success",
        details={"rule_count": len(payload.rules)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    member, permissions = list_member_permissions(db, member_id)
    return MemberPermissionListResponse(
        member_id=member.id,
        household_id=member.household_id,
        items=[MemberPermissionRead.model_validate(item) for item in permissions],
    )


@router.get("/{member_id}", response_model=MemberPermissionListResponse)
def get_member_permissions_endpoint(
    member_id: str,
    db: Session = Depends(get_db),
    _actor: ActorContext = Depends(require_admin_actor),
) -> MemberPermissionListResponse:
    member, permissions = list_member_permissions(db, member_id)
    return MemberPermissionListResponse(
        member_id=member.id,
        household_id=member.household_id,
        items=[MemberPermissionRead.model_validate(item) for item in permissions],
    )
