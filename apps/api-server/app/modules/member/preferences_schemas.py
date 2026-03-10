from typing import Any

from pydantic import BaseModel


class MemberPreferenceUpsert(BaseModel):
    preferred_name: str | None = None
    light_preference: Any | None = None
    climate_preference: Any | None = None
    content_preference: Any | None = None
    reminder_channel_preference: Any | None = None
    sleep_schedule: Any | None = None
    birthday_is_lunar: bool = False


class MemberPreferenceRead(MemberPreferenceUpsert):
    member_id: str
    updated_at: str | None = None

