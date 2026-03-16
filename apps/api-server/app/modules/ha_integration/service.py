from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import load_json, utc_now_iso
from app.modules.ha_integration.client import AsyncHomeAssistantClient, HomeAssistantClient
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.service import get_household_or_404

HOME_ASSISTANT_PLUGIN_ID = "homeassistant"
HOME_ASSISTANT_SCOPE_TYPE = "plugin"
HOME_ASSISTANT_SCOPE_KEY = "default"


@dataclass(slots=True)
class HomeAssistantRuntimeConfig:
    household_id: str
    base_url: str | None
    access_token: str | None
    sync_rooms_enabled: bool
    last_device_sync_at: str | None
    updated_at: str | None
    source: str


def get_household_ha_config(db: Session, household_id: str) -> HouseholdHaConfig | None:
    return db.get(HouseholdHaConfig, household_id)


def get_home_assistant_runtime_config(db: Session, household_id: str) -> HomeAssistantRuntimeConfig | None:
    get_household_or_404(db, household_id)
    plugin_payload = _load_homeassistant_plugin_payload(db, household_id=household_id)
    if plugin_payload is not None:
        legacy = get_household_ha_config(db, household_id)
        return HomeAssistantRuntimeConfig(
            household_id=household_id,
            base_url=_normalize_optional_text(plugin_payload.get("base_url")),
            access_token=_normalize_optional_text(plugin_payload.get("access_token")),
            sync_rooms_enabled=bool(plugin_payload.get("sync_rooms_enabled")),
            last_device_sync_at=(legacy.last_device_sync_at if legacy else None),
            updated_at=_resolve_runtime_updated_at(legacy),
            source="plugin_config",
        )

    legacy = get_household_ha_config(db, household_id)
    if legacy is None:
        return None
    return HomeAssistantRuntimeConfig(
        household_id=household_id,
        base_url=_normalize_optional_text(legacy.base_url),
        access_token=_normalize_optional_text(legacy.access_token),
        sync_rooms_enabled=bool(legacy.sync_rooms_enabled),
        last_device_sync_at=legacy.last_device_sync_at,
        updated_at=legacy.updated_at,
        source="legacy_table",
    )


def get_home_assistant_config_view(db: Session, household_id: str) -> dict[str, Any]:
    runtime_config = get_home_assistant_runtime_config(db, household_id)
    return {
        "household_id": household_id,
        "base_url": (runtime_config.base_url if runtime_config else None),
        "token_configured": bool(runtime_config and runtime_config.access_token),
        "sync_rooms_enabled": bool(runtime_config.sync_rooms_enabled) if runtime_config else False,
        "last_device_sync_at": (runtime_config.last_device_sync_at if runtime_config else None),
        "updated_at": (runtime_config.updated_at if runtime_config else None),
    }


def upsert_household_ha_config(
    db: Session,
    *,
    household_id: str,
    base_url: str | None,
    access_token: str | None,
    clear_access_token: bool,
    sync_rooms_enabled: bool,
    updated_by: str | None = None,
) -> HouseholdHaConfig:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    if config is None:
        config = HouseholdHaConfig(household_id=household_id)

    normalized_base_url = _normalize_optional_text(base_url)
    normalized_access_token = _normalize_optional_text(access_token)

    config.base_url = normalized_base_url
    if clear_access_token:
        config.access_token = None
    elif access_token is not None:
        config.access_token = normalized_access_token
    config.sync_rooms_enabled = bool(sync_rooms_enabled)
    config.updated_at = utc_now_iso()
    db.add(config)
    db.flush()

    _save_homeassistant_plugin_config(
        db,
        household_id=household_id,
        base_url=normalized_base_url,
        access_token=normalized_access_token,
        clear_access_token=clear_access_token,
        sync_rooms_enabled=sync_rooms_enabled,
        updated_by=updated_by,
    )
    return config


def sync_legacy_homeassistant_config_from_plugin_values(
    db: Session,
    *,
    household_id: str,
    values: dict[str, Any],
    secret_fields: dict[str, Any],
    secret_data: dict[str, Any],
) -> HouseholdHaConfig:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    if config is None:
        config = HouseholdHaConfig(household_id=household_id)

    config.base_url = _normalize_optional_text(values.get("base_url"))
    config.sync_rooms_enabled = bool(values.get("sync_rooms_enabled"))
    if secret_fields.get("access_token", {}).get("has_value"):
        config.access_token = _normalize_optional_text(secret_data.get("access_token"))
    else:
        config.access_token = None
    config.updated_at = utc_now_iso()
    db.add(config)
    db.flush()
    return config


