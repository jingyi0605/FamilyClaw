from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.device_control.schemas import DeviceControlPluginPayload


@dataclass(frozen=True, slots=True)
class HomeAssistantServiceCall:
    domain: str
    service: str
    entity_id: str
    service_data: dict[str, Any]
    normalized_state_patch: dict[str, Any] | None = None


class HomeAssistantActionMappingError(ValueError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def build_service_call(
    payload: DeviceControlPluginPayload,
    *,
    allowed_device_types: set[str] | None = None,
) -> HomeAssistantServiceCall:
    device_type = payload.device_snapshot.device_type
    if allowed_device_types is not None and device_type not in allowed_device_types:
        raise HomeAssistantActionMappingError(
            f"插件不负责设备类型 {device_type}",
            error_code="action_not_supported_by_platform",
        )

    entity_id = _resolve_entity_id(payload)
    params = payload.params

    if device_type == "light":
        if payload.action == "turn_on":
            return _call("light", "turn_on", entity_id, {}, {"status": "active"})
        if payload.action == "turn_off":
            return _call("light", "turn_off", entity_id, {}, {"status": "inactive"})
        if payload.action == "set_brightness":
            return _call("light", "turn_on", entity_id, {"brightness_pct": params["brightness_pct"]}, {"status": "active"})

    if device_type == "ac":
        if payload.action == "turn_on":
            return _call("climate", "turn_on", entity_id, {}, {"status": "active"})
        if payload.action == "turn_off":
            return _call("climate", "turn_off", entity_id, {}, {"status": "inactive"})
        if payload.action == "set_temperature":
            return _call("climate", "set_temperature", entity_id, {"temperature": params["temperature_c"]}, {"status": "active"})
        if payload.action == "set_hvac_mode":
            next_status = "inactive" if params["hvac_mode"] == "off" else "active"
            return _call("climate", "set_hvac_mode", entity_id, {"hvac_mode": params["hvac_mode"]}, {"status": next_status})

    if device_type == "curtain":
        if payload.action == "open":
            return _call("cover", "open_cover", entity_id, {}, {"status": "active"})
        if payload.action == "close":
            return _call("cover", "close_cover", entity_id, {}, {"status": "inactive"})
        if payload.action == "stop":
            return _call("cover", "stop_cover", entity_id, {}, None)

    if device_type == "speaker":
        if payload.action == "turn_on":
            return _call("media_player", "turn_on", entity_id, {}, {"status": "active"})
        if payload.action == "turn_off":
            return _call("media_player", "turn_off", entity_id, {}, {"status": "inactive"})
        if payload.action == "play_pause":
            return _call("media_player", "media_play_pause", entity_id, {}, {"status": "active"})
        if payload.action == "set_volume":
            return _call(
                "media_player",
                "volume_set",
                entity_id,
                {"volume_level": round(float(params["volume_pct"]) / 100.0, 4)},
                {"status": "active"},
            )

    if device_type == "lock":
        if payload.action == "lock":
            return _call("lock", "lock", entity_id, {}, {"status": "inactive"})
        if payload.action == "unlock":
            return _call("lock", "unlock", entity_id, {}, {"status": "active"})

    raise HomeAssistantActionMappingError(
        f"设备类型 {device_type} 不支持动作 {payload.action}",
        error_code="action_not_supported_by_platform",
    )


def _resolve_entity_id(payload: DeviceControlPluginPayload) -> str:
    entity_id = (payload.binding.external_entity_id or "").strip()
    if entity_id:
        return entity_id

    capabilities = payload.binding.capabilities or {}
    capability_entity_id = capabilities.get("primary_entity_id")
    if isinstance(capability_entity_id, str) and capability_entity_id.strip():
        return capability_entity_id.strip()

    raise HomeAssistantActionMappingError(
        "设备绑定缺少 Home Assistant entity_id",
        error_code="platform_target_not_found",
    )


def _call(
    domain: str,
    service: str,
    entity_id: str,
    service_data: dict[str, Any],
    normalized_state_patch: dict[str, Any] | None,
) -> HomeAssistantServiceCall:
    return HomeAssistantServiceCall(
        domain=domain,
        service=service,
        entity_id=entity_id,
        service_data={"entity_id": entity_id, **service_data},
        normalized_state_patch=normalized_state_patch,
    )
