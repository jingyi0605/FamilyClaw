from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.device.models import Device
from app.modules.device.schemas import DeviceRead
from app.modules.device.service import get_device_or_404
from app.modules.device_action.schemas import DeviceActionExecuteRequest, DeviceActionExecuteResponse
from app.modules.device_control.protocol import device_control_protocol_registry
from app.modules.ha_integration.client import HomeAssistantClient, HomeAssistantClientError
from app.modules.ha_integration.service import async_execute_home_assistant_device_action, execute_home_assistant_device_action

HIGH_RISK_ACTIONS: dict[str, set[str]] = {}
for definition in device_control_protocol_registry.list_definitions():
    if definition.risk_level != "high":
        continue
    for device_type in definition.supported_device_types:
        HIGH_RISK_ACTIONS.setdefault(device_type, set()).add(definition.action)


@dataclass
class DeviceActionAuditContext:
    details: dict


def _ensure_device_belongs_to_household(device: Device, household_id: str) -> None:
    if device.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device must belong to the same household",
        )


def _ensure_device_controllable(device: Device) -> None:
    if not bool(device.controllable):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device is not controllable",
        )


def _ensure_action_supported_for_device(device: Device, action: str) -> None:
    allowed_actions: dict[str, set[str]] = {
        "light": {"turn_on", "turn_off", "set_brightness"},
        "ac": {"turn_on", "turn_off", "set_temperature", "set_hvac_mode"},
        "curtain": {"open", "close", "stop"},
        "speaker": {"turn_on", "turn_off", "play_pause", "set_volume"},
        "lock": {"lock", "unlock"},
    }

    if action not in allowed_actions.get(device.device_type, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action is not supported for current device type",
        )


def _ensure_high_risk_action_confirmed(payload: DeviceActionExecuteRequest, device: Device) -> None:
    if payload.action in HIGH_RISK_ACTIONS.get(device.device_type, set()) and not payload.confirm_high_risk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="high risk action requires confirmation",
        )


def execute_device_action(
    db: Session,
    *,
    payload: DeviceActionExecuteRequest,
    client: HomeAssistantClient | None = None,
) -> tuple[DeviceActionExecuteResponse, DeviceActionAuditContext]:
    device = get_device_or_404(db, payload.device_id)
    _ensure_device_belongs_to_household(device, payload.household_id)
    _ensure_device_controllable(device)
    _ensure_action_supported_for_device(device, payload.action)
    _ensure_high_risk_action_confirmed(payload, device)

    try:
        execution = execute_home_assistant_device_action(
            db,
            household_id=payload.household_id,
            device=device,
            action=payload.action,
            params=payload.params,
            client=client,
        )
    except HomeAssistantClientError:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    response = DeviceActionExecuteResponse(
        household_id=payload.household_id,
        device=DeviceRead.model_validate(device),
        action=payload.action,
        platform=execution.platform,
        service_domain=execution.service_domain,
        service_name=execution.service_name,
        entity_id=execution.entity_id,
        params=execution.params,
        result="success",
        executed_at=utc_now_iso(),
    )
    audit_context = DeviceActionAuditContext(
        details={
            "reason": payload.reason,
            "confirm_high_risk": payload.confirm_high_risk,
            "platform": execution.platform,
            "service_domain": execution.service_domain,
            "service_name": execution.service_name,
            "entity_id": execution.entity_id,
            "params": execution.params,
            "response_payload": execution.response_payload,
        }
    )
    return response, audit_context


async def aexecute_device_action(
    db: Session,
    *,
    payload: DeviceActionExecuteRequest,
) -> tuple[DeviceActionExecuteResponse, DeviceActionAuditContext]:
    device = get_device_or_404(db, payload.device_id)
    _ensure_device_belongs_to_household(device, payload.household_id)
    _ensure_device_controllable(device)
    _ensure_action_supported_for_device(device, payload.action)
    _ensure_high_risk_action_confirmed(payload, device)

    try:
        execution = await async_execute_home_assistant_device_action(
            db,
            household_id=payload.household_id,
            device=device,
            action=payload.action,
            params=payload.params,
        )
    except HomeAssistantClientError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response = DeviceActionExecuteResponse(
        household_id=payload.household_id,
        device=DeviceRead.model_validate(device),
        action=payload.action,
        platform=execution.platform,
        service_domain=execution.service_domain,
        service_name=execution.service_name,
        entity_id=execution.entity_id,
        params=execution.params,
        result="success",
        executed_at=utc_now_iso(),
    )
    audit_context = DeviceActionAuditContext(
        details={
            "reason": payload.reason,
            "confirm_high_risk": payload.confirm_high_risk,
            "platform": execution.platform,
            "service_domain": execution.service_domain,
            "service_name": execution.service_name,
            "entity_id": execution.entity_id,
            "params": execution.params,
            "response_payload": execution.response_payload,
        }
    )
    return response, audit_context
