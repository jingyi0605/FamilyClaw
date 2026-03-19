from __future__ import annotations

from app.plugins.builtin.homeassistant_device_action.adapter import (
    HomeAssistantRuntimeConfigError,
    append_last_action_at,
    build_home_assistant_client,
    error_result,
    parse_action_payload,
    success_result,
)
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClientError
from app.plugins.builtin.homeassistant_device_action.mapper import (
    HomeAssistantActionMappingError,
    build_service_call,
)


ALLOWED_DEVICE_TYPES = {"light", "ac", "curtain", "speaker", "lock"}


def run(payload: dict | None = None) -> dict:
    raw_payload = payload or {}
    plugin_id = str(raw_payload.get("plugin_id") or "homeassistant")
    action = str(raw_payload.get("action") or "turn_on")

    try:
        request = parse_action_payload(raw_payload)
        plugin_id = request.plugin_id
        action = request.action
    except Exception as exc:
        return error_result(
            plugin_id=plugin_id,
            action=action,
            error_code="plugin_internal_error",
            error_message=f"控制 payload 不合法: {exc}",
        )

    try:
        service_call = build_service_call(request, allowed_device_types=ALLOWED_DEVICE_TYPES)
        client = build_home_assistant_client(
            runtime_config=request.runtime_config,
            timeout_seconds=request.timeout_seconds,
        )
        response_payload = client.call_service(
            domain=service_call.domain,
            service=service_call.service,
            data=service_call.service_data,
        )
    except HomeAssistantActionMappingError as exc:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code=exc.error_code,
            error_message=exc.message,
        )
    except HomeAssistantRuntimeConfigError as exc:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="integration_config_invalid",
            error_message=str(exc),
        )
    except HomeAssistantClientError as exc:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code=_map_client_error(str(exc)),
            error_message=str(exc),
        )
    except Exception as exc:
        return error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="plugin_internal_error",
            error_message=str(exc),
        )

    return success_result(
        plugin_id=request.plugin_id,
        action=request.action,
        external_request={
            "domain": service_call.domain,
            "service": service_call.service,
            "entity_id": service_call.entity_id,
            "service_data": service_call.service_data,
        },
        external_response=response_payload,
        normalized_state_patch=append_last_action_at(service_call.normalized_state_patch),
    )


def _map_client_error(message: str) -> str:
    lowered = message.lower()
    if "token" in lowered or "auth" in lowered:
        return "platform_auth_failed"
    if any(
        marker in lowered
        for marker in (
            "connection failed",
            "could not resolve host",
            "failed to establish",
            "name or service not known",
            "temporary failure in name resolution",
            "timed out",
            "timeout",
        )
    ):
        return "platform_unreachable"
    if "invalid json" in lowered:
        return "platform_response_invalid"
    return "platform_request_failed"
