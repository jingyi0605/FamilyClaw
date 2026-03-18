from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.region.schemas import (
    HouseholdCoordinateOverrideRead,
    HouseholdCoordinateUpdate,
    HouseholdRegionRead,
    RegionSelection,
)

HouseholdSetupLifecycleStatus = Literal["pending", "in_progress", "completed", "blocked"]
HouseholdSetupStepCode = Literal[
    "family_profile",
    "first_member",
    "provider_setup",
    "first_butler_agent",
    "finish",
]


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)
    locale: str = Field(min_length=1, max_length=32)
    region_selection: RegionSelection | None = None


class HouseholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    city: str | None
    timezone: str
    locale: str
    status: str
    region: HouseholdRegionRead
    coordinate_override: HouseholdCoordinateOverrideRead | None = None
    created_at: str
    updated_at: str


class HouseholdUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    locale: str | None = Field(default=None, min_length=1, max_length=32)
    region_selection: RegionSelection | None = None


class HouseholdListResponse(BaseModel):
    items: list[HouseholdRead]
    page: int
    page_size: int
    total: int


class HouseholdCoordinateUpsert(HouseholdCoordinateUpdate):
    pass


class HouseholdSetupStatusRead(BaseModel):
    household_id: str
    status: HouseholdSetupLifecycleStatus
    current_step: HouseholdSetupStepCode
    completed_steps: list[HouseholdSetupStepCode]
    missing_requirements: list[HouseholdSetupStepCode]
    is_required: bool
    resume_token: str | None = None
    updated_at: str
