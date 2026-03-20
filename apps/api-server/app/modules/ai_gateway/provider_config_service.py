from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import cast

from app.modules.plugin.schemas import PluginRegistryItem
from app.modules.plugin.service import list_registered_plugins
from app.modules.ai_gateway.schemas import (
    AiProviderAdapterRead,
    AiProviderBrandingRead,
    AiProviderConfigActionRead,
    AiProviderConfigFieldUiRead,
    AiProviderConfigSectionRead,
    AiProviderConfigUiRead,
    AiProviderFieldOptionRead,
    AiProviderFieldRead,
    AiProviderModelDiscoveryConfigRead,
    AiProviderConfigVisibilityRuleRead,
)


def list_provider_adapters() -> list[AiProviderAdapterRead]:
    snapshot = list_registered_plugins()
    return list_provider_adapters_from_plugins(snapshot.items)


def list_provider_adapters_from_plugins(plugin_items: list[PluginRegistryItem]) -> list[AiProviderAdapterRead]:
    rows = []
    for item in plugin_items:
        capability = item.capabilities.ai_provider
        if "ai-provider" not in item.types or capability is None:
            continue
        runtime_capability = capability.runtime_capability if isinstance(capability.runtime_capability, dict) else {}
        rows.append(
            {
                "plugin_id": item.id,
                "plugin_name": item.name,
                "adapter_code": capability.adapter_code,
                "display_name": capability.display_name,
                "description": item.compatibility.get("description") if isinstance(item.compatibility, dict) else None,
                "branding": _build_branding_read(item),
                "transport_type": runtime_capability.get("transport_type"),
                "api_family": runtime_capability.get("api_family"),
                "default_privacy_level": runtime_capability.get("default_privacy_level"),
                "default_supported_capabilities": runtime_capability.get("default_supported_capabilities", []),
                "supported_model_types": capability.supported_model_types,
                "llm_workflow": capability.llm_workflow,
                "supports_model_discovery": bool(runtime_capability.get("supports_model_discovery")),
                "field_schema": capability.field_schema,
                "config_ui": _build_config_ui(capability),
                "model_discovery": _build_model_discovery(capability),
            }
        )
    return _build_adapter_reads(rows)


def _build_adapter_reads(rows: list[dict[str, object]]) -> list[AiProviderAdapterRead]:
    return [
        AiProviderAdapterRead(
            plugin_id=str(row["plugin_id"]),
            plugin_name=str(row["plugin_name"]),
            adapter_code=str(row["adapter_code"]),
            display_name=str(row["display_name"]),
            description=str(row.get("description") or row["display_name"]),
            branding=cast(AiProviderBrandingRead, row["branding"]),
            transport_type=str(row["transport_type"]),
            api_family=str(row["api_family"]),
            default_privacy_level=str(row["default_privacy_level"]),
            default_supported_capabilities=list(row.get("default_supported_capabilities", [])),
            supported_model_types=list(row.get("supported_model_types", [])),
            llm_workflow=str(row.get("llm_workflow", row["api_family"])),
            supports_model_discovery=bool(row.get("supports_model_discovery")),
            field_schema=[
                AiProviderFieldRead(
                    key=str(field["key"]),
                    label=str(field["label"]),
                    field_type=str(field["field_type"]),
                    required=bool(field["required"]),
                    placeholder=field.get("placeholder"),
                    help_text=field.get("help_text"),
                    default_value=field.get("default_value"),
                    options=[
                        AiProviderFieldOptionRead(label=str(option["label"]), value=str(option["value"]))
                        for option in field.get("options", [])
                    ],
                )
                for field in list(row["field_schema"])
                if str(field.get("key") or "") != "provider_code"
            ],
            config_ui=cast(AiProviderConfigUiRead, row["config_ui"]),
            model_discovery=cast(AiProviderModelDiscoveryConfigRead, row["model_discovery"]),
        )
        for row in rows
    ]


def _build_branding_read(plugin: PluginRegistryItem) -> AiProviderBrandingRead:
    capability = plugin.capabilities.ai_provider
    assert capability is not None
    branding = capability.branding
    return AiProviderBrandingRead(
        logo_url=_load_data_url(plugin, branding.logo_resource),
        logo_dark_url=_load_data_url(plugin, branding.logo_resource_dark),
        description_locales=_load_description_locales(plugin, branding.description_resource),
    )


def _build_config_ui(capability) -> AiProviderConfigUiRead:
    config_ui = capability.config_ui
    field_order = [key for key in config_ui.field_order if key != "provider_code"]
    hidden_fields = [key for key in config_ui.hidden_fields if key != "provider_code"]
    sections = config_ui.sections
    return AiProviderConfigUiRead(
        field_order=field_order,
        hidden_fields=hidden_fields,
        sections=[
            AiProviderConfigSectionRead(
                key=section.key,
                title=section.title,
                description=section.description,
                fields=[field for field in section.fields if field != "provider_code"],
            )
            for section in sections
        ],
        field_ui={
            key: AiProviderConfigFieldUiRead(
                help_text=value.help_text,
                hidden_when=[
                    AiProviderConfigVisibilityRuleRead(field=rule.field, operator=rule.operator, value=rule.value)
                    for rule in value.hidden_when
                ],
            )
            for key, value in config_ui.field_ui.items()
            if key != "provider_code"
        },
        actions=[
            AiProviderConfigActionRead(
                key=action.key,
                label=action.label,
                description=action.description,
                kind=action.kind,
                placement=action.placement,
                field_key=action.field_key,
            )
            for action in config_ui.actions
            if action.field_key != "provider_code"
        ],
    )


def _build_model_discovery(capability) -> AiProviderModelDiscoveryConfigRead:
    config = capability.model_discovery
    return AiProviderModelDiscoveryConfigRead(
        enabled=config.enabled,
        action_key=config.action_key,
        depends_on_fields=[field for field in config.depends_on_fields if field != "provider_code"],
        target_field=config.target_field,
        debounce_ms=config.debounce_ms,
        empty_state_text=config.empty_state_text,
        discovery_hint_text=config.discovery_hint_text,
        discovering_text=config.discovering_text,
        discovered_text_template=config.discovered_text_template,
    )


def _resolve_plugin_resource_path(plugin: PluginRegistryItem, resource_path: str | None) -> Path | None:
    if not resource_path:
        return None
    manifest_dir = Path(plugin.manifest_path).resolve().parent
    resolved_path = (manifest_dir / resource_path).resolve()
    if manifest_dir not in resolved_path.parents and resolved_path != manifest_dir:
        raise ValueError(f"插件 {plugin.id} 的资源路径越界: {resource_path}")
    return resolved_path


def _load_data_url(plugin: PluginRegistryItem, resource_path: str | None) -> str | None:
    resolved_path = _resolve_plugin_resource_path(plugin, resource_path)
    if resolved_path is None or not resolved_path.exists() or not resolved_path.is_file():
        return None
    mime_type, _ = mimetypes.guess_type(str(resolved_path))
    payload = resolved_path.read_bytes()
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type or 'application/octet-stream'};base64,{encoded}"


def _load_description_locales(plugin: PluginRegistryItem, resource_path: str | None) -> dict[str, str]:
    resolved_path = _resolve_plugin_resource_path(plugin, resource_path)
    if resolved_path is None or not resolved_path.exists() or not resolved_path.is_file():
        return {}
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(payload, str):
        return {"default": payload}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in payload.items():
        normalized_key = str(key).strip()
        normalized_value = str(value).strip()
        if normalized_key and normalized_value:
            result[normalized_key] = normalized_value
    return result
