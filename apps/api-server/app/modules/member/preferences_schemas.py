from typing import Any

from pydantic import BaseModel, Field


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


class MemberGuideStatusRead(BaseModel):
    member_id: str
    user_app_guide_version: int | None = None
    updated_at: str | None = None


class MemberGuideStatusUpsert(BaseModel):
    user_app_guide_version: int = Field(ge=1)

