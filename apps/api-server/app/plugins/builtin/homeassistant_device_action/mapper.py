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
            return _call("light", "turn_on", entity_id, {}, {"status": "active", "state": "on", "value": True})
        if payload.action == "turn_off":
            return _call("light", "turn_off", entity_id, {}, {"status": "inactive", "state": "off", "value": False})
        if payload.action == "set_brightness":
            return _call(
                "light",
                "turn_on",
                entity_id,
                {"brightness_pct": params["brightness_pct"]},
                {"status": "active", "state": "on", "value": params["brightness_pct"]},
            )

    if device_type == "ac":
        if payload.action == "turn_on":
            return _call("climate", "turn_on", entity_id, {}, {"status": "active", "state": "on"})
        if payload.action == "turn_off":
            return _call("climate", "turn_off", entity_id, {}, {"status": "inactive", "state": "off"})
        if payload.action == "set_temperature":
            return _call(
                "climate",
                "set_temperature",
                entity_id,
                {"temperature": params["temperature_c"]},
                {"status": "active", "value": params["temperature_c"]},
            )
        if payload.action == "set_hvac_mode":
            next_status = "inactive" if params["hvac_mode"] == "off" else "active"
            return _call(
                "climate",
                "set_hvac_mode",
                entity_id,
                {"hvac_mode": params["hvac_mode"]},
                {"status": next_status, "state": params["hvac_mode"], "value": params["hvac_mode"]},
            )

    if device_type == "curtain":
        if payload.action == "open":
            return _call("cover", "open_cover", entity_id, {}, {"status": "active", "state": "open", "value": "open"})
        if payload.action == "close":
            return _call("cover", "close_cover", entity_id, {}, {"status": "inactive", "state": "closed", "value": "closed"})
        if payload.action == "stop":
            return _call("cover", "stop_cover", entity_id, {}, {"value": "stopped"})

    if device_type == "speaker":
        if payload.action == "turn_on":
            return _call("media_player", "turn_on", entity_id, {}, {"status": "active", "state": "on"})
        if payload.action == "turn_off":
            return _call("media_player", "turn_off", entity_id, {}, {"status": "inactive", "state": "off"})
        if payload.action == "play_pause":
            return _call("media_player", "media_play_pause", entity_id, {}, {"status": "active"})
        if payload.action == "set_volume":
            return _call(
                "media_player",
                "volume_set",
                entity_id,
                {"volume_level": round(float(params["volume_pct"]) / 100.0, 4)},
                {"status": "active", "value": params["volume_pct"]},
            )

    if device_type == "lock":
        if payload.action == "lock":
            return _call("lock", "lock", entity_id, {}, {"status": "inactive", "state": "locked", "value": "locked"})
        if payload.action == "unlock":
            return _call("lock", "unlock", entity_id, {}, {"status": "active", "state": "unlocked", "value": "unlocked"})

    raise HomeAssistantActionMappingError(
        f"设备类型 {device_type} 不支持动作 {payload.action}",
        error_code="action_not_supported_by_platform",
    )


def _resolve_entity_id(payload: DeviceControlPluginPayload) -> str:
    requested_entity_id = (payload.target_entity_id or "").strip()
    if requested_entity_id:
        if requested_entity_id in _collect_binding_entity_ids(payload):
            return requested_entity_id
        raise HomeAssistantActionMappingError(
            "请求的实体不属于当前设备",
            error_code="platform_target_not_found",
        )

    capabilities = payload.binding.capabilities or {}
    # 老绑定里 external_entity_id 可能指向 sensor，一旦这里优先用它，聊天快控就会和设备页走出两套行为。
    # 默认执行必须优先选择主控实体，其次再退回旧字段。
    for candidate in (
        _resolve_preferred_capability_entity_id(payload, capabilities),
        payload.binding.external_entity_id,
    ):
        normalized = _normalize_entity_id(candidate)
        if normalized:
            return normalized

    raise HomeAssistantActionMappingError(
        "设备绑定缺少 Home Assistant entity_id",
        error_code="platform_target_not_found",
    )


def _resolve_preferred_capability_entity_id(
    payload: DeviceControlPluginPayload,
    capabilities: dict[str, Any],
) -> str | None:
    primary_entity_id = _normalize_entity_id(capabilities.get("primary_entity_id"))
    if primary_entity_id:
        return primary_entity_id

    expected_domain = _expected_domain_for_device_type(payload.device_snapshot.device_type)
    raw_entities = capabilities.get("entities")
    if not isinstance(raw_entities, list):
        return None

    fallback_entity_id: str | None = None
    for raw_entity in raw_entities:
        if not isinstance(raw_entity, dict):
            continue
        entity_id = _normalize_entity_id(raw_entity.get("entity_id"))
        if not entity_id:
            continue
        if fallback_entity_id is None:
            fallback_entity_id = entity_id
        domain = _normalize_entity_id(raw_entity.get("domain"))
        control = raw_entity.get("control") if isinstance(raw_entity.get("control"), dict) else {}
        control_kind = _normalize_entity_id(control.get("kind")) or "none"
        if expected_domain and domain == expected_domain and control_kind != "none":
            return entity_id

    return fallback_entity_id


def _expected_domain_for_device_type(device_type: str) -> str | None:
    return {
        "light": "light",
        "ac": "climate",
        "curtain": "cover",
        "speaker": "media_player",
        "lock": "lock",
    }.get(device_type)


def _collect_binding_entity_ids(payload: DeviceControlPluginPayload) -> set[str]:
    entity_ids: set[str] = set()
    capabilities = payload.binding.capabilities or {}
    for candidate in (
        payload.binding.external_entity_id,
        capabilities.get("primary_entity_id"),
    ):
        normalized = _normalize_entity_id(candidate)
        if normalized:
            entity_ids.add(normalized)

    raw_entity_ids = capabilities.get("entity_ids")
    if isinstance(raw_entity_ids, list):
        for candidate in raw_entity_ids:
            normalized = _normalize_entity_id(candidate)
            if normalized:
                entity_ids.add(normalized)

    for raw_entity in capabilities.get("entities", []):
        if not isinstance(raw_entity, dict):
            continue
        normalized = _normalize_entity_id(raw_entity.get("entity_id"))
        if normalized:
            entity_ids.add(normalized)
    return entity_ids


def _normalize_entity_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


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
