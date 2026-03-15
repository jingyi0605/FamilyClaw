from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeviceType = Literal["light", "ac", "curtain", "speaker", "camera", "sensor", "lock"]
DeviceVendor = Literal["xiaomi", "ha", "other"]
DeviceStatus = Literal["active", "offline", "inactive"]


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
