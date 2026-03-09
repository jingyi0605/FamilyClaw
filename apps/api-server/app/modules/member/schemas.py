from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemberRole = Literal["admin", "adult", "child", "elder", "guest"]
MemberAgeGroup = Literal["toddler", "child", "teen", "adult", "elder"]
MemberStatus = Literal["active", "inactive"]


class MemberCreate(BaseModel):
    household_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    nickname: str | None = Field(default=None, max_length=100)
    role: MemberRole
    age_group: MemberAgeGroup | None = None
    birthday: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    guardian_member_id: str | None = None


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    nickname: str | None = Field(default=None, max_length=100)
    role: MemberRole | None = None
    age_group: MemberAgeGroup | None = None
    birthday: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    status: MemberStatus | None = None
    guardian_member_id: str | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    name: str
    nickname: str | None
    role: MemberRole
    age_group: MemberAgeGroup | None
    birthday: date | None
    phone: str | None
    status: MemberStatus
    guardian_member_id: str | None
    created_at: str
    updated_at: str


class MemberListResponse(BaseModel):
    items: list[MemberRead]
    page: int
    page_size: int
    total: int

