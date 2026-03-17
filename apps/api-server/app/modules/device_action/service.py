from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.device.service import get_device_or_404
from app.modules.device.schemas import DeviceRead
from app.modules.device_action.schemas import DeviceActionExecuteRequest, DeviceActionExecuteResponse
from app.modules.device_control.schemas import DeviceControlRequest
from app.modules.device_control.service import (
    DeviceControlServiceError,
    aexecute_device_control,
    execute_device_control,
)
from app.modules.device_control.protocol import device_control_protocol_registry


# 语音快路径需要按设备类型快速判断哪些动作必须拦截确认。
HIGH_RISK_ACTIONS: dict[str, set[str]] = {}
for definition in device_control_protocol_registry.list_definitions():
    if definition.risk_level != "high":
        continue
    for device_type in definition.supported_device_types:
        HIGH_RISK_ACTIONS.setdefault(device_type, set()).add(definition.action)


@dataclass
class DeviceActionAuditContext:
    details: dict


def _build_response(*, db: Session, payload: DeviceActionExecuteRequest, execution) -> DeviceActionExecuteResponse:
    device = get_device_or_404(db, payload.device_id)
    external_request = execution.external_request if isinstance(execution.external_request, dict) else {}
    return DeviceActionExecuteResponse(
        household_id=payload.household_id,
        device=DeviceRead.model_validate(device),
        action=payload.action,
        platform=execution.platform,
        service_domain=str(external_request.get("domain") or ""),
        service_name=str(external_request.get("service") or ""),
        entity_id=str(execution.resolved_entity_id or external_request.get("entity_id") or ""),
        params=execution.params,
        result="success",
        executed_at=utc_now_iso(),
    )


def _build_audit_context(*, payload: DeviceActionExecuteRequest, execution) -> DeviceActionAuditContext:
    return DeviceActionAuditContext(
        details={
            "reason": payload.reason,
            "confirm_high_risk": payload.confirm_high_risk,
            "idempotency_key": payload.idempotency_key,
            "requested_entity_id": payload.entity_id,
            "resolved_entity_id": execution.resolved_entity_id,
            "plugin_id": execution.plugin_id,
            "platform": execution.platform,
            "action": execution.action,
            "params": execution.params,
            "external_request": execution.external_request,
            "external_response": execution.external_response,
            "normalized_state_patch": execution.normalized_state_patch,
        }
    )


def _translate_control_error(exc: DeviceControlServiceError) -> HTTPException:
    detail: str | dict[str, str] = exc.message
    if exc.error_code in {
        "plugin_result_invalid",
        "plugin_execution_failed",
        "plugin_execution_timeout",
        "plugin_not_visible_in_household",
        "plugin_disabled",
        "high_risk_confirmation_required",
        "device_binding_missing",
        "invalid_action_params",
        "action_not_supported",
        "device_not_controllable",
        "device_disabled",
        "platform_unreachable",
        "permission_denied",
    }:
        detail = exc.to_detail()
    return HTTPException(status_code=exc.status_code, detail=detail)


def execute_device_action(
    db: Session,
    *,
    payload: DeviceActionExecuteRequest,
) -> tuple[DeviceActionExecuteResponse, DeviceActionAuditContext]:
    try:
        execution = execute_device_control(
            db,
            request=DeviceControlRequest(
                household_id=payload.household_id,
                device_id=payload.device_id,
                entity_id=payload.entity_id,
                action=payload.action,
                params=payload.params,
                reason=payload.reason,
                confirm_high_risk=payload.confirm_high_risk,
                idempotency_key=payload.idempotency_key,
            ),
        )
    except DeviceControlServiceError as exc:
        raise _translate_control_error(exc) from exc

    return _build_response(db=db, payload=payload, execution=execution), _build_audit_context(
        payload=payload,
        execution=execution,
    )


async def aexecute_device_action(
    db: Session,
    *,
    payload: DeviceActionExecuteRequest,
) -> tuple[DeviceActionExecuteResponse, DeviceActionAuditContext]:
    try:
        execution = await aexecute_device_control(
            db,
            request=DeviceControlRequest(
                household_id=payload.household_id,
                device_id=payload.device_id,
                entity_id=payload.entity_id,
                action=payload.action,
                params=payload.params,
                reason=payload.reason,
                confirm_high_risk=payload.confirm_high_risk,
                idempotency_key=payload.idempotency_key,
            ),
        )
    except DeviceControlServiceError as exc:
        raise _translate_control_error(exc) from exc

    return _build_response(db=db, payload=payload, execution=execution), _build_audit_context(
        payload=payload,
        execution=execution,
    )
