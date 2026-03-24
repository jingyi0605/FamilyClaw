from __future__ import annotations

from typing import Any

from app.modules.device.binding_capabilities import config_spec_supports_voice_terminal_device_fields
from app.modules.plugin.schemas import PluginManifestConfigSpec

from .models import Device


def _normalize_voice_takeover_prefixes(raw_value: Any) -> list[str]:
    if isinstance(raw_value, str):
        raw_items = raw_value.replace("，", ",").replace("\n", ",").split(",")
    elif isinstance(raw_value, list):
        raw_items = raw_value
    else:
        return []

    normalized: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text or text in normalized:
            continue
        normalized.append(text)
    return normalized


def load_device_scope_legacy_payloads(
    *,
    plugin_id: str,
    config_spec: PluginManifestConfigSpec,
    device: Device,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    _ = plugin_id
    if config_spec.scope_type != "device":
        return {}, {}, False

    field_keys = {field.key for field in config_spec.config_schema.fields}
    if not config_spec_supports_voice_terminal_device_fields(field_keys):
        return {}, {}, False

    data: dict[str, Any] = {}
    if "voice_auto_takeover_enabled" in field_keys:
        data["voice_auto_takeover_enabled"] = bool(device.voice_auto_takeover_enabled)
    if "voice_takeover_prefixes" in field_keys:
        data["voice_takeover_prefixes"] = "\n".join(device.voice_takeover_prefixes)
    return data, {}, True


def sync_device_scope_legacy_fields(
    *,
    plugin_id: str,
    config_spec: PluginManifestConfigSpec,
    device: Device,
    values: dict[str, Any],
) -> None:
    _ = plugin_id
    if config_spec.scope_type != "device":
        return

    field_keys = {field.key for field in config_spec.config_schema.fields}
    if not config_spec_supports_voice_terminal_device_fields(field_keys):
        return

    if "voice_auto_takeover_enabled" in values:
        device.voice_auto_takeover_enabled = 1 if bool(values["voice_auto_takeover_enabled"]) else 0
    if "voice_takeover_prefixes" in values:
        normalized_prefixes = _normalize_voice_takeover_prefixes(values["voice_takeover_prefixes"])
        if normalized_prefixes:
            device.voice_takeover_prefixes = normalized_prefixes
