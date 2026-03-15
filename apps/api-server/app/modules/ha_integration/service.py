from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.ha_integration.client import AsyncHomeAssistantClient, HomeAssistantClient
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.service import get_household_or_404


def get_household_ha_config(db: Session, household_id: str) -> HouseholdHaConfig | None:
    return db.get(HouseholdHaConfig, household_id)


def get_home_assistant_config_view(db: Session, household_id: str) -> dict[str, Any]:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    return {
        "household_id": household_id,
        "base_url": _normalize_optional_text(config.base_url) if config else None,
        "token_configured": bool(config and _normalize_optional_text(config.access_token)),
        "sync_rooms_enabled": bool(config.sync_rooms_enabled) if config else False,
        "last_device_sync_at": config.last_device_sync_at if config else None,
        "updated_at": config.updated_at if config else None,
    }


def upsert_household_ha_config(
    db: Session,
    *,
    household_id: str,
    base_url: str | None,
    access_token: str | None,
    clear_access_token: bool,
    sync_rooms_enabled: bool,
) -> HouseholdHaConfig:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    if config is None:
        config = HouseholdHaConfig(household_id=household_id)

    config.base_url = _normalize_optional_text(base_url)
    if clear_access_token:
        config.access_token = None
    elif access_token is not None:
        config.access_token = _normalize_optional_text(access_token)
    config.sync_rooms_enabled = bool(sync_rooms_enabled)
    config.updated_at = utc_now_iso()
    db.add(config)
    db.flush()
    return config


def build_home_assistant_client_for_household(db: Session, household_id: str) -> HomeAssistantClient:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    return HomeAssistantClient(
        base_url=_normalize_optional_text(config.base_url) if config else None,
        token=_normalize_optional_text(config.access_token) if config else None,
    )


def build_async_home_assistant_client_for_household(db: Session, household_id: str) -> AsyncHomeAssistantClient:
    get_household_or_404(db, household_id)
    config = get_household_ha_config(db, household_id)
    return AsyncHomeAssistantClient(
        base_url=_normalize_optional_text(config.base_url) if config else None,
        token=_normalize_optional_text(config.access_token) if config else None,
    )


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
