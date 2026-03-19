from __future__ import annotations

from typing import Any


WEATHER_STATE_PENDING = "pending_coordinate"
WEATHER_STATE_STALE = "stale"
WEATHER_STATE_ERROR = "error"
WEATHER_MESSAGE_WAITING_COORDINATE = "等待补充坐标"
WEATHER_MESSAGE_UNAVAILABLE = "天气数据暂不可用"
WEATHER_MESSAGE_NO_DATA = "暂无数据"
WEATHER_MESSAGE_STALE = "天气已降级为旧缓存"
WEATHER_ENTITY_PRESENTATION: dict[str, tuple[str, str | None]] = {
    "weather.condition": ("天气状态", None),
    "weather.temperature": ("温度", "°C"),
    "weather.humidity": ("湿度", "%"),
    "weather.wind_speed": ("风速", "m/s"),
    "weather.wind_direction": ("风向", "°"),
    "weather.pressure": ("气压", "hPa"),
    "weather.cloud_cover": ("云量", "%"),
    "weather.precipitation_next_1h": ("未来 1 小时降水", "mm"),
    "weather.forecast_6h": ("未来 6 小时摘要", None),
    "weather.updated_at": ("更新时间", None),
}


def normalize_weather_capabilities_payload(capabilities: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(capabilities, dict):
        return {}

    raw_entities = capabilities.get("entities")
    if not isinstance(raw_entities, list):
        return capabilities

    normalized_entities: list[Any] = []
    changed = False
    for raw_entity in raw_entities:
        if not isinstance(raw_entity, dict):
            normalized_entities.append(raw_entity)
            continue
        normalized_entity, entity_changed = _normalize_weather_entity_payload(raw_entity)
        normalized_entities.append(normalized_entity)
        changed = changed or entity_changed

    if not changed:
        return capabilities

    normalized = dict(capabilities)
    normalized["entities"] = normalized_entities
    return normalized


def _normalize_weather_entity_payload(raw_entity: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    entity_id = str(raw_entity.get("entity_id") or "").strip()
    presentation = WEATHER_ENTITY_PRESENTATION.get(entity_id)
    if presentation is None:
        return raw_entity, False

    name, unit = presentation
    normalized = dict(raw_entity)
    changed = False
    if normalized.get("name") != name:
        normalized["name"] = name
        changed = True
    if normalized.get("unit") != unit:
        normalized["unit"] = unit
        changed = True

    metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
    state = str(normalized.get("state") or "").strip() or "unknown"
    normalized_metadata, metadata_changed = _normalize_weather_entity_metadata(
        entity_id=entity_id,
        state=state,
        metadata=metadata,
    )
    if metadata_changed:
        normalized["metadata"] = normalized_metadata
        metadata = normalized_metadata
        changed = True
    state_display = _build_normalized_weather_state_display(
        entity_id=entity_id,
        state=state,
        unit=unit,
        metadata=metadata,
        fallback=str(normalized.get("state_display") or "").strip(),
    )
    if normalized.get("state_display") != state_display:
        normalized["state_display"] = state_display
        changed = True
    return normalized, changed


def _normalize_weather_entity_metadata(
    *,
    entity_id: str,
    state: str,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    if not metadata:
        return metadata, False

    normalized = dict(metadata)
    changed = False
    condition_text = str(normalized.get("condition_text") or "").strip()
    if condition_text and _looks_like_weather_mojibake(condition_text):
        fallback_condition_text = _build_condition_text_fallback(entity_id=entity_id, state=state)
        if fallback_condition_text is None:
            normalized.pop("condition_text", None)
        else:
            normalized["condition_text"] = fallback_condition_text
        changed = True
    error_message = str(normalized.get("error_message") or "").strip()
    if error_message and _looks_like_weather_mojibake(error_message):
        fallback_error_message = _build_error_message_fallback(state=state)
        if fallback_error_message is None:
            normalized.pop("error_message", None)
        else:
            normalized["error_message"] = fallback_error_message
        changed = True
    return normalized, changed


def _build_normalized_weather_state_display(
    *,
    entity_id: str,
    state: str,
    unit: str | None,
    metadata: dict[str, Any],
    fallback: str,
) -> str:
    safe_fallback = fallback if fallback and not _looks_like_weather_mojibake(fallback) else ""
    error_message = str(metadata.get("error_message") or "").strip()
    if entity_id == "weather.condition":
        condition_text = str(metadata.get("condition_text") or "").strip()
        if condition_text and not _looks_like_weather_mojibake(condition_text):
            return condition_text
        if error_message:
            return error_message
        if state == WEATHER_STATE_PENDING:
            return WEATHER_MESSAGE_WAITING_COORDINATE
        if state == WEATHER_STATE_STALE:
            return WEATHER_MESSAGE_STALE
        if state == WEATHER_STATE_ERROR:
            return WEATHER_MESSAGE_UNAVAILABLE
        if state == "unknown":
            return WEATHER_MESSAGE_NO_DATA
        return safe_fallback or state

    if entity_id == "weather.forecast_6h":
        if state == "unknown":
            return WEATHER_MESSAGE_NO_DATA
        parts: list[str] = []
        condition_text = str(metadata.get("condition_text") or "").strip()
        if condition_text and not _looks_like_weather_mojibake(condition_text):
            parts.append(condition_text)
        min_temperature = metadata.get("min_temperature")
        max_temperature = metadata.get("max_temperature")
        if isinstance(min_temperature, (int, float)) and isinstance(max_temperature, (int, float)):
            parts.append(f"{_format_decimal(float(min_temperature))}~{_format_decimal(float(max_temperature))} °C")
        return " ".join(parts) or safe_fallback or _build_condition_text_fallback(entity_id=entity_id, state=state) or state

    if entity_id == "weather.updated_at":
        if state and state != "unknown":
            return state
        return safe_fallback or WEATHER_MESSAGE_NO_DATA

    if state == "unknown":
        return WEATHER_MESSAGE_NO_DATA
    return safe_fallback or state


def _build_condition_text_fallback(*, entity_id: str, state: str) -> str | None:
    if entity_id == "weather.condition":
        if state == WEATHER_STATE_PENDING:
            return WEATHER_MESSAGE_WAITING_COORDINATE
        if state == WEATHER_STATE_STALE:
            return WEATHER_MESSAGE_STALE
        if state == WEATHER_STATE_ERROR:
            return WEATHER_MESSAGE_UNAVAILABLE
        if state == "unknown":
            return WEATHER_MESSAGE_NO_DATA
        return state
    if entity_id == "weather.forecast_6h":
        if state == "unknown":
            return WEATHER_MESSAGE_NO_DATA
        return state
    return None


def _build_error_message_fallback(*, state: str) -> str | None:
    if state == WEATHER_STATE_PENDING:
        return WEATHER_MESSAGE_WAITING_COORDINATE
    if state == WEATHER_STATE_STALE:
        return WEATHER_MESSAGE_STALE
    if state == WEATHER_STATE_ERROR:
        return WEATHER_MESSAGE_UNAVAILABLE
    if state == "unknown":
        return WEATHER_MESSAGE_NO_DATA
    return None


def _looks_like_weather_mojibake(value: str) -> bool:
    if not value:
        return False

    suspicious_markers = (
        "閿",
        "鑴",
        "蹇",
        "姘",
        "鑾",
        "鍐",
        "婢",
        "閺",
        "閸",
        "鐏",
        "濞",
        "妞",
        "鎺",
        "閹",
        "婵",
        "闁",
        "缂",
        "濡",
        "濠",
        "缁",
        "閻",
        "鏈€",
        "鏆",
        "鏇",
        "澶╂皵",
    )
    return any(marker in value for marker in suspicious_markers)


def _format_decimal(value: float) -> str:
    normalized = f"{value:.1f}"
    return normalized[:-2] if normalized.endswith(".0") else normalized
