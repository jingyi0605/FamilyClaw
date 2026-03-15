from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.utils import utc_now_iso
from app.modules.device.models import Device
from app.modules.device_control.schemas import DeviceControlPluginPayload
from app.modules.ha_integration.client import HomeAssistantClientError
from app.modules.ha_integration.service import execute_home_assistant_device_action


def run_legacy_homeassistant_action(payload: dict | None = None) -> dict:
    raw_payload = payload or {}
    try:
        request = DeviceControlPluginPayload.model_validate(raw_payload)
    except Exception as exc:
        return _error_result(
            plugin_id=str((raw_payload or {}).get("plugin_id") or "unknown-plugin"),
            action=str((raw_payload or {}).get("action") or "turn_on"),
            error_code="plugin_internal_error",
            error_message=f"控制 payload 不合法: {exc}",
        )

    database_url = _extract_database_url(raw_payload)
    if not database_url:
        return _error_result(
            plugin_id=request.plugin_id,
            action=request.action,
            error_code="plugin_internal_error",
            error_message="缺少插件运行时数据库上下文",
        )

    session_factory, engine = _build_session_factory(database_url)
    try:
        with session_factory() as db:
            device = db.get(Device, request.device_snapshot.id)
            if device is None:
                return _error_result(
                    plugin_id=request.plugin_id,
                    action=request.action,
                    error_code="platform_target_not_found",
                    error_message="本地设备不存在",
                )
            try:
                execution = execute_home_assistant_device_action(
                    db,
                    household_id=request.household_id,
                    device=device,
                    action=request.action,
                    params=_to_legacy_params(action=request.action, params=request.params),
                )
                db.commit()
            except HomeAssistantClientError as exc:
                db.rollback()
                return _error_result(
                    plugin_id=request.plugin_id,
                    action=request.action,
                    error_code="platform_request_failed",
                    error_message=str(exc),
                )
            except ValueError as exc:
                db.rollback()
                return _error_result(
                    plugin_id=request.plugin_id,
                    action=request.action,
                    error_code=_map_value_error_to_code(str(exc)),
                    error_message=str(exc),
                )

            return {
                "schema_version": "device-control-result.v1",
                "success": True,
                "platform": execution.platform,
                "plugin_id": request.plugin_id,
                "executed_action": request.action,
                "external_request": {
                    "domain": execution.service_domain,
                    "service": execution.service_name,
                    "entity_id": execution.entity_id,
                    "service_data": execution.params,
                },
                "external_response": execution.response_payload,
                "normalized_state_patch": {
                    "status": "active",
                    "last_action_at": utc_now_iso(),
                },
            }
    finally:
        engine.dispose()


def _build_session_factory(database_url: str) -> tuple[sessionmaker[Session], Any]:
    url = make_url(database_url)
    engine = create_engine(
        database_url,
        future=True,
        connect_args={"check_same_thread": False} if url.get_backend_name() == "sqlite" else {},
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session), engine


def _extract_database_url(payload: dict[str, Any]) -> str | None:
    system_context = payload.get("_system_context")
    if not isinstance(system_context, dict):
        return None
    device_control_context = system_context.get("device_control")
    if not isinstance(device_control_context, dict):
        return None
    database_url = device_control_context.get("database_url")
    if not isinstance(database_url, str) or not database_url.strip():
        return None
    return database_url.strip()


def _to_legacy_params(*, action: str, params: dict[str, Any]) -> dict[str, Any]:
    if action == "set_brightness":
        return {"brightness": params.get("brightness_pct")}
    if action == "set_temperature":
        return {"temperature": params.get("temperature_c")}
    if action == "set_hvac_mode":
        return {"hvac_mode": params.get("hvac_mode")}
    if action == "set_volume":
        volume_pct = params.get("volume_pct")
        return {"volume": float(volume_pct) / 100 if isinstance(volume_pct, (int, float)) else volume_pct}
    return {}


def _map_value_error_to_code(message: str) -> str:
    lowered = message.lower()
    if "binding not found" in lowered or "entity id not found" in lowered:
        return "platform_target_not_found"
    if "unsupported action" in lowered or "does not support action" in lowered:
        return "action_not_supported_by_platform"
    return "plugin_internal_error"


def _error_result(*, plugin_id: str, action: str, error_code: str, error_message: str) -> dict:
    return {
        "schema_version": "device-control-result.v1",
        "success": False,
        "platform": "home_assistant",
        "plugin_id": plugin_id,
        "executed_action": action,
        "error_code": error_code,
        "error_message": error_message,
    }
