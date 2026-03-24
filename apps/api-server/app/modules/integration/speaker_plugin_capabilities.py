from __future__ import annotations

from app.modules.plugin.schemas import PluginRegistryItem

SPEAKER_GATEWAY_CONFIG_FIELD = "gateway_id"


def plugin_uses_speaker_gateway_discovery(plugin: PluginRegistryItem) -> bool:
    config_spec = next(
        (item for item in plugin.config_specs if item.scope_type == "integration_instance"),
        None,
    )
    if config_spec is None:
        config_spec = next(
            (item for item in plugin.config_specs if item.scope_type == "plugin"),
            None,
        )
    if config_spec is None:
        return False

    field_keys = {field.key for field in config_spec.config_schema.fields}
    if SPEAKER_GATEWAY_CONFIG_FIELD not in field_keys:
        return False

    speaker_capability = plugin.capabilities.speaker_adapter
    if speaker_capability is not None and speaker_capability.supports_discovery:
        return True

    integration_capability = plugin.capabilities.integration
    return bool(integration_capability and integration_capability.supports_discovery)
