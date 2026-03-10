from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, require_admin_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.member.preferences_schemas import MemberPreferenceRead, MemberPreferenceUpsert
from app.modules.member.preferences_service import get_member_preferences_or_default, upsert_member_preferences

router = APIRouter(prefix="/member-preferences", tags=["member-preferences"])


@router.put("/{member_id}", response_model=MemberPreferenceRead)
def upsert_member_preferences_endpoint(
    member_id: str,
    payload: MemberPreferenceUpsert,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_admin_actor),
) -> MemberPreferenceRead:
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
    _actor: ActorContext = Depends(require_admin_actor),
) -> MemberPreferenceRead:
    return get_member_preferences_or_default(db, member_id)

