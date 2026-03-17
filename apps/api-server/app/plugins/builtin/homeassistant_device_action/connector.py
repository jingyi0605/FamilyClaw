from __future__ import annotations

import asyncio
from typing import Any

from app.modules.device_integration.schemas import DeviceIntegrationPluginPayload
from app.plugins.builtin.homeassistant_device_action.adapter import (
    build_home_assistant_client,
    build_session_factory,
    extract_database_url,
)
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClientError

SUPPORTED_DEVICE_TYPES: dict[str, tuple[str, bool]] = {
    "light": ("light", True),
    "climate": ("ac", True),
    "cover": ("curtain", True),
    "media_player": ("speaker", True),
    "camera": ("camera", False),
    "lock": ("lock", True),
    "sensor": ("sensor", False),
    "binary_sensor": ("sensor", False),
}

DOMAIN_PRIORITY = {
    "climate": 0,
    "light": 1,
    "cover": 2,
    "lock": 3,
    "media_player": 4,
    "camera": 5,
    "sensor": 6,
    "binary_sensor": 7,
}


def sync(payload: dict | None = None) -> dict:
    raw_payload = payload or {}
    try:
        request = DeviceIntegrationPluginPayload.model_validate(raw_payload)
    except Exception as exc:
        return _plugin_error_result(
            plugin_id=str(raw_payload.get("plugin_id") or "homeassistant"),
            reason=f"接入 payload 不合法: {exc}",
        )

    database_url = extract_database_url(raw_payload)
    if not database_url:
        return _plugin_error_result(
            plugin_id=request.plugin_id,
            reason="缺少插件运行时数据库上下文",
        )

    session_factory, engine = build_session_factory(database_url)
    try:
        with session_factory() as db:
            try:
                client = build_home_assistant_client(
                    db,
                    integration_instance_id=request.integration_instance_id,
                    timeout_seconds=15,
                )
                device_registry, entity_registry, area_registry, states = _fetch_home_assistant_payloads(client)
                return _build_sync_result(
                    request=request,
                    device_registry=device_registry,
                    entity_registry=entity_registry,
                    area_registry=area_registry,
                    states=states,
                    base_url=client.get_base_url(),
                )
            except HomeAssistantClientError as exc:
                return _plugin_error_result(plugin_id=request.plugin_id, reason=str(exc))
    finally:
        engine.dispose()


def _fetch_home_assistant_payloads(client) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    async def _run() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        return await asyncio.gather(
            asyncio.to_thread(client.get_device_registry),
            asyncio.to_thread(client.get_entity_registry),
            asyncio.to_thread(client.get_area_registry),
            asyncio.to_thread(client.get_states),
        )

    return asyncio.run(_run())


def _build_sync_result(
    *,
    request: DeviceIntegrationPluginPayload,
    device_registry: list[dict],
    entity_registry: list[dict],
    area_registry: list[dict],
    states: list[dict],
    base_url: str,
) -> dict[str, Any]:
    state_map = _build_state_map(states)
    area_name_map = _build_area_name_map(area_registry)
    supported_entities_by_device, _ = _group_supported_entities_by_device(entity_registry)
    selected_ids = {item.strip() for item in request.selected_external_ids if item.strip()}

    device_candidates: list[dict[str, Any]] = []
    devices: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    records = _build_observation_records(states)

    for ha_device in device_registry:
        try:
            external_device_id = _normalize_optional_text(ha_device.get("id"))
            if not external_device_id:
                continue
            if selected_ids and external_device_id not in selected_ids:
                continue
            entity_entries = supported_entities_by_device.get(external_device_id, [])
            if not entity_entries:
                continue

            primary_entity = _select_primary_entity(entity_entries)
            primary_entity_id = _normalize_optional_text(primary_entity.get("entity_id"))
            if not primary_entity_id or "." not in primary_entity_id:
                continue
            domain = primary_entity_id.split(".", 1)[0]
            mapped_device_type, controllable = SUPPORTED_DEVICE_TYPES[domain]
            state = state_map.get(primary_entity_id)
            room_name = _resolve_room_name(
                ha_device=ha_device,
                primary_entity=primary_entity,
                area_name_map=area_name_map,
                state_map=state_map,
            )
            name = _resolve_device_name(ha_device=ha_device, primary_entity=primary_entity, state=state)
            candidate = {
                "external_device_id": external_device_id,
                "primary_entity_id": primary_entity_id,
                "name": name,
                "room_name": room_name,
                "device_type": mapped_device_type,
                "entity_count": len(entity_entries),
            }
            device_candidates.append(candidate)
            if request.sync_scope != "device_sync":
                continue
            devices.append(
                {
                    **candidate,
                    "controllable": controllable,
                    "status": _normalize_ha_device_status(entity_entries, state_map),
                    "capabilities": {
                        "ha_device_id": external_device_id,
                        "entity_ids": [entry["entity_id"] for entry in entity_entries],
                        "primary_entity_id": primary_entity_id,
                        "entities": _build_entity_snapshots(
                            entity_entries=entity_entries,
                            state_map=state_map,
                            supported_device_type=mapped_device_type,
                        ),
                        "domain": domain,
                        "manufacturer": _normalize_optional_text(ha_device.get("manufacturer")),
                        "model": _normalize_optional_text(ha_device.get("model")),
                        "sw_version": _normalize_optional_text(ha_device.get("sw_version")),
                        "hw_version": _normalize_optional_text(ha_device.get("hw_version")),
                        "name": name,
                        "state": state.get("state") if isinstance(state, dict) else None,
                        "room_name": room_name,
                        "base_url": base_url,
                    },
                }
            )
        except Exception as exc:
            failures.append({"external_ref": _normalize_optional_text(ha_device.get("id")), "reason": str(exc)})

    room_candidates = _build_room_candidates(area_registry, device_registry, entity_registry)
    rooms = room_candidates if request.sync_scope == "room_sync" else []

    return {
        "schema_version": "device-sync-result.v1",
        "plugin_id": request.plugin_id,
        "platform": "home_assistant",
        "device_candidates": device_candidates if request.sync_scope == "device_candidates" else [],
        "room_candidates": room_candidates if request.sync_scope == "room_candidates" else [],
        "devices": devices,
        "rooms": rooms,
        "failures": failures,
        "records": records,
    }