def load_homeassistant_plugin_fallback_payload(
    db: Session,
    *,
    household_id: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    if config is None:
        return {}, {}, False

    data_payload = {
        "base_url": _normalize_optional_text(config.base_url),
        "sync_rooms_enabled": bool(config.sync_rooms_enabled),
    }
    secret_payload = {}
    if _normalize_optional_text(config.access_token):
        secret_payload["access_token"] = _normalize_optional_text(config.access_token)
    return data_payload, secret_payload, bool(data_payload["base_url"] or secret_payload or data_payload["sync_rooms_enabled"])


def record_home_assistant_device_sync(db: Session, *, household_id: str) -> None:
    runtime_config = get_home_assistant_runtime_config(db, household_id)
    if runtime_config is None:
        return

    config = get_household_ha_config(db, household_id)
    if config is None:
        config = HouseholdHaConfig(household_id=household_id)

    config.base_url = runtime_config.base_url
    config.access_token = runtime_config.access_token
    config.sync_rooms_enabled = runtime_config.sync_rooms_enabled
    config.last_device_sync_at = utc_now_iso()
    config.updated_at = utc_now_iso()
    db.add(config)
    db.flush()


def build_home_assistant_client_for_household(
    db: Session,
    household_id: str,
    *,
    timeout_seconds: float | None = None,
) -> HomeAssistantClient:
    runtime_config = get_home_assistant_runtime_config(db, household_id)
    return HomeAssistantClient(
        base_url=(runtime_config.base_url if runtime_config else None),
        token=(runtime_config.access_token if runtime_config else None),
        timeout_seconds=timeout_seconds,
    )


def build_async_home_assistant_client_for_household(
    db: Session,
    household_id: str,
    *,
    timeout_seconds: float | None = None,
) -> AsyncHomeAssistantClient:
    runtime_config = get_home_assistant_runtime_config(db, household_id)
    return AsyncHomeAssistantClient(
        base_url=(runtime_config.base_url if runtime_config else None),
        token=(runtime_config.access_token if runtime_config else None),
        timeout_seconds=timeout_seconds,
    )


def _save_homeassistant_plugin_config(
    db: Session,
    *,
    household_id: str,
    base_url: str | None,
    access_token: str | None,
    clear_access_token: bool,
    sync_rooms_enabled: bool,
    updated_by: str | None,
) -> None:
    from app.modules.plugin.config_service import save_plugin_config_form
    from app.modules.plugin.schemas import PluginConfigUpdateRequest

    values: dict[str, Any] = {
        "base_url": base_url,
        "sync_rooms_enabled": bool(sync_rooms_enabled),
    }
    if access_token is not None:
        values["access_token"] = access_token

    save_plugin_config_form(
        db,
        household_id=household_id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        payload=PluginConfigUpdateRequest(
            scope_type=HOME_ASSISTANT_SCOPE_TYPE,
            scope_key=HOME_ASSISTANT_SCOPE_KEY,
            values=values,
            clear_secret_fields=(["access_token"] if clear_access_token else []),
        ),
        updated_by=updated_by,
    )


def _load_homeassistant_plugin_payload(
    db: Session,
    *,
    household_id: str,
) -> dict[str, Any] | None:
    from app.modules.plugin import repository as plugin_repository
    from app.modules.plugin.config_crypto import decrypt_plugin_config_secrets

    instance = plugin_repository.get_plugin_config_instance(
        db,
        household_id=household_id,
        plugin_id=HOME_ASSISTANT_PLUGIN_ID,
        scope_type=HOME_ASSISTANT_SCOPE_TYPE,
        scope_key=HOME_ASSISTANT_SCOPE_KEY,
    )
    if instance is None:
        return None

    loaded_data = load_json(instance.data_json)
    data_payload = loaded_data if isinstance(loaded_data, dict) else {}
    payload = dict(data_payload)
    payload.update(decrypt_plugin_config_secrets(instance.secret_data_encrypted))
    payload["updated_at"] = instance.updated_at
    return payload


def _resolve_runtime_updated_at(config: HouseholdHaConfig | None) -> str | None:
    if config is None:
        return None
    return config.updated_at


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
