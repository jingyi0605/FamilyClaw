from __future__ import annotations

from typing import Any

from app.db.utils import utc_now_iso
from app.modules.device_control.schemas import DeviceControlPluginPayload
from app.modules.device_integration.schemas import IntegrationSyncPluginPayload
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClient


RESULT_SCHEMA_VERSION = "device-control-result.v1"


class HomeAssistantRuntimeConfigError(ValueError):
    pass


def parse_action_payload(raw_payload: dict[str, Any] | None) -> DeviceControlPluginPayload:
    return DeviceControlPluginPayload.model_validate(raw_payload or {})


def parse_integration_payload(raw_payload: dict[str, Any] | None) -> IntegrationSyncPluginPayload:
    return IntegrationSyncPluginPayload.model_validate(raw_payload or {})


def build_home_assistant_client(
    *,
    runtime_config: dict[str, Any] | None,
    timeout_seconds: int | float,
) -> HomeAssistantClient:
    payload = runtime_config if isinstance(runtime_config, dict) else {}
    base_url = _normalize_optional_text(payload.get("base_url"))
    access_token = _normalize_optional_text(payload.get("access_token"))
    if not base_url or not access_token:
        raise HomeAssistantRuntimeConfigError("Home Assistant 实例配置未完成。")
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
