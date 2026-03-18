from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RegionAdminLevel = Literal["province", "city", "district"]
HouseholdRegionStatus = Literal["configured", "unconfigured", "provider_unavailable"]
CoordinatePrecision = Literal["country", "province", "city", "district", "point"]
RegionCoordinateSource = Literal["provider_builtin", "provider_external"]
HouseholdCoordinateSource = Literal["manual_browser", "manual_app", "manual_admin"]
ResolvedCoordinateSourceType = Literal["household_exact", "region_representative", "unavailable"]


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
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_precision: CoordinatePrecision | None = None
    coordinate_source: RegionCoordinateSource | None = None
    coordinate_updated_at: str | None = None

    @model_validator(mode="after")
    def validate_coordinate_fields(self) -> "RegionNodeRead":
        if self.latitude is None and self.longitude is None:
            if self.coordinate_precision is not None or self.coordinate_source is not None:
                raise ValueError("地区坐标精度和来源不能脱离经纬度单独出现")
            return self
        if self.latitude is None or self.longitude is None:
            raise ValueError("地区坐标必须同时提供经纬度")
        if self.coordinate_precision is None or self.coordinate_source is None:
            raise ValueError("地区坐标存在时必须同时提供精度和来源")
        return self


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
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_precision: CoordinatePrecision | None = None
    coordinate_source: RegionCoordinateSource | None = None
    coordinate_updated_at: str | None = None

    @model_validator(mode="after")
    def validate_coordinate_fields(self) -> "RegionCatalogImportItem":
        if self.latitude is None and self.longitude is None:
            if self.coordinate_precision is not None or self.coordinate_source is not None:
                raise ValueError("地区坐标精度和来源不能脱离经纬度单独出现")
            return self
        if self.latitude is None or self.longitude is None:
            raise ValueError("地区坐标必须同时提供经纬度")
        if self.coordinate_precision is None or self.coordinate_source is None:
            raise ValueError("地区坐标存在时必须同时提供精度和来源")
        return self


class HouseholdCoordinateOverrideRead(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_source: HouseholdCoordinateSource
    coordinate_precision: CoordinatePrecision
    coordinate_updated_at: str


class HouseholdCoordinateUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_source: HouseholdCoordinateSource
    confirmed: bool = False


class ResolvedHouseholdCoordinateRead(BaseModel):
    available: bool
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    source_type: ResolvedCoordinateSourceType
    precision: CoordinatePrecision | None = None
    provider_code: str | None = None
    region_code: str | None = None
    region_path: list[str] = Field(default_factory=list)
    updated_at: str | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> "ResolvedHouseholdCoordinateRead":
        if self.available:
            if self.latitude is None or self.longitude is None:
                raise ValueError("可用坐标必须同时提供经纬度")
            if self.source_type == "unavailable":
                raise ValueError("可用坐标不能标记为 unavailable")
        else:
            if self.source_type != "unavailable":
                raise ValueError("不可用坐标必须标记为 unavailable")
            if self.latitude is not None or self.longitude is not None:
                raise ValueError("不可用坐标不能携带经纬度")
        return self


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
    coordinate: ResolvedHouseholdCoordinateRead = Field(
        default_factory=lambda: ResolvedHouseholdCoordinateRead(
            available=False,
            source_type="unavailable",
        )
    )


class HouseholdRegionErrorRead(HouseholdRegionRead):
    error_code: str | None = None
    detail: str | None = None
