from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.device.schemas import DeviceRead

DeviceActionName = Literal[
    "turn_on",
    "turn_off",
    "set_brightness",
    "set_temperature",
    "set_hvac_mode",
    "open",
    "close",
    "stop",
    "play_pause",
    "set_volume",
    "lock",
    "unlock",
]


class DeviceActionExecuteRequest(BaseModel):
    household_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    action: DeviceActionName
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="context.fast_path", min_length=1, max_length=100)
    confirm_high_risk: bool = False


class DeviceActionExecuteResponse(BaseModel):
    household_id: str
    device: DeviceRead
    action: DeviceActionName
    platform: str
    service_domain: str
    service_name: str
    entity_id: str
    params: dict[str, Any]
    result: Literal["success"]
    executed_at: str
