from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.device.schemas import DeviceRead
from app.modules.device_control.protocol import DeviceActionName


class DeviceActionExecuteRequest(BaseModel):
    household_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    entity_id: str | None = Field(default=None, min_length=1)
    action: DeviceActionName
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="context.fast_path", min_length=1, max_length=100)
    confirm_high_risk: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


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
