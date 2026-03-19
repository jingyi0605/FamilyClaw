from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.config_crypto import encrypt_plugin_config_secrets
from app.modules.plugin.models import PluginConfigInstance


HOME_ASSISTANT_PLUGIN_ID = "homeassistant"


def seed_homeassistant_integration_instance(
    db: Session,
    *,
    household_id: str,
    display_name: str = "Home Assistant",
    base_url: str = "http://ha.local:8123",
    access_token: str = "demo-token",
    sync_rooms_enabled: bool = True,
    status: str = "active",
) -> IntegrationInstance:
    now = utc_now_iso()
    instance = IntegrationInstance(
        id=new_uuid(),
        household_id=household_id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        display_name=display_name,
        status=status,
        last_synced_at=None,
        last_error_code=None,
        last_error_message=None,
        created_at=now,
        updated_at=now,
    )
    config = PluginConfigInstance(
        id=new_uuid(),
        household_id=household_id,
        integration_instance_id=instance.id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        scope_type="integration_instance",
        scope_key=instance.id,
        schema_version=1,
        data_json=(
            dump_json(
                {
                    "base_url": base_url,
                    "sync_rooms_enabled": sync_rooms_enabled,
                }
            )
            or "{}"
        ),
        secret_data_encrypted=encrypt_plugin_config_secrets({"access_token": access_token}),
        updated_by="test",
        created_at=now,
        updated_at=now,
    )
    db.add(instance)
    db.add(config)
    db.flush()
    return instance


def build_homeassistant_sync_payload(
    *,
    household_id: str,
    integration_instance_id: str,
    sync_scope: str = "device_sync",
    selected_external_ids: list[str] | None = None,
) -> dict:
    return {
        "household_id": household_id,
        "plugin_id": HOME_ASSISTANT_PLUGIN_ID,
        "integration_instance_id": integration_instance_id,
        "sync_scope": sync_scope,
        "selected_external_ids": selected_external_ids or [],
        "options": {},
        "runtime_config": {
            "base_url": "http://ha.local:8123",
            "access_token": "demo-token",
            "sync_rooms_enabled": True,
        },
    }


def mock_homeassistant_registry_payloads():
    return patch.multiple(
        "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient",
        get_device_registry=lambda self: [
            {
                "id": "ha-device-light-1",
                "name": "客厅主灯",
                "name_by_user": None,
                "manufacturer": "Philips",
                "model": "Hue",
                "area_id": "area-living-room",
            }
        ],
        get_entity_registry=lambda self: [
            {
                "entity_id": "light.living_room_main",
                "device_id": "ha-device-light-1",
                "area_id": "area-living-room",
                "name": "客厅主灯",
                "original_name": "Living Room Main",
                "disabled_by": None,
            }
        ],
        get_area_registry=lambda self: [{"area_id": "area-living-room", "name": "客厅"}],
        get_states=lambda self: [
            {
                "entity_id": "light.living_room_main",
                "state": "on",
                "attributes": {"friendly_name": "客厅主灯", "area_name": "客厅"},
                "last_updated": "2026-03-15T12:00:00Z",
            },
            {
                "entity_id": "sensor.living_room_temperature",
                "state": "23.5",
                "attributes": {"unit_of_measurement": "°C"},
                "last_updated": "2026-03-15T12:00:00Z",
            },
            {
                "entity_id": "sensor.living_room_humidity",
                "state": "48",
                "attributes": {"unit_of_measurement": "%", "device_class": "humidity"},
                "last_updated": "2026-03-15T12:00:00Z",
            },
        ],
    )
