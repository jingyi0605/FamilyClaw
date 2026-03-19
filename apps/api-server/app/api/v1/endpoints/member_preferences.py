from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_admin_actor, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.member.service import get_member_or_404
from app.modules.member.preferences_schemas import (
    MemberGuideStatusRead,
    MemberGuideStatusUpsert,
    MemberPreferenceRead,
    MemberPreferenceUpsert,
)
from app.modules.member.preferences_service import (
    get_member_guide_status_or_default,
    get_member_preferences_or_default,
    upsert_member_guide_status,
    upsert_member_preferences,
)

router = APIRouter(prefix="/member-preferences", tags=["member-preferences"])


def ensure_actor_can_write_member_guide_status(actor: ActorContext, member_id: str) -> None:
    if actor.account_type == "system":
        return

    if actor.member_id != member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot update another member guide status",
        )


@router.put("/{member_id}", response_model=MemberPreferenceRead)
def upsert_member_preferences_endpoint(
    member_id: str,
    payload: MemberPreferenceUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberPreferenceRead:
    member = get_member_or_404(db, member_id)
    ensure_actor_can_access_household(actor, member.household_id)
    member, _preference = upsert_member_preferences(db, member_id=member_id, payload=payload)
    write_audit_log(
        db,
        household_id=member.household_id,
        actor=actor,
        action="member_preference.upsert",
        target_type="member_preference",
        target_id=member_id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    return get_member_preferences_or_default(db, member_id)


@router.get("/{member_id}", response_model=MemberPreferenceRead)
def get_member_preferences_endpoint(
    member_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberPreferenceRead:
    member = get_member_or_404(db, member_id)
    ensure_actor_can_access_household(actor, member.household_id)
    return get_member_preferences_or_default(db, member_id)


@router.get("/{member_id}/guide-status", response_model=MemberGuideStatusRead)
def get_member_guide_status_endpoint(
    member_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberGuideStatusRead:
    member = get_member_or_404(db, member_id)
    ensure_actor_can_access_household(actor, member.household_id)
    return get_member_guide_status_or_default(db, member_id)


@router.put("/{member_id}/guide-status", response_model=MemberGuideStatusRead)
def upsert_member_guide_status_endpoint(
    member_id: str,
    payload: MemberGuideStatusUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> MemberGuideStatusRead:
    member = get_member_or_404(db, member_id)
    ensure_actor_can_access_household(actor, member.household_id)
    ensure_actor_can_write_member_guide_status(actor, member_id)
    member, _preference = upsert_member_guide_status(db, member_id=member_id, payload=payload)
    write_audit_log(
        db,
        household_id=member.household_id,
        actor=actor,
        action="member_preference.guide_status_upsert",
        target_type="member_preference",
        target_id=member_id,
        result="success",
        details=payload.model_dump(mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc

    return get_member_guide_status_or_default(db, member_id)

