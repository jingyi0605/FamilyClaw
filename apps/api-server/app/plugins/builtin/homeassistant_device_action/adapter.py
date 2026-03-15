from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.utils import utc_now_iso
from app.modules.device_control.schemas import DeviceControlPluginPayload
from app.modules.ha_integration.client import HomeAssistantClient
from app.modules.ha_integration.models import HouseholdHaConfig

RESULT_SCHEMA_VERSION = "device-control-result.v1"


def parse_payload(raw_payload: dict[str, Any] | None) -> DeviceControlPluginPayload:
    return DeviceControlPluginPayload.model_validate(raw_payload or {})


def build_session_factory(database_url: str) -> tuple[sessionmaker[Session], Any]:
    url = make_url(database_url)
    engine = create_engine(
        database_url,
        future=True,
        connect_args={"check_same_thread": False} if url.get_backend_name() == "sqlite" else {},
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session), engine


def extract_database_url(payload: dict[str, Any]) -> str | None:
    system_context = payload.get("_system_context")
    if not isinstance(system_context, dict):
        return None
    for context_key in ("device_control", "device_integration"):
        context_payload = system_context.get(context_key)
        if not isinstance(context_payload, dict):
            continue
        database_url = context_payload.get("database_url")
        if isinstance(database_url, str) and database_url.strip():
            return database_url.strip()
    return None


def build_home_assistant_client(
    db: Session,
    *,
    household_id: str,
    timeout_seconds: int,
) -> HomeAssistantClient:
    config = db.get(HouseholdHaConfig, household_id)
    base_url = _normalize_optional_text(config.base_url) if config else None
    access_token = _normalize_optional_text(config.access_token) if config else None
    return HomeAssistantClient(
        base_url=base_url,
        token=access_token,
        timeout_seconds=float(timeout_seconds),
    )


def success_result(
    *,
    plugin_id: str,
    action: str,
    external_request: dict[str, Any],
    external_response: dict[str, Any] | list[Any],
    normalized_state_patch: dict[str, Any] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "success": True,
        "platform": "home_assistant",
        "plugin_id": plugin_id,
        "executed_action": action,
        "external_request": external_request,
        "external_response": external_response,
    }
    if normalized_state_patch:
        result["normalized_state_patch"] = normalized_state_patch
    return result


def error_result(*, plugin_id: str, action: str, error_code: str, error_message: str) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "success": False,
        "platform": "home_assistant",
        "plugin_id": plugin_id,
        "executed_action": action,
        "error_code": error_code,
        "error_message": error_message,
    }


def append_last_action_at(patch: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(patch or {})
    result["last_action_at"] = utc_now_iso()
    return result


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalized = value.strip()
    return normalized or None
