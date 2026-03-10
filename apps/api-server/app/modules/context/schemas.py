from typing import Any, Literal

from pydantic import BaseModel, Field

HomeMode = Literal["home", "away", "night", "sleep", "custom"]
PrivacyMode = Literal["balanced", "strict", "care"]
AutomationLevel = Literal["manual", "assisted", "automatic"]
HomeAssistantStatus = Literal["healthy", "degraded", "offline"]
PresenceStatus = Literal["home", "away", "unknown"]
ActivityStatus = Literal["active", "focused", "resting", "sleeping", "idle"]
RoomScenePreset = Literal["auto", "welcome", "focus", "rest", "quiet"]
ClimatePolicy = Literal["follow_member", "follow_room", "manual"]
InsightTone = Literal["info", "success", "warning", "danger"]
ContextStateSource = Literal["snapshot", "configured", "default"]


class ContextConfigMemberState(BaseModel):
    member_id: str = Field(min_length=1)
    presence: PresenceStatus = "unknown"
    activity: ActivityStatus = "idle"
    current_room_id: str | None = None
    confidence: int = Field(default=0, ge=0, le=100)
    last_seen_minutes: int = Field(default=0, ge=0, le=720)
    highlight: str = Field(default="", max_length=500)


class ContextConfigRoomSetting(BaseModel):
    room_id: str = Field(min_length=1)
    scene_preset: RoomScenePreset = "auto"
    climate_policy: ClimatePolicy = "follow_room"
    privacy_guard_enabled: bool = False
    announcement_enabled: bool = True


class ContextConfigUpsert(BaseModel):
    home_mode: HomeMode = "home"
    privacy_mode: PrivacyMode = "balanced"
    automation_level: AutomationLevel = "assisted"
    home_assistant_status: HomeAssistantStatus = "healthy"
    active_member_id: str | None = None
    voice_fast_path_enabled: bool = True
    guest_mode_enabled: bool = False
    child_protection_enabled: bool = True
    elder_care_watch_enabled: bool = True
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = Field(default="22:00", pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")
    member_states: list[ContextConfigMemberState] = Field(default_factory=list)
    room_settings: list[ContextConfigRoomSetting] = Field(default_factory=list)


class ContextConfigRead(ContextConfigUpsert):
    household_id: str
    version: int
    updated_by: str | None = None
    updated_at: str


class ContextOverviewActiveMember(BaseModel):
    member_id: str
    name: str
    role: str
    presence: PresenceStatus
    activity: ActivityStatus
    current_room_id: str | None = None
    current_room_name: str | None = None
    confidence: int = Field(ge=0, le=100)
    source: ContextStateSource


class ContextOverviewMemberState(BaseModel):
    member_id: str
    name: str
    role: str
    presence: PresenceStatus
    activity: ActivityStatus
    current_room_id: str | None = None
    current_room_name: str | None = None
    confidence: int = Field(ge=0, le=100)
    last_seen_minutes: int = Field(ge=0)
    highlight: str
    source: ContextStateSource
    source_summary: Any | None = None
    updated_at: str | None = None


class ContextOverviewRoomOccupant(BaseModel):
    member_id: str
    name: str
    role: str
    presence: PresenceStatus
    activity: ActivityStatus


class ContextOverviewRoomOccupancy(BaseModel):
    room_id: str
    name: str
    room_type: str
    privacy_level: str
    occupant_count: int = Field(ge=0)
    occupants: list[ContextOverviewRoomOccupant]
    device_count: int = Field(ge=0)
    online_device_count: int = Field(ge=0)
    scene_preset: RoomScenePreset
    climate_policy: ClimatePolicy
    privacy_guard_enabled: bool
    announcement_enabled: bool


class ContextOverviewDeviceSummary(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    offline: int = Field(ge=0)
    inactive: int = Field(ge=0)
    controllable: int = Field(ge=0)


class ContextOverviewInsight(BaseModel):
    code: str
    title: str
    message: str
    tone: InsightTone


class ContextOverviewRead(BaseModel):
    household_id: str
    household_name: str
    home_mode: HomeMode
    privacy_mode: PrivacyMode
    automation_level: AutomationLevel
    home_assistant_status: HomeAssistantStatus
    voice_fast_path_enabled: bool
    guest_mode_enabled: bool
    child_protection_enabled: bool
    elder_care_watch_enabled: bool
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    active_member: ContextOverviewActiveMember | None = None
    member_states: list[ContextOverviewMemberState]
    room_occupancy: list[ContextOverviewRoomOccupancy]
    device_summary: ContextOverviewDeviceSummary
    insights: list[ContextOverviewInsight]
    degraded: bool
    generated_at: str
