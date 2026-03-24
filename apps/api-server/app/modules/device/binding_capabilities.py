from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import load_json
from app.modules.device.models import Device, DeviceBinding
from app.modules.integration.speaker_plugin_capabilities import plugin_uses_speaker_gateway_discovery
from app.modules.plugin.service import PluginServiceError, get_household_plugin

VOICE_TERMINAL_CAPABILITY_TAGS = frozenset({"voice_terminal", "voiceprint", "speaker", "microphone"})
VOICE_TERMINAL_ADAPTER_TYPES = frozenset({"voice_terminal", "speaker_adapter"})
VOICE_TERMINAL_DEVICE_FIELD_KEYS = frozenset({"voice_auto_takeover_enabled", "voice_takeover_prefixes"})


def load_binding_capabilities(binding: DeviceBinding) -> dict[str, Any]:
    if not binding.capabilities:
        return {}
    loaded = load_json(binding.capabilities)
    return loaded if isinstance(loaded, dict) else {}


def load_capability_tags(capabilities: dict[str, Any]) -> list[str]:
    raw_tags = capabilities.get("capability_tags")
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    for item in raw_tags:
        text = str(item).strip().lower()
        if not text or text in tags:
            continue
        tags.append(text)
    return tags


def binding_supports_voice_terminal(
    db: Session,
    *,
    device: Device,
    binding: DeviceBinding,
    capabilities: dict[str, Any] | None = None,
) -> bool:
    if binding.plugin_id:
        try:
            plugin = get_household_plugin(
                db,
                household_id=device.household_id,
                plugin_id=binding.plugin_id,
            )
        except PluginServiceError:
            plugin = None
        if plugin is not None and (
            plugin.capabilities.speaker_adapter is not None
            or plugin_uses_speaker_gateway_discovery(plugin)
        ):
            return True

    resolved_capabilities = capabilities if capabilities is not None else load_binding_capabilities(binding)
    adapter_type = _normalize_optional_text(resolved_capabilities.get("adapter_type"))
    if adapter_type is None:
        adapter_type = _normalize_optional_text(binding.platform)
    if adapter_type in VOICE_TERMINAL_ADAPTER_TYPES:
        return True

    capability_tags = set(load_capability_tags(resolved_capabilities))
    return bool(capability_tags.intersection(VOICE_TERMINAL_CAPABILITY_TAGS))


def config_spec_supports_voice_terminal_device_fields(field_keys: set[str]) -> bool:
    return bool(field_keys.intersection(VOICE_TERMINAL_DEVICE_FIELD_KEYS))


def _normalize_optional_text(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None
