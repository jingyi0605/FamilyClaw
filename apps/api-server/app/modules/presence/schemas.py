from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PresenceSourceType = Literal["lock", "camera", "bluetooth", "sensor", "voice"]
PresenceStatus = Literal["home", "away", "unknown"]


class PresenceEventCreate(BaseModel):
    household_id: str = Field(min_length=1)
    member_id: str | None = None
    room_id: str | None = None
    source_type: PresenceSourceType
    source_ref: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0, le=1)
    payload: Any | None = None
    occurred_at: str = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        normalized = value.replace("Z", "+00:00")
        try:
            from datetime import datetime

            datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("occurred_at must be a valid ISO8601 datetime") from exc
        return value


class PresenceEventWriteResponse(BaseModel):
    event_id: str
    accepted: bool
    snapshot_updated: bool
    cache_refreshed: bool
    member_id: str | None = None
    household_id: str
    status: PresenceStatus | None = None
    current_room_id: str | None = None
    confidence: int | None = None
