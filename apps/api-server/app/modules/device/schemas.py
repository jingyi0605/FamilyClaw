from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.plugin.schemas import PluginConfigFormRead

DeviceType = Literal["light", "ac", "curtain", "speaker", "camera", "sensor", "lock"]
DeviceVendor = Literal["xiaomi", "ha", "other"]
DeviceStatus = Literal["active", "offline", "inactive", "disabled"]
DeviceEntityView = Literal["favorites", "all"]
DeviceEntityControlKind = Literal["none", "toggle", "range", "action_set"]
DeviceDetailBuiltinTabKey = Literal["voiceprint"]


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    room_id: str | None
    name: str
    device_type: DeviceType
    vendor: DeviceVendor
    status: DeviceStatus
    controllable: bool
    voice_auto_takeover_enabled: bool
    voiceprint_identity_enabled: bool
    voice_takeover_prefixes: list[str]
    created_at: str
    updated_at: str


class DeviceUpdate(BaseModel):
    room_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    status: DeviceStatus | None = None
    controllable: bool | None = None
    voice_auto_takeover_enabled: bool | None = None
    voiceprint_identity_enabled: bool | None = None
    voice_takeover_prefixes: list[str] | None = None

    @field_validator("voice_takeover_prefixes", mode="before")
    @classmethod
    def normalize_voice_takeover_prefixes(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            raw_items = value.replace("，", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raise ValueError("voice_takeover_prefixes 必须是字符串或字符串数组")

        normalized: list[str] = []
        for item in raw_items:
            text = str(item).strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def validate_voice_takeover_prefixes(self) -> "DeviceUpdate":
        if self.voice_takeover_prefixes is not None and not self.voice_takeover_prefixes:
            raise ValueError("voice_takeover_prefixes 至少需要一个前缀")
        return self


class DeviceListResponse(BaseModel):
    items: list[DeviceRead]
    page: int
    page_size: int
    total: int


class DeviceDetailCapabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supports_voice_terminal: bool = False
    supports_voiceprint: bool = False
    adapter_type: str | None = None
    plugin_id: str | None = None
    vendor_code: str | None = None
    capability_tags: list[str] = Field(default_factory=list)


class DeviceDetailBuiltinTabRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: DeviceDetailBuiltinTabKey


class DeviceDetailPluginTabRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab_key: str
    title: str
    description: str | None = None
    plugin_id: str
    plugin_name: str
    config_form: PluginConfigFormRead


class DeviceDetailViewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: DeviceRead
    capabilities: DeviceDetailCapabilityRead
    builtin_tabs: list[DeviceDetailBuiltinTabRead] = Field(default_factory=list)
    plugin_tabs: list[DeviceDetailPluginTabRead] = Field(default_factory=list)


class DeviceEntityControlOptionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)


class DeviceEntityControlRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: DeviceEntityControlKind = "none"
    value: Any | None = None
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    action: str | None = None
    action_on: str | None = None
    action_off: str | None = None
    options: list[DeviceEntityControlOptionRead] = Field(default_factory=list)
    disabled: bool = False
    disabled_reason: str | None = None


class DeviceEntityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str
    integration_instance_id: str | None = None
    entity_id: str
    name: str
    domain: str
    state: str
    state_display: str
    unit: str | None = None
    favorite: bool = False
    read_only: bool = False
    control: DeviceEntityControlRead = Field(default_factory=DeviceEntityControlRead)
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str


class DeviceEntityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: DeviceRead
    view: DeviceEntityView
    items: list[DeviceEntityRead] = Field(default_factory=list)


class DeviceEntityFavoriteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    favorite: bool


class DeviceActionLogRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: str
    target_type: str
    result: str
    actor_type: str
    actor_id: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class DeviceActionLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: DeviceRead
    items: list[DeviceActionLogRead] = Field(default_factory=list)
    page: int
    page_size: int
    total: int
