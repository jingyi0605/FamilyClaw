from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.device.models import Device, DeviceBinding


HOME_ASSISTANT_PLUGIN_ID = "homeassistant"


@dataclass(slots=True)
class DevicePluginRoute:
    plugin_id: str
    binding: DeviceBinding


class DevicePluginRoutingError(ValueError):
    def __init__(self, message: str, *, error_code: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.field = field


def resolve_home_assistant_action_plugin_id(device_type: str) -> str:
    _ = device_type
    return HOME_ASSISTANT_PLUGIN_ID


def get_device_binding(db: Session, *, device_id: str) -> DeviceBinding | None:
    return db.scalar(select(DeviceBinding).where(DeviceBinding.device_id == device_id).order_by(DeviceBinding.id.asc()))


def route_device_plugin(db: Session, *, device: Device) -> DevicePluginRoute:
    binding = get_device_binding(db, device_id=device.id)
    if binding is None:
        raise DevicePluginRoutingError(
            "设备缺少正式绑定信息",
            error_code="device_binding_missing",
            field="device_id",
        )
    if not binding.plugin_id:
        raise DevicePluginRoutingError(
            "设备绑定缺少 plugin_id，不能继续执行",
            error_code="device_binding_missing",
            field="plugin_id",
        )
    return DevicePluginRoute(plugin_id=binding.plugin_id, binding=binding)
