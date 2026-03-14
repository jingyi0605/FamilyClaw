from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RegionAdminLevel = Literal["province", "city", "district"]
HouseholdRegionStatus = Literal["configured", "unconfigured", "provider_unavailable"]


class RegionSelection(BaseModel):
    provider_code: str = Field(min_length=1, max_length=50)
    country_code: str = Field(min_length=1, max_length=16)
    region_code: str = Field(min_length=1, max_length=32)


class RegionNodeRefRead(BaseModel):
    code: str
    name: str


class RegionNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_code: str
    country_code: str
    region_code: str
    parent_region_code: str | None
    admin_level: RegionAdminLevel
    name: str
    full_name: str
    path_codes: list[str]
    path_names: list[str]
    timezone: str | None = None
    source_version: str | None = None


class RegionCatalogImportItem(BaseModel):
    region_code: str = Field(min_length=1, max_length=32)
    parent_region_code: str | None = Field(default=None, max_length=32)
    admin_level: RegionAdminLevel
    name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    path_codes: list[str] = Field(min_length=1)
    path_names: list[str] = Field(min_length=1)
    timezone: str | None = Field(default="Asia/Shanghai", max_length=64)
    enabled: bool = True
    extra: dict[str, Any] | None = None


class HouseholdRegionRead(BaseModel):
    status: HouseholdRegionStatus
    provider_code: str | None = None
    country_code: str | None = None
    region_code: str | None = None
    admin_level: RegionAdminLevel | None = None
    province: RegionNodeRefRead | None = None
    city: RegionNodeRefRead | None = None
    district: RegionNodeRefRead | None = None
    display_name: str | None = None
    timezone: str | None = None


class HouseholdRegionErrorRead(HouseholdRegionRead):
    error_code: str | None = None
    detail: str | None = None
