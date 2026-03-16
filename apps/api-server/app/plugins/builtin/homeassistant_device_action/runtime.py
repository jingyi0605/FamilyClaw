from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import load_json, utc_now_iso
from app.modules.integration import repository as integration_repository
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin.config_crypto import decrypt_plugin_config_secrets
from app.modules.plugin.service import PluginServiceError
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClient


HOME_ASSISTANT_PLUGIN_ID = "homeassistant"


@dataclass(slots=True)
class HomeAssistantRuntimeConfig:
    integration_instance_id: str
    household_id: str
    base_url: str | None
    access_token: str | None
    sync_rooms_enabled: bool
    last_synced_at: str | None
    updated_at: str | None


def get_home_assistant_runtime_config(
    db: Session,
    *,
    integration_instance_id: str,
) -> HomeAssistantRuntimeConfig:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None or instance.plugin_id != HOME_ASSISTANT_PLUGIN_ID:
        raise PluginServiceError(
            f"Home Assistant 实例不存在: {integration_instance_id}",
            error_code="integration_instance_not_found",
            field="integration_instance_id",
            status_code=404,
        )

    config_instance = plugin_repository.get_plugin_config_instance_for_integration_instance(
        db,
        integration_instance_id=integration_instance_id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        scope_type="plugin",
    )
    if config_instance is None:
        raise PluginServiceError(
            "Home Assistant 实例还没有完成配置。",
            error_code="integration_config_invalid",
            field="integration_instance_id",
            status_code=400,
        )

    loaded = load_json(config_instance.data_json)
    payload = loaded if isinstance(loaded, dict) else {}
    payload.update(decrypt_plugin_config_secrets(config_instance.secret_data_encrypted))
    return HomeAssistantRuntimeConfig(
        integration_instance_id=integration_instance_id,
        household_id=instance.household_id,
        base_url=_normalize_optional_text(payload.get("base_url")),
        access_token=_normalize_optional_text(payload.get("access_token")),
        sync_rooms_enabled=bool(payload.get("sync_rooms_enabled")),
        last_synced_at=instance.last_synced_at,
        updated_at=config_instance.updated_at,
    )


def build_home_assistant_client_for_instance(
    db: Session,
    *,
    integration_instance_id: str,
    timeout_seconds: float | None = None,
) -> HomeAssistantClient:
    config = get_home_assistant_runtime_config(db, integration_instance_id=integration_instance_id)
    return HomeAssistantClient(
        base_url=config.base_url,
        token=config.access_token,
        timeout_seconds=timeout_seconds,
    )


def mark_home_assistant_instance_sync_succeeded(db: Session, *, integration_instance_id: str) -> None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None:
        return
    instance.status = "active"
    instance.last_synced_at = utc_now_iso()
    instance.last_error_code = None
    instance.last_error_message = None
    instance.updated_at = utc_now_iso()
    db.add(instance)


def mark_home_assistant_instance_sync_failed(
    db: Session,
    *,
    integration_instance_id: str,
    error_code: str,
    error_message: str,
) -> None:
    instance = integration_repository.get_integration_instance(db, integration_instance_id)
    if instance is None:
        return
    instance.status = "degraded"
    instance.last_error_code = error_code
    instance.last_error_message = error_message
    instance.updated_at = utc_now_iso()
    db.add(instance)


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
