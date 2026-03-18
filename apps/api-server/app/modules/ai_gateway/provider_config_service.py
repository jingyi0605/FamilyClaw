from __future__ import annotations

from app.modules.plugin.schemas import PluginRegistryItem
from app.modules.plugin.service import list_registered_plugins
from app.modules.ai_gateway.schemas import (
    AiProviderAdapterRead,
    AiProviderFieldOptionRead,
    AiProviderFieldRead,
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
                "transport_type": runtime_capability.get("transport_type"),
                "api_family": runtime_capability.get("api_family"),
                "default_privacy_level": runtime_capability.get("default_privacy_level"),
                "default_supported_capabilities": runtime_capability.get("default_supported_capabilities", []),
                "supported_model_types": capability.supported_model_types,
                "llm_workflow": capability.llm_workflow,
                "field_schema": capability.field_schema,
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
            transport_type=str(row["transport_type"]),
            api_family=str(row["api_family"]),
            default_privacy_level=str(row["default_privacy_level"]),
            default_supported_capabilities=list(row.get("default_supported_capabilities", [])),
            supported_model_types=list(row.get("supported_model_types", [])),
            llm_workflow=str(row.get("llm_workflow", row["api_family"])),
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
            ],
        )
        for row in rows
    ]