def _build_room_candidates(area_registry: list[dict], device_registry: list[dict], entity_registry: list[dict]) -> list[dict[str, Any]]:
    counts = _build_area_entity_counts(device_registry, entity_registry)
    items: list[dict[str, Any]] = []
    for area in sorted(area_registry, key=lambda item: str(item.get("name", ""))):
        room_name = _normalize_optional_text(area.get("name"))
        if not room_name:
            continue
        area_id = _normalize_optional_text(area.get("area_id"))
        items.append({"name": room_name, "entity_count": counts.get(area_id or "", 0)})
    return items


def _build_observation_records(states: list[dict]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        entity_id = _normalize_optional_text(state.get("entity_id"))
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        captured_at = _normalize_optional_text(state.get("last_updated")) or _normalize_optional_text(state.get("last_changed"))
        raw_attributes = state.get("attributes")
        attributes: dict[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
        if domain in {"light", "switch", "lock", "cover", "media_player", "climate"}:
            records.append({"record_type": "device_power_state", "external_device_id": entity_id, "device": entity_id, "value": state.get("state"), "unit": "state", "captured_at": captured_at})
        if domain == "sensor":
            unit = _normalize_optional_text(attributes.get("unit_of_measurement")) or ""
            if unit in {"°C", "℃", "celsius"}:
                records.append({"record_type": "temperature", "external_device_id": entity_id, "device": entity_id, "value": _safe_float(state.get("state")), "unit": "celsius", "captured_at": captured_at})
            elif unit in {"%", "percent"} and _looks_like_humidity(entity_id, attributes):
                records.append({"record_type": "humidity", "external_device_id": entity_id, "device": entity_id, "value": _safe_float(state.get("state")), "unit": "percent", "captured_at": captured_at})
    return [item for item in records if item.get("value") is not None]


def _build_entity_snapshots(
    *,
    entity_entries: list[dict],
    state_map: dict[str, dict],
    supported_device_type: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in sorted(entity_entries, key=lambda item: str(item.get("entity_id", ""))):
        entity_id = _normalize_optional_text(entry.get("entity_id"))
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        state = state_map.get(entity_id)
        attributes = state.get("attributes") if isinstance(state, dict) and isinstance(state.get("attributes"), dict) else {}
        unit = _normalize_optional_text(attributes.get("unit_of_measurement")) if isinstance(attributes, dict) else None
        current_state = _normalize_optional_text(state.get("state")) if isinstance(state, dict) else None
        items.append(
            {
                "entity_id": entity_id,
                "name": _resolve_entity_name(entry=entry, state=state),
                "domain": domain,
                "state": current_state or "unknown",
                "state_display": _friendly_state_display(current_state or "unknown"),
                "unit": unit,
                "control": _build_entity_control(
                    supported_device_type=supported_device_type,
                    domain=domain,
                    state=current_state or "unknown",
                    attributes=attributes if isinstance(attributes, dict) else {},
                ),
                "metadata": {
                    "device_class": _normalize_optional_text(attributes.get("device_class")) if isinstance(attributes, dict) else None,
                    "supported_features": attributes.get("supported_features") if isinstance(attributes, dict) else None,
                    "friendly_name": _normalize_optional_text(attributes.get("friendly_name")) if isinstance(attributes, dict) else None,
                },
                "updated_at": _normalize_optional_text(state.get("last_updated")) if isinstance(state, dict) else None,
            }
        )
    return items


def _build_entity_control(
    *,
    supported_device_type: str,
    domain: str,
    state: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    if domain in {"sensor", "binary_sensor", "camera"}:
        return {"kind": "none"}
    if supported_device_type == "light" and domain == "light":
        return {
            "kind": "toggle",
            "value": state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if supported_device_type == "ac" and domain == "climate":
        hvac_modes = attributes.get("hvac_modes")
        if isinstance(hvac_modes, list):
            options = [
                {
                    "label": _friendly_state_display(str(mode)),
                    "value": str(mode),
                    "action": "set_hvac_mode",
                    "params": {"hvac_mode": str(mode)},
                }
                for mode in hvac_modes
                if isinstance(mode, str) and mode.strip()
            ]
            if options:
                return {
                    "kind": "action_set",
                    "value": state,
                    "options": options,
                }
        return {
            "kind": "toggle",
            "value": state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if supported_device_type == "curtain" and domain == "cover":
        return {
            "kind": "action_set",
            "value": state,
            "options": [
                {"label": "打开", "value": "open", "action": "open", "params": {}},
                {"label": "关闭", "value": "closed", "action": "close", "params": {}},
                {"label": "停止", "value": "stopped", "action": "stop", "params": {}},
            ],
        }
    if supported_device_type == "speaker" and domain == "media_player":
        volume_level = attributes.get("volume_level")
        if isinstance(volume_level, (int, float)):
            return {
                "kind": "range",
                "value": int(round(float(volume_level) * 100)),
                "min_value": 0,
                "max_value": 100,
                "step": 5,
                "unit": "%",
                "action": "set_volume",
            }
        return {
            "kind": "toggle",
            "value": state not in {"off", "unknown", "unavailable"},
            "action_on": "turn_on",
            "action_off": "turn_off",
        }
    if supported_device_type == "lock" and domain == "lock":
        return {
            "kind": "action_set",
            "value": state,
            "options": [
                {"label": "上锁", "value": "locked", "action": "lock", "params": {}},
                {"label": "解锁", "value": "unlocked", "action": "unlock", "params": {}},
            ],
        }
    return {"kind": "none"}


def _resolve_entity_name(*, entry: dict, state: dict | None) -> str:
    for value in (
        entry.get("name"),
        entry.get("original_name"),
    ):
        normalized = _normalize_optional_text(value)
        if normalized:
            return normalized
    if isinstance(state, dict):
        attributes = state.get("attributes")
        if isinstance(attributes, dict):
            friendly_name = _normalize_optional_text(attributes.get("friendly_name"))
            if friendly_name:
                return friendly_name
    return str(entry.get("entity_id"))


def _friendly_state_display(value: str) -> str:
    mapping = {
        "on": "开启",
        "off": "关闭",
        "open": "打开",
        "closed": "关闭",
        "locked": "已上锁",
        "unlocked": "未上锁",
        "playing": "播放中",
        "paused": "已暂停",
        "idle": "空闲",
        "cool": "制冷",
        "heat": "制热",
        "auto": "自动",
        "dry": "除湿",
        "fan_only": "送风",
        "unavailable": "离线",
        "unknown": "未知",
    }
    return mapping.get(value, value)


def _plugin_error_result(*, plugin_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "device-sync-result.v1",
        "plugin_id": plugin_id,
        "platform": "home_assistant",
        "device_candidates": [],
        "room_candidates": [],
        "devices": [],
        "rooms": [],
        "failures": [{"external_ref": None, "reason": reason}],
        "records": [],
    }


def _build_state_map(states: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for state in states:
        entity_id = _normalize_optional_text(state.get("entity_id")) if isinstance(state, dict) else None
        if entity_id:
            result[entity_id] = state
    return result


def _build_area_name_map(area_registry: list[dict]) -> dict[str, str]:
    result: dict[str, str] = {}
    for area in area_registry:
        area_id = _normalize_optional_text(area.get("area_id")) if isinstance(area, dict) else None
        area_name = _normalize_optional_text(area.get("name")) if isinstance(area, dict) else None
        if area_id and area_name:
            result[area_id] = area_name
    return result


def _group_supported_entities_by_device(entity_registry: list[dict]) -> tuple[dict[str, list[dict]], int]:
    grouped: dict[str, list[dict]] = {}
    skipped = 0
    for entry in entity_registry:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        entity_id = _normalize_optional_text(entry.get("entity_id"))
        device_id = _normalize_optional_text(entry.get("device_id"))
        disabled_by = _normalize_optional_text(entry.get("disabled_by"))
        if not entity_id or not device_id or disabled_by or "." not in entity_id:
            skipped += 1
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in SUPPORTED_DEVICE_TYPES:
            skipped += 1
            continue
        grouped.setdefault(device_id, []).append(entry)
    return grouped, skipped


def _select_primary_entity(entity_entries: list[dict]) -> dict:
    return sorted(
        entity_entries,
        key=lambda entry: (DOMAIN_PRIORITY.get(str(entry.get("entity_id", "")).split(".", 1)[0], 99), str(entry.get("entity_id", ""))),
    )[0]


def _resolve_device_name(*, ha_device: dict, primary_entity: dict, state: dict | None) -> str:
    for value in (ha_device.get("name_by_user"), ha_device.get("name"), primary_entity.get("name"), primary_entity.get("original_name")):
        normalized = _normalize_optional_text(value)
        if normalized:
            return normalized
    if isinstance(state, dict):
        attributes = state.get("attributes")
        if isinstance(attributes, dict):
            friendly_name = _normalize_optional_text(attributes.get("friendly_name"))
            if friendly_name:
                return friendly_name
    return str(primary_entity.get("entity_id"))


def _normalize_ha_device_status(entity_entries: list[dict], state_map: dict[str, dict]) -> str:
    has_active = False
    has_offline = False
    for entry in entity_entries:
        entity_id = str(entry.get("entity_id", "")).strip()
        state = state_map.get(entity_id)
        if not isinstance(state, dict):
            continue
        normalized = _normalize_device_status(str(state.get("state")))
        if normalized == "active":
            has_active = True
        elif normalized == "offline":
            has_offline = True
    if has_active:
        return "active"
    if has_offline:
        return "offline"
    return "inactive"


def _resolve_room_name(*, ha_device: dict, primary_entity: dict, area_name_map: dict[str, str], state_map: dict[str, dict]) -> str | None:
    for area_id in (_normalize_optional_text(primary_entity.get("area_id")), _normalize_optional_text(ha_device.get("area_id"))):
        if area_id and area_id in area_name_map:
            return area_name_map[area_id]
    state = state_map.get(str(primary_entity.get("entity_id", "")))
    return _extract_room_name(state)


def _build_area_entity_counts(device_registry: list[dict], entity_registry: list[dict]) -> dict[str, int]:
    device_area_map: dict[str, str] = {}
    for device in device_registry:
        if not isinstance(device, dict):
            continue
        device_id = _normalize_optional_text(device.get("id"))
        area_id = _normalize_optional_text(device.get("area_id"))
        if device_id and area_id:
            device_area_map[device_id] = area_id
    counts: dict[str, int] = {}
    for entry in entity_registry:
        if not isinstance(entry, dict):
            continue
        entity_id = _normalize_optional_text(entry.get("entity_id"))
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in SUPPORTED_DEVICE_TYPES:
            continue
        area_id = _normalize_optional_text(entry.get("area_id"))
        if not area_id:
            device_id = _normalize_optional_text(entry.get("device_id"))
            area_id = device_area_map.get(device_id or "")
        if area_id:
            counts[area_id] = counts.get(area_id, 0) + 1
    return counts


def _extract_room_name(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    attributes = state.get("attributes")
    if not isinstance(attributes, dict):
        return None
    for key in ("area_name", "room_name", "room", "roomName", "area"):
        value = attributes.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_device_status(state_value: str) -> str:
    if state_value in {"unavailable", "unknown"}:
        return "offline"
    if state_value in {"off", "idle", "standby", "locked", "closed"}:
        return "inactive"
    return "active"


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_humidity(entity_id: str, attributes: dict[str, Any]) -> bool:
    device_class = _normalize_optional_text(attributes.get("device_class"))
    if device_class == "humidity":
        return True
    return "humidity" in entity_id.lower()
