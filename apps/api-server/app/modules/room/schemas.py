from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoomType = Literal["living_room", "bedroom", "study", "entrance", "kitchen", "bathroom", "gym", "garage"]
PrivacyLevel = Literal["public", "private", "sensitive"]


class RoomCreate(BaseModel):
    household_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    room_type: RoomType
    privacy_level: PrivacyLevel


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    name: str
    room_type: RoomType
    privacy_level: PrivacyLevel
    created_at: str


class RoomListResponse(BaseModel):
    items: list[RoomRead]
    page: int
    page_size: int
    total: int

