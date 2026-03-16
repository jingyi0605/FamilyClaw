from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.modules.device_control.protocol import DeviceActionName, RiskLevel


class DeviceControlRequest(BaseModel):
    household_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    action: DeviceActionName
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=100)
    confirm_high_risk: bool = False
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    requested_by: dict[str, Any] | None = None


class DeviceControlBindingSnapshot(BaseModel):
    binding_id: str
    integration_instance_id: str | None = None
    platform: str
    plugin_id: str
    external_device_id: str | None = None
    external_entity_id: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    binding_version: int = 1


class DeviceControlDeviceSnapshot(BaseModel):
    id: str
    name: str
    device_type: str
    status: str
    controllable: bool
    room_id: str | None = None


class DeviceControlPluginPayload(BaseModel):
    schema_version: str = "device-control.v1"
    request_id: str
    household_id: str
    plugin_id: str
    binding: DeviceControlBindingSnapshot
    device_snapshot: DeviceControlDeviceSnapshot
    action: DeviceActionName
    params: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(ge=1)
    reason: str
    risk_level: RiskLevel
    idempotency_key: str | None = None
    system_context: dict[str, Any] | None = None


class DeviceControlPluginResult(BaseModel):
    schema_version: str = "device-control-result.v1"
    success: bool
    platform: str
    plugin_id: str
    executed_action: DeviceActionName
    external_request: dict[str, Any] | None = None
    external_response: dict[str, Any] | list[Any] | None = None
    normalized_state_patch: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_error_fields(self) -> "DeviceControlPluginResult":
        if self.success and (self.error_code or self.error_message):
            raise ValueError("成功结果不能带错误字段")
        if not self.success and (not self.error_code or not self.error_message):
            raise ValueError("失败结果必须带错误字段")
        return self


class DeviceControlExecutionResult(BaseModel):
    request_id: str
    household_id: str
    device_id: str
    action: DeviceActionName
    params: dict[str, Any] = Field(default_factory=dict)
    plugin_id: str
    platform: str
    risk_level: RiskLevel
    external_request: dict[str, Any] | None = None
    external_response: dict[str, Any] | list[Any] | None = None
    normalized_state_patch: dict[str, Any] | None = None
