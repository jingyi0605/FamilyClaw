from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.db.engine import build_database_engine
from app.modules.device_control.schemas import DeviceControlPluginPayload
from app.modules.device_integration.schemas import IntegrationSyncPluginPayload

DEVICE_CONTROL_RESULT_SCHEMA_VERSION = "device-control-result.v1"


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


def parse_integration_payload(raw_payload: dict[str, Any] | None) -> IntegrationSyncPluginPayload:
    return IntegrationSyncPluginPayload.model_validate(raw_payload or {})


def parse_action_payload(raw_payload: dict[str, Any] | None) -> DeviceControlPluginPayload:
    return DeviceControlPluginPayload.model_validate(raw_payload or {})


def success_result(
    *,
    plugin_id: str,
    action: str,
    external_request: dict[str, Any],
    external_response: dict[str, Any] | list[Any],
    normalized_state_patch: dict[str, Any] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": DEVICE_CONTROL_RESULT_SCHEMA_VERSION,
        "success": True,
        "platform": "open_xiaoai",
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
        "schema_version": DEVICE_CONTROL_RESULT_SCHEMA_VERSION,
        "success": False,
        "platform": "open_xiaoai",
        "plugin_id": plugin_id,
        "executed_action": action,
        "error_code": error_code,
        "error_message": error_message,
    }


def run_speaker_adapter(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """正式 speaker_adapter 入口。

    这一层先只作为契约占位，明确 open_xiaoai_speaker 属于 audio_session 车道。
    具体厂商 runtime 细节仍留在插件内部，不回灌宿主核心。
    """

    raw_payload = payload or {}
    return {
        "accepted": True,
        "plugin_id": str(raw_payload.get("plugin_id") or "open-xiaoai-speaker"),
        "mode": "audio_session",
        "payload_kind": str(raw_payload.get("kind") or "speaker_adapter"),
    }
