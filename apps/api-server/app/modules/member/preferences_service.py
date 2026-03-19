from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json
from app.modules.member.models import Member, MemberPreference
from app.modules.member.preferences_schemas import (
    MemberGuideStatusRead,
    MemberGuideStatusUpsert,
    MemberPreferenceRead,
    MemberPreferenceUpsert,
)


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
    preference = get_or_create_member_preference(db, member_id=member_id)

    preference.preferred_name = payload.preferred_name
    preference.light_preference = dump_json(payload.light_preference)
    preference.climate_preference = dump_json(payload.climate_preference)
    preference.content_preference = dump_json(payload.content_preference)
    preference.reminder_channel_preference = dump_json(payload.reminder_channel_preference)
    preference.sleep_schedule = dump_json(payload.sleep_schedule)
    preference.birthday_is_lunar = payload.birthday_is_lunar
    db.add(preference)
    return member, preference


def get_or_create_member_preference(db: Session, *, member_id: str) -> MemberPreference:
    preference = db.get(MemberPreference, member_id)
    if preference is None:
        preference = MemberPreference(member_id=member_id)
    return preference


def get_member_guide_status_or_default(db: Session, member_id: str) -> MemberGuideStatusRead:
    member = get_member_or_404(db, member_id)
    preference = db.get(MemberPreference, member_id)
    if preference is None:
        return MemberGuideStatusRead(
            member_id=member.id,
            user_app_guide_version=None,
            updated_at=None,
        )

    return MemberGuideStatusRead(
        member_id=preference.member_id,
        user_app_guide_version=preference.user_app_guide_version,
        updated_at=preference.updated_at,
    )


def upsert_member_guide_status(
    db: Session,
    *,
    member_id: str,
    payload: MemberGuideStatusUpsert,
) -> tuple[Member, MemberPreference]:
    member = get_member_or_404(db, member_id)
    preference = get_or_create_member_preference(db, member_id=member_id)
    current_version = preference.user_app_guide_version
    next_version = payload.user_app_guide_version

    if current_version is not None and next_version < current_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="guide version cannot move backward",
        )

    preference.user_app_guide_version = next_version
    db.add(preference)
    return member, preference


def get_member_preferences_or_default(db: Session, member_id: str) -> MemberPreferenceRead:
    member = get_member_or_404(db, member_id)
    preference = db.get(MemberPreference, member_id)
    if preference is None:
        return MemberPreferenceRead(
            member_id=member.id,
            preferred_name=None,
            light_preference=None,
            climate_preference=None,
            content_preference=None,
            reminder_channel_preference=None,
            sleep_schedule=None,
            birthday_is_lunar=False,
            updated_at=None,
        )

    return MemberPreferenceRead(
        member_id=preference.member_id,
        preferred_name=preference.preferred_name,
        light_preference=load_json(preference.light_preference),
        climate_preference=load_json(preference.climate_preference),
        content_preference=load_json(preference.content_preference),
        reminder_channel_preference=load_json(preference.reminder_channel_preference),
        sleep_schedule=load_json(preference.sleep_schedule),
        birthday_is_lunar=preference.birthday_is_lunar,
        updated_at=preference.updated_at,
    )

