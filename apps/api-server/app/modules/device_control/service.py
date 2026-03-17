from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.utils import load_json, new_uuid, utc_now_iso
from app.modules.device.models import Device
from app.modules.device.service import get_device_or_404, update_binding_entity_state
from app.modules.device_control.protocol import DeviceControlProtocolError, device_control_protocol_registry
from app.modules.device_control.router import DevicePluginRoutingError, route_device_plugin
from app.modules.device_control.schemas import (
    DeviceControlBindingSnapshot,
    DeviceControlDeviceSnapshot,
    DeviceControlExecutionResult,
    DeviceControlPluginPayload,
    DeviceControlPluginResult,
    DeviceControlRequest,
)
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginServiceError,
    aexecute_household_plugin,
    execute_household_plugin,
    require_available_household_plugin,
)


class DeviceControlServiceError(ValueError):
    def __init__(self, message: str, *, error_code: str, status_code: int, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.field = field

    def to_detail(self) -> dict[str, str]:
        payload = {
            "detail": self.message,
            "error_code": self.error_code,
            "timestamp": utc_now_iso(),
        }
        if self.field is not None:
            payload["field"] = self.field
        return payload


def _ensure_device_belongs_to_household(device: Device, household_id: str) -> None:
    if device.household_id != household_id:
        raise DeviceControlServiceError(
            "device must belong to the same household",
            error_code="permission_denied",
            status_code=400,
            field="household_id",
        )


def _ensure_device_controllable(device: Device) -> None:
    if not bool(device.controllable):
        raise DeviceControlServiceError(
            "device is not controllable",
            error_code="device_not_controllable",
            status_code=400,
            field="device_id",
        )


def _ensure_device_enabled(device: Device) -> None:
    if device.status == "disabled":
        raise DeviceControlServiceError(
            "device has been disabled",
            error_code="device_disabled",
            status_code=409,
            field="device_id",
        )


def _ensure_high_risk_confirmed(*, action: str, confirm_high_risk: bool) -> None:
    if device_control_protocol_registry.is_high_risk(action) and not confirm_high_risk:
        raise DeviceControlServiceError(
            "high risk action requires confirmation",
            error_code="high_risk_confirmation_required",
            status_code=403,
            field="confirm_high_risk",
        )


def _translate_protocol_error(exc: DeviceControlProtocolError) -> DeviceControlServiceError:
    status_code = 400
    if exc.error_code == "action_not_supported":
        status_code = 400
    return DeviceControlServiceError(
        exc.message,
        error_code=exc.error_code,
        status_code=status_code,
        field=exc.field,
    )


def _translate_router_error(exc: DevicePluginRoutingError) -> DeviceControlServiceError:
    return DeviceControlServiceError(
        exc.message,
        error_code=exc.error_code,
        status_code=409,
        field=exc.field,
    )


def _translate_plugin_error(exc: PluginServiceError) -> DeviceControlServiceError:
    return DeviceControlServiceError(
        exc.detail,
        error_code=exc.error_code,
        status_code=exc.status_code,
        field=exc.field,
    )


def _build_database_url(db: Session) -> str | None:
    bind = db.get_bind()
    if hasattr(bind, "url"):
        return _render_database_url(bind.url)
    engine = getattr(bind, "engine", None)
    if engine is not None and hasattr(engine, "url"):
        return _render_database_url(engine.url)
    return None


def _render_database_url(url: Any) -> str:
    if hasattr(url, "render_as_string"):
        return url.render_as_string(hide_password=False)
    return str(url)


def _build_payload(
    *,
    db: Session,
    request: DeviceControlRequest,
    device: Device,
    plugin_id: str,
    route_binding,
    risk_level: str,
    normalized_params: dict[str, Any],
    timeout_seconds: int,
) -> DeviceControlPluginPayload:
    capabilities = load_json(route_binding.capabilities)
    if not isinstance(capabilities, dict):
        capabilities = {}
    database_url = _build_database_url(db)

    payload = DeviceControlPluginPayload(
        request_id=request.idempotency_key or new_uuid(),
        household_id=request.household_id,
        plugin_id=plugin_id,
        binding=DeviceControlBindingSnapshot(
            binding_id=route_binding.id,
            integration_instance_id=route_binding.integration_instance_id,
            platform=route_binding.platform,
            plugin_id=plugin_id,
            external_device_id=route_binding.external_device_id,
            external_entity_id=route_binding.external_entity_id,
            capabilities=capabilities,
            binding_version=route_binding.binding_version,
        ),
        device_snapshot=DeviceControlDeviceSnapshot(
            id=device.id,
            name=device.name,
            device_type=device.device_type,
            status=device.status,
            controllable=bool(device.controllable),
            room_id=device.room_id,
        ),
        target_entity_id=request.entity_id,
        action=request.action,
        params=normalized_params,
        timeout_seconds=timeout_seconds,
        reason=request.reason,
        risk_level=risk_level,
        idempotency_key=request.idempotency_key,
        system_context={"device_control": {"database_url": database_url}} if database_url else None,
    )
    return payload


def _apply_normalized_state_patch(db: Session, *, device: Device, patch: dict[str, Any] | None) -> None:
    if not isinstance(patch, dict):
        return
    status_value = patch.get("status")
    if isinstance(status_value, str) and status_value.strip():
        device.status = status_value.strip()
        db.add(device)


def _translate_execution_failure(error_code: str | None, error_message: str | None) -> DeviceControlServiceError:
    normalized_error_code = error_code or "plugin_execution_failed"
    message = error_message or "插件执行失败"
    status_code = 502
    if normalized_error_code in {"plugin_not_visible_in_household", "plugin_disabled", "plugin_not_available"}:
        status_code = 409
    elif normalized_error_code == "platform_unreachable":
        status_code = 503
        message = "device platform is unreachable"
    elif normalized_error_code == "plugin_type_not_supported":
        status_code = 400
    elif normalized_error_code == "plugin_execution_timeout":
        status_code = 504
    return DeviceControlServiceError(message, error_code=normalized_error_code, status_code=status_code)


def _finalize_execution(
    *,
    db: Session,
    request: DeviceControlRequest,
    device: Device,
    plugin_id: str,
    route_binding,
    risk_level: str,
    execution_output: Any,
    request_id: str,
    normalized_params: dict[str, Any],
) -> DeviceControlExecutionResult:
    try:
        plugin_result = DeviceControlPluginResult.model_validate(execution_output or {})
    except ValidationError as exc:
        raise DeviceControlServiceError(
            f"插件返回结果不合法: {exc.errors()[0].get('msg', 'unknown error')}",
            error_code="plugin_result_invalid",
            status_code=502,
        ) from exc

    if plugin_result.plugin_id != plugin_id:
        raise DeviceControlServiceError(
            "插件返回的 plugin_id 和路由结果不一致",
            error_code="plugin_result_invalid",
            status_code=502,
            field="plugin_id",
        )
    if plugin_result.executed_action != request.action:
        raise DeviceControlServiceError(
            "插件返回的动作和请求不一致",
            error_code="plugin_result_invalid",
            status_code=502,
            field="action",
        )
    if not plugin_result.success:
        raise _translate_execution_failure(plugin_result.error_code, plugin_result.error_message)

    _apply_normalized_state_patch(db, device=device, patch=plugin_result.normalized_state_patch)
    external_request = plugin_result.external_request if isinstance(plugin_result.external_request, dict) else {}
    resolved_entity_id = external_request.get("entity_id") if isinstance(external_request.get("entity_id"), str) else None
    update_binding_entity_state(
        db,
        binding=route_binding,
        resolved_entity_id=resolved_entity_id,
        patch=plugin_result.normalized_state_patch,
    )

    return DeviceControlExecutionResult(
        request_id=request_id,
        household_id=request.household_id,
        device_id=device.id,
        action=request.action,
        params=normalized_params,
        plugin_id=plugin_id,
        platform=plugin_result.platform,
        risk_level=risk_level,
        resolved_entity_id=resolved_entity_id,
        external_request=plugin_result.external_request,
        external_response=plugin_result.external_response,
        normalized_state_patch=plugin_result.normalized_state_patch,
    )


def execute_device_control(db: Session, *, request: DeviceControlRequest) -> DeviceControlExecutionResult:
    device = get_device_or_404(db, request.device_id)
    _ensure_device_belongs_to_household(device, request.household_id)
    _ensure_device_enabled(device)
    _ensure_device_controllable(device)

    try:
        definition, normalized_params = device_control_protocol_registry.validate_action_for_device(
            device_type=device.device_type,
            action=request.action,
            params=request.params,
        )
        _ensure_high_risk_confirmed(action=request.action, confirm_high_risk=request.confirm_high_risk)
        route = route_device_plugin(db, device=device, requested_entity_id=request.entity_id)
        plugin = require_available_household_plugin(
            db,
            household_id=request.household_id,
            plugin_id=route.plugin_id,
            plugin_type="action",
        )
    except DeviceControlProtocolError as exc:
        raise _translate_protocol_error(exc) from exc
    except DevicePluginRoutingError as exc:
        raise _translate_router_error(exc) from exc
    except PluginServiceError as exc:
        raise _translate_plugin_error(exc) from exc

    timeout_seconds = plugin.runner_config.timeout_seconds if plugin.runner_config is not None else 8
    payload = _build_payload(
        db=db,
        request=request,
        device=device,
        plugin_id=route.plugin_id,
        route_binding=route.binding,
        risk_level=definition.risk_level,
        normalized_params=normalized_params,
        timeout_seconds=timeout_seconds,
    )

    execution = execute_household_plugin(
        db,
        household_id=request.household_id,
        request=PluginExecutionRequest(
            plugin_id=route.plugin_id,
            plugin_type="action",
            payload=_serialize_plugin_payload(payload),
            trigger="device-control",
        ),
    )
    if not execution.success:
        raise _translate_execution_failure(execution.error_code, execution.error_message)

    return _finalize_execution(
        db=db,
        request=request,
        device=device,
        plugin_id=route.plugin_id,
        route_binding=route.binding,
        risk_level=definition.risk_level,
        execution_output=execution.output,
        request_id=payload.request_id,
        normalized_params=normalized_params,
    )


async def aexecute_device_control(db: Session, *, request: DeviceControlRequest) -> DeviceControlExecutionResult:
    device = get_device_or_404(db, request.device_id)
    _ensure_device_belongs_to_household(device, request.household_id)
    _ensure_device_enabled(device)
    _ensure_device_controllable(device)

    try:
        definition, normalized_params = device_control_protocol_registry.validate_action_for_device(
            device_type=device.device_type,
            action=request.action,
            params=request.params,
        )
        _ensure_high_risk_confirmed(action=request.action, confirm_high_risk=request.confirm_high_risk)
        route = route_device_plugin(db, device=device, requested_entity_id=request.entity_id)
        plugin = require_available_household_plugin(
            db,
            household_id=request.household_id,
            plugin_id=route.plugin_id,
            plugin_type="action",
        )
    except DeviceControlProtocolError as exc:
        raise _translate_protocol_error(exc) from exc
    except DevicePluginRoutingError as exc:
        raise _translate_router_error(exc) from exc
    except PluginServiceError as exc:
        raise _translate_plugin_error(exc) from exc

    timeout_seconds = plugin.runner_config.timeout_seconds if plugin.runner_config is not None else 8
    payload = _build_payload(
        db=db,
        request=request,
        device=device,
        plugin_id=route.plugin_id,
        route_binding=route.binding,
        risk_level=definition.risk_level,
        normalized_params=normalized_params,
        timeout_seconds=timeout_seconds,
    )

    execution = await aexecute_household_plugin(
        db,
        household_id=request.household_id,
        request=PluginExecutionRequest(
            plugin_id=route.plugin_id,
            plugin_type="action",
            payload=_serialize_plugin_payload(payload),
            trigger="device-control",
        ),
    )
    if not execution.success:
        raise _translate_execution_failure(execution.error_code, execution.error_message)

    return _finalize_execution(
        db=db,
        request=request,
        device=device,
        plugin_id=route.plugin_id,
        route_binding=route.binding,
        risk_level=definition.risk_level,
        execution_output=execution.output,
        request_id=payload.request_id,
        normalized_params=normalized_params,
    )


def _serialize_plugin_payload(payload: DeviceControlPluginPayload) -> dict[str, Any]:
    payload_dict = payload.model_dump(mode="json", by_alias=True)
    if payload.system_context is not None:
        payload_dict["_system_context"] = payload.system_context
    return payload_dict
