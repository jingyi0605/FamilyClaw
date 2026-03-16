from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import build_database_engine
from app.db.utils import utc_now_iso
from app.modules.device_control.schemas import DeviceControlPluginPayload
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClient
from app.plugins.builtin.homeassistant_device_action.runtime import build_home_assistant_client_for_instance

RESULT_SCHEMA_VERSION = "device-control-result.v1"


def parse_payload(raw_payload: dict[str, Any] | None) -> DeviceControlPluginPayload:
    return DeviceControlPluginPayload.model_validate(raw_payload or {})


def build_session_factory(database_url: str) -> tuple[sessionmaker[Session], Any]:
    engine = build_database_engine(database_url)
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
    integration_instance_id: str,
    timeout_seconds: int,
) -> HomeAssistantClient:
    return build_home_assistant_client_for_instance(
        db,
        integration_instance_id=integration_instance_id,
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
