from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.device.entity_store import build_binding_entity_ids
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


def _binding_matches_entity(db: Session, binding: DeviceBinding, requested_entity_id: str) -> bool:
    entity_id = requested_entity_id.strip()
    if not entity_id:
        return False
    return entity_id in _collect_binding_entity_ids(db, binding)


def _collect_binding_entity_ids(db: Session, binding: DeviceBinding) -> set[str]:
    capabilities = _load_binding_capabilities(binding)
    return build_binding_entity_ids(db, binding=binding, capabilities=capabilities)


def _load_binding_capabilities(binding: DeviceBinding) -> dict[str, Any]:
    try:
        from app.db.utils import load_json
    except ImportError:
        return {}
    loaded = load_json(binding.capabilities)
    return loaded if isinstance(loaded, dict) else {}


def get_device_binding(db: Session, *, device_id: str, requested_entity_id: str | None = None) -> DeviceBinding | None:
    bindings = list(
        db.scalars(
            select(DeviceBinding)
            .where(DeviceBinding.device_id == device_id)
            .order_by(DeviceBinding.last_sync_at.desc().nullslast(), DeviceBinding.id.asc())
        ).all()
    )
    normalized_entity_id = (requested_entity_id or "").strip()
    if normalized_entity_id:
        for binding in bindings:
            if _binding_matches_entity(db, binding, normalized_entity_id):
                return binding
    return bindings[0] if bindings else None


def route_device_plugin(db: Session, *, device: Device, requested_entity_id: str | None = None) -> DevicePluginRoute:
    binding = get_device_binding(db, device_id=device.id, requested_entity_id=requested_entity_id)
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
