from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json
from app.modules.member.models import Member, MemberPreference
from app.modules.member.preferences_schemas import MemberPreferenceRead, MemberPreferenceUpsert


def get_member_or_404(db: Session, member_id: str) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    return member


def upsert_member_preferences(
    db: Session,
    *,
    member_id: str,
    payload: MemberPreferenceUpsert,
) -> tuple[Member, MemberPreference]:
    member = get_member_or_404(db, member_id)
    preference = db.get(MemberPreference, member_id)
    if preference is None:
        preference = MemberPreference(member_id=member_id)

    preference.preferred_name = payload.preferred_name
    preference.light_preference = dump_json(payload.light_preference)
    preference.climate_preference = dump_json(payload.climate_preference)
    preference.content_preference = dump_json(payload.content_preference)
    preference.reminder_channel_preference = dump_json(payload.reminder_channel_preference)
    preference.sleep_schedule = dump_json(payload.sleep_schedule)
    db.add(preference)
    return member, preference


def get_member_preferences_or_404(db: Session, member_id: str) -> MemberPreferenceRead:
    get_member_or_404(db, member_id)
    preference = db.get(MemberPreference, member_id)
    if preference is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member preferences not found",
        )

    return MemberPreferenceRead(
        member_id=preference.member_id,
        preferred_name=preference.preferred_name,
        light_preference=load_json(preference.light_preference),
        climate_preference=load_json(preference.climate_preference),
        content_preference=load_json(preference.content_preference),
        reminder_channel_preference=load_json(preference.reminder_channel_preference),
        sleep_schedule=load_json(preference.sleep_schedule),
        updated_at=preference.updated_at,
    )

