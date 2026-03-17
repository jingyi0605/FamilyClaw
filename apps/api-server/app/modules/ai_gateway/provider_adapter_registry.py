from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR


CUSTOM_PROVIDER_PLUGIN_ROOT = BASE_DIR / "app" / "modules" / "ai_gateway" / "provider_plugins"
PROVIDER_ADAPTER_REGISTRY_PATH = Path(__file__).resolve()
PROVIDER_ADAPTER_PLUGIN_VERSION = "1.0.0"


def list_provider_adapters() -> list[dict[str, Any]]:
    adapters: dict[str, dict[str, Any]] = {
        item["adapter_code"]: item
        for item in _build_builtin_provider_plugins()
    }
    for item in _load_custom_provider_plugins():
        adapters[item["adapter_code"]] = item
    return list(adapters.values())


def _build_plugin_compatibility(
    *,
    transport_type: str,
    api_family: str,
    description: str | None = None,
    compatibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = dict(compatibility or {})
    normalized.setdefault("provider_profile_schema_version", 1)
    normalized.setdefault("transport_type", transport_type)
    normalized.setdefault("api_family", api_family)
    if isinstance(description, str) and description.strip():
        normalized.setdefault("description", description.strip())
    return normalized


def _build_builtin_provider_plugins() -> list[dict[str, Any]]:
    return [
        _build_openai_compatible_provider(
            adapter_code="chatgpt",
            display_name="ChatGPT",
            description="Best for the official OpenAI API and OpenAI-compatible gateways.",
            base_url="https://api.openai.com/v1",
            secret_placeholder="OPENAI_API_KEY",
            model_placeholder="gpt-4o-mini",
            model_default="gpt-4o-mini",
            privacy_options=_public_privacy_options(include_local=True),
            supported_model_types=["llm", "embedding", "vision", "speech", "image"],
        ),
        _build_openai_compatible_provider(
            adapter_code="deepseek",
            display_name="DeepSeek",
            description="Official compatible endpoint for general LLM tasks.",
            base_url="https://api.deepseek.com/v1",
            secret_placeholder="DEEPSEEK_API_KEY",
            model_placeholder="deepseek-chat",
            model_default="deepseek-chat",
            supported_model_types=["llm"],
        ),
        _build_openai_compatible_provider(
            adapter_code="qwen",
            display_name="Qwen",
            description="DashScope compatible endpoint that usually works well in mainland China.",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            secret_placeholder="DASHSCOPE_API_KEY",
            model_placeholder="qwen-plus",
            model_default="qwen-plus",
            supported_model_types=["llm", "embedding", "vision", "image"],
        ),
        _build_openai_compatible_provider(
            adapter_code="glm",
            display_name="GLM",
            description="GLM compatible endpoint that still uses the shared LLM flow.",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            secret_placeholder="GLM_API_KEY",
            model_placeholder="glm-4-flash",
            model_default="glm-4-flash",
            supported_model_types=["llm", "vision", "embedding"],
        ),
        _build_openai_compatible_provider(
            adapter_code="siliconflow",
            display_name="SiliconFlow",
            description="Aggregator-style endpoint for switching across hosted model families.",
            base_url="https://api.siliconflow.cn/v1",
            secret_placeholder="SILICONFLOW_API_KEY",
            model_placeholder="Qwen/Qwen2.5-72B-Instruct",
            model_default="Qwen/Qwen2.5-72B-Instruct",
            supported_model_types=["llm", "embedding", "vision", "speech", "image"],
        ),
        _build_openai_compatible_provider(
            adapter_code="kimi",
            display_name="Kimi",
            description="Moonshot compatible endpoint for long-context LLM conversations.",
            base_url="https://api.moonshot.cn/v1",
            secret_placeholder="KIMI_API_KEY",
            model_placeholder="moonshot-v1-8k",
            model_default="moonshot-v1-8k",
            supported_model_types=["llm", "vision"],
        ),
        _build_openai_compatible_provider(
            adapter_code="minimax",
            display_name="MiniMax",
            description="Keeps the setup surface minimal for everyday use.",
            base_url="https://api.minimax.chat/v1",
            secret_placeholder="MINIMAX_API_KEY",
            model_placeholder="MiniMax-Text-01",
            model_default="MiniMax-Text-01",
            supported_model_types=["llm", "speech", "image"],
        ),
        _build_native_provider(
            adapter_code="claude",
            display_name="Claude",
            description="Anthropic Messages API with its native LLM workflow.",
            base_url="https://api.anthropic.com/v1",
            secret_placeholder="ANTHROPIC_API_KEY",
            model_placeholder="claude-3-7-sonnet-latest",
            model_default="claude-3-7-sonnet-latest",
            supported_model_types=["llm", "vision"],
            extra_fields=[
                _field(
                    "anthropic_version",
                    "Anthropic Version",
                    "text",
                    required=False,
                    placeholder="2023-06-01",
                    default_value="2023-06-01",
                ),
            ],
        ),
        _build_native_provider(
            adapter_code="gemini",
            display_name="Gemini",
            description="Google Gemini GenerateContent API with its native multimodal workflow.",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            secret_placeholder="GEMINI_API_KEY",
            model_placeholder="gemini-2.0-flash",
            model_default="gemini-2.0-flash",
            supported_model_types=["llm", "embedding", "vision", "speech", "image"],
        ),
        _build_openai_compatible_provider(
            adapter_code="openrouter",
            display_name="OpenRouter",
            description="Aggregator for multiple upstream models with a few provider-specific headers.",
            base_url="https://openrouter.ai/api/v1",
            secret_placeholder="OPENROUTER_API_KEY",
            model_placeholder="openai/gpt-4o-mini",
            model_default="openai/gpt-4o-mini",
            supported_model_types=["llm", "vision", "image"],
            extra_fields=[
                _field(
                    "site_url",
                    "Site URL",
                    "text",
                    required=False,
                    placeholder="https://familyclaw.local",
                    help_text="Optional. Sent as HTTP-Referer for OpenRouter requests.",
                ),
                _field(
                    "app_name",
                    "App Name",
                    "text",
                    required=False,
                    placeholder="FamilyClaw",
                    help_text="Optional. Sent as X-Title for OpenRouter requests.",
                ),
            ],
        ),
        _build_openai_compatible_provider(
            adapter_code="doubao",
            display_name="Doubao Ark",
            description="Volcengine Ark compatible endpoint for mainland China deployment.",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            secret_placeholder="ARK_API_KEY",
            model_placeholder="doubao-seed-1-6-flash-250615",
            model_default="doubao-seed-1-6-flash-250615",
            supported_model_types=["llm", "embedding", "vision", "speech"],
        ),
        _build_openai_compatible_provider(
            adapter_code="doubao-coding",
            display_name="Doubao Coding",
            description="Dedicated coding and planning model entry on the Ark endpoint.",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            secret_placeholder="ARK_API_KEY",
            model_placeholder="doubao-seed-code-250615",
            model_default="doubao-seed-code-250615",
            supported_model_types=["llm"],
        ),
        _build_openai_compatible_provider(
            adapter_code="byteplus",
            display_name="BytePlus ModelArk",
            description="BytePlus compatible endpoint for overseas environments.",
            base_url="https://ark.byteintl.com/api/v3",
            secret_placeholder="BYTEPLUS_API_KEY",
            model_placeholder="doubao-1.5-pro-32k",
            model_default="doubao-1.5-pro-32k",
            supported_model_types=["llm", "embedding", "vision", "speech"],
        ),
        _build_openai_compatible_provider(
            adapter_code="byteplus-coding",
            display_name="BytePlus Coding",
            description="Separate coding-oriented model entry on the BytePlus endpoint.",
            base_url="https://ark.byteintl.com/api/v3",
            secret_placeholder="BYTEPLUS_API_KEY",
            model_placeholder="doubao-seed-code",
            model_default="doubao-seed-code",
            supported_model_types=["llm"],
        ),
    ]


def _load_custom_provider_plugins() -> list[dict[str, Any]]:
    if not CUSTOM_PROVIDER_PLUGIN_ROOT.exists():
        return []

    loaded: list[dict[str, Any]] = []
    for path in sorted(CUSTOM_PROVIDER_PLUGIN_ROOT.rglob("*.json")):
        loaded.extend(_load_provider_plugin_file(path))
    return loaded


def _load_provider_plugin_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    if not isinstance(rows, list):
        raise ValueError(f"invalid provider plugin payload: {path}")
    normalized: list[dict[str, Any]] = []
    for item in rows:
        normalized.append(_normalize_custom_provider_plugin(item, path=path))
    return normalized


def _normalize_custom_provider_plugin(item: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"provider plugin entry must be an object: {path}")

    required_fields = [
        "adapter_code",
        "display_name",
        "description",
        "transport_type",
        "api_family",
        "default_privacy_level",
        "default_supported_capabilities",
        "field_schema",
    ]
    missing_fields = [field for field in required_fields if field not in item]
    if missing_fields:
        raise ValueError(f"provider plugin missing fields {missing_fields}: {path}")

    field_schema = item.get("field_schema")
    if not isinstance(field_schema, list):
        raise ValueError(f"provider plugin field_schema must be a list: {path}")

    return {
        "plugin_id": str(item.get("plugin_id") or f"provider-plugin.{item['adapter_code']}"),
        "plugin_name": str(item.get("plugin_name") or item["display_name"]),
        "plugin_version": str(item.get("plugin_version") or PROVIDER_ADAPTER_PLUGIN_VERSION),
        "adapter_code": str(item["adapter_code"]),
        "display_name": str(item["display_name"]),
        "description": str(item["description"]),
        "transport_type": str(item["transport_type"]),
        "api_family": str(item["api_family"]),
        "default_privacy_level": str(item["default_privacy_level"]),
        "default_supported_capabilities": _normalize_string_list(item["default_supported_capabilities"]),
        "supported_model_types": _normalize_string_list(item.get("supported_model_types") or ["llm"]),
        "llm_workflow": str(item.get("llm_workflow") or item["api_family"]),
        "field_schema": [_normalize_field(field, path=path) for field in field_schema],
        "compatibility": _build_plugin_compatibility(
            transport_type=str(item["transport_type"]),
            api_family=str(item["api_family"]),
            description=str(item["description"]),
            compatibility=item.get("compatibility") if isinstance(item.get("compatibility"), dict) else None,
        ),
    }


def _build_openai_compatible_provider(
    *,
    adapter_code: str,
    display_name: str,
    description: str,
    base_url: str,
    secret_placeholder: str,
    model_placeholder: str,
    model_default: str,
    supported_model_types: list[str],
    privacy_options: list[dict[str, str]] | None = None,
    extra_fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fields = [
        _field("display_name", "Display Name", "text", required=True, placeholder=f"{display_name} Main"),
        _field("provider_code", "Provider Code", "text", required=True, placeholder=f"family-{adapter_code}-main"),
        _field(
            "base_url",
            "Base URL",
            "text",
            required=False,
            placeholder=base_url,
            default_value=base_url,
            help_text="Defaults to the common official endpoint. Change it only when you use a proxy or gateway.",
        ),
        _field("secret_ref", "Secret Reference", "secret", required=True, placeholder=secret_placeholder),
        _field("model_name", "Model Name", "text", required=True, placeholder=model_placeholder, default_value=model_default),
        _field(
            "privacy_level",
            "Privacy Level",
            "select",
            required=True,
            options=privacy_options or _public_privacy_options(),
            default_value="public_cloud",
        ),
        _field("latency_budget_ms", "Latency Budget (ms)", "number", required=False, placeholder="15000"),
    ]
    if extra_fields:
        fields.extend(extra_fields)
    return {
        "plugin_id": f"builtin.provider.{adapter_code}",
        "plugin_name": display_name,
        "plugin_version": PROVIDER_ADAPTER_PLUGIN_VERSION,
        "adapter_code": adapter_code,
        "display_name": display_name,
        "description": description,
        "transport_type": "openai_compatible",
        "api_family": "openai_chat_completions",
        "default_privacy_level": "public_cloud",
        "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
        "supported_model_types": supported_model_types,
        "llm_workflow": "openai_chat_completions",
        "field_schema": fields,
        "compatibility": _build_plugin_compatibility(
            transport_type="openai_compatible",
            api_family="openai_chat_completions",
            description=description,
        ),
    }


def _build_native_provider(
    *,
    adapter_code: str,
    display_name: str,
    description: str,
    base_url: str,
    secret_placeholder: str,
    model_placeholder: str,
    model_default: str,
    supported_model_types: list[str],
    extra_fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fields = [
        _field("display_name", "Display Name", "text", required=True, placeholder=f"{display_name} Main"),
        _field("provider_code", "Provider Code", "text", required=True, placeholder=f"family-{adapter_code}-main"),
        _field(
            "base_url",
            "Base URL",
            "text",
            required=False,
            placeholder=base_url,
            default_value=base_url,
            help_text="Defaults to the official native endpoint. Change it only when you use a proxy or gateway.",
        ),
        _field("secret_ref", "Secret Reference", "secret", required=True, placeholder=secret_placeholder),
        _field("model_name", "Model Name", "text", required=True, placeholder=model_placeholder, default_value=model_default),
        _field(
            "privacy_level",
            "Privacy Level",
            "select",
            required=True,
            options=_public_privacy_options(),
            default_value="public_cloud",
        ),
        _field("latency_budget_ms", "Latency Budget (ms)", "number", required=False, placeholder="15000"),
    ]
    if extra_fields:
        fields.extend(extra_fields)
    api_family = "anthropic_messages" if adapter_code == "claude" else "gemini_generate_content"
    return {
        "plugin_id": f"builtin.provider.{adapter_code}",
        "plugin_name": display_name,
        "plugin_version": PROVIDER_ADAPTER_PLUGIN_VERSION,
        "adapter_code": adapter_code,
        "display_name": display_name,
        "description": description,
        "transport_type": "native_sdk",
        "api_family": api_family,
        "default_privacy_level": "public_cloud",
        "default_supported_capabilities": ["qa_generation", "qa_structured_answer"],
        "supported_model_types": supported_model_types,
        "llm_workflow": api_family,
        "field_schema": fields,
        "compatibility": _build_plugin_compatibility(
            transport_type="native_sdk",
            api_family=api_family,
            description=description,
        ),
    }


def _public_privacy_options(*, include_local: bool = False) -> list[dict[str, str]]:
    options = [
        {"label": "Public Cloud", "value": "public_cloud"},
        {"label": "Private Cloud", "value": "private_cloud"},
    ]
    if include_local:
        options.append({"label": "Local Only", "value": "local_only"})
    return options


def _field(
    key: str,
    label: str,
    field_type: str,
    *,
    required: bool,
    placeholder: str | None = None,
    help_text: str | None = None,
    default_value: str | int | bool | None = None,
    options: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "field_type": field_type,
        "required": required,
        "placeholder": placeholder,
        "help_text": help_text,
        "default_value": default_value,
        "options": options or [],
    }


def _normalize_string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("provider plugin list field must be a list")
    return [str(item).strip() for item in values if str(item).strip()]


def _normalize_field(field: Any, *, path: Path) -> dict[str, Any]:
    if not isinstance(field, dict):
        raise ValueError(f"provider plugin field must be an object: {path}")

    options = field.get("options") or []
    if not isinstance(options, list):
        raise ValueError(f"provider plugin field options must be a list: {path}")

    return {
        "key": str(field["key"]),
        "label": str(field["label"]),
        "field_type": str(field["field_type"]),
        "required": bool(field.get("required", False)),
        "placeholder": str(field["placeholder"]) if field.get("placeholder") is not None else None,
        "help_text": str(field["help_text"]) if field.get("help_text") is not None else None,
        "default_value": field.get("default_value"),
        "options": [
            {
                "label": str(option["label"]),
                "value": str(option["value"]),
            }
            for option in options
            if isinstance(option, dict)
        ],
    }
