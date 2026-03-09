from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    created_at: str
    updated_at: str


class DeviceUpdate(BaseModel):
    room_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    status: DeviceStatus | None = None
    controllable: bool | None = None


class DeviceListResponse(BaseModel):
    items: list[DeviceRead]
    page: int
    page_size: int
    total: int
