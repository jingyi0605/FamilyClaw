from __future__ import annotations

from collections.abc import Mapping

from app.modules.ai_gateway.provider_driver import build_openai_compatible_driver
from app.modules.ai_gateway.schemas import AiCapability
from app.modules.plugin.schemas import PluginRegistryItem
from app.plugins._ai_provider_runtime_helpers import (
    WrappedAiProviderDriver,
    clone_provider_profile_with_extra_config,
    read_int_value,
    read_provider_extra_config,
)

_FAST_TEXT_TASK_TYPES = {
    "butler_bootstrap_extract",
    "config_extraction",
    "conversation_device_control_planner",
    "conversation_intent_detection",
    "memory_extraction",
    "proposal_batch_extraction",
    "reminder_extraction",
}
_FAST_TASK_MAX_TOKENS = 256


def build_driver(plugin: PluginRegistryItem | None = None):
    return WrappedAiProviderDriver(
        base_driver=build_openai_compatible_driver(plugin),
        prepare_request=_prepare_request,
    )


def _prepare_request(provider_profile, capability: AiCapability, payload: Mapping[str, object]):
    if capability != "text":
        return provider_profile, payload

    task_type = str(payload.get("task_type") or "").strip()
    if not task_type:
        return provider_profile, payload

    extra_config = read_provider_extra_config(provider_profile)
    next_extra_config = dict(extra_config)
    changed = False

    payload_temperature = _read_optional_float(payload.get("temperature"))
    if payload_temperature is not None:
        next_extra_config["temperature"] = payload_temperature
        changed = True

    current_max_tokens = read_int_value(extra_config.get("max_tokens"), 512)
    payload_max_tokens = read_int_value(payload.get("max_tokens"), current_max_tokens)
    if task_type in _FAST_TEXT_TASK_TYPES:
        payload_max_tokens = min(payload_max_tokens, _FAST_TASK_MAX_TOKENS)
    if payload_max_tokens != current_max_tokens:
        next_extra_config["max_tokens"] = payload_max_tokens
        changed = True

    model_name = str(extra_config.get("model_name") or extra_config.get("default_model") or "").strip().lower()
    if task_type in _FAST_TEXT_TASK_TYPES and _supports_thinking_control(model_name):
        default_request_body = extra_config.get("default_request_body")
        if not isinstance(default_request_body, dict):
            default_request_body = {}
        else:
            default_request_body = dict(default_request_body)
        if default_request_body.get("thinking") != {"type": "disabled"}:
            default_request_body["thinking"] = {"type": "disabled"}
            next_extra_config["default_request_body"] = default_request_body
            changed = True

    if not changed:
        return provider_profile, payload
    return clone_provider_profile_with_extra_config(provider_profile, next_extra_config), payload


def _supports_thinking_control(model_name: str) -> bool:
    return model_name.startswith("glm-5")


def _read_optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
