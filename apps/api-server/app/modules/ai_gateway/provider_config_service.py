from __future__ import annotations

from app.modules.ai_gateway.provider_adapter_registry import list_provider_adapters as list_registered_provider_adapters
from app.modules.ai_gateway.schemas import (
    AiProviderAdapterRead,
    AiProviderFieldOptionRead,
    AiProviderFieldRead,
)


def list_provider_adapters() -> list[AiProviderAdapterRead]:
    rows = list_registered_provider_adapters()
    return [
        AiProviderAdapterRead(
            plugin_id=row["plugin_id"],
            plugin_name=row["plugin_name"],
            adapter_code=row["adapter_code"],
            display_name=row["display_name"],
            description=row["description"],
            transport_type=row["transport_type"],
            api_family=row["api_family"],
            default_privacy_level=row["default_privacy_level"],
            default_supported_capabilities=row["default_supported_capabilities"],
            supported_model_types=row.get("supported_model_types", []),
            llm_workflow=row.get("llm_workflow", row["api_family"]),
            field_schema=[
                AiProviderFieldRead(
                    key=field["key"],
                    label=field["label"],
                    field_type=field["field_type"],
                    required=field["required"],
                    placeholder=field.get("placeholder"),
                    help_text=field.get("help_text"),
                    default_value=field.get("default_value"),
                    options=[
                        AiProviderFieldOptionRead(label=option["label"], value=option["value"])
                        for option in field.get("options", [])
                    ],
                )
                for field in row["field_schema"]
            ],
        )
        for row in rows
    ]
