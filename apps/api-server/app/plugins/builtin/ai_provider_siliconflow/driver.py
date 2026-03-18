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


def build_driver(plugin: PluginRegistryItem | None = None):
    return WrappedAiProviderDriver(
        base_driver=build_openai_compatible_driver(plugin),
        prepare_request=_prepare_request,
    )


def _prepare_request(provider_profile, capability: AiCapability, payload: Mapping[str, object]):
    extra_config = read_provider_extra_config(provider_profile)
    model_name = str(extra_config.get("model_name") or extra_config.get("default_model") or "").strip().lower()
    if not _is_thinking_model(model_name):
        return provider_profile, payload

    next_extra_config = dict(extra_config)
    default_request_body = extra_config.get("default_request_body")
    if not isinstance(default_request_body, dict):
        default_request_body = {}
    else:
        default_request_body = dict(default_request_body)

    default_request_body["enable_thinking"] = False
    default_request_body.setdefault("thinking_budget", 128)
    next_extra_config["default_request_body"] = default_request_body

    next_payload = payload
    if capability == "text":
        max_tokens_ceiling = 128 if _resolve_text_task_kind(payload) in {"scene_explanation", "reminder_copywriting"} else 256
        next_extra_config["max_tokens"] = min(read_int_value(extra_config.get("max_tokens"), max_tokens_ceiling), max_tokens_ceiling)
        if "max_tokens" in payload:
            next_payload = {
                **payload,
                "max_tokens": min(read_int_value(payload.get("max_tokens"), max_tokens_ceiling), max_tokens_ceiling),
            }

    return clone_provider_profile_with_extra_config(provider_profile, next_extra_config), next_payload


def _is_thinking_model(model_name: str) -> bool:
    is_qwen3 = ("qwen3-" in model_name or model_name.endswith("qwen3") or "/qwen3" in model_name) and "qwen3-235b" not in model_name
    is_qwen35 = "qwen3.5-" in model_name or "/qwen3.5" in model_name
    is_deepseek_r1 = "deepseek-r1" in model_name
    return is_qwen3 or is_qwen35 or is_deepseek_r1


def _resolve_text_task_kind(payload: Mapping[str, object]) -> str:
    task_type = str(payload.get("task_type") or "").strip()
    if task_type in {"reminder_copywriting", "scene_explanation"}:
        return task_type
    if "title" in payload and "question" not in payload and "scene_name" not in payload:
        return "reminder_copywriting"
    if "scene_name" in payload:
        return "scene_explanation"
    return "general"
