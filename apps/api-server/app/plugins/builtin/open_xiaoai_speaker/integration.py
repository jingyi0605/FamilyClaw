from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.utils import load_json
from app.modules.integration.models import IntegrationDiscovery
from app.plugins.builtin.open_xiaoai_speaker.runtime import (
    build_session_factory,
    extract_database_url,
    parse_integration_payload,
)


def sync(payload: dict | None = None) -> dict:
    raw_payload = payload or {}
    try:
        request = parse_integration_payload(raw_payload)
    except Exception as exc:
        return _plugin_error_result(
            plugin_id=str(raw_payload.get("plugin_id") or "open-xiaoai-speaker"),
            reason=f"接入 payload 不合法: {exc}",
        )

    database_url = extract_database_url(raw_payload)
    if not database_url:
        return _plugin_error_result(
            plugin_id=request.plugin_id,
            reason="缺少插件运行时数据库上下文",
        )

    session_factory, engine = build_session_factory(database_url)
    try:
        with session_factory() as db:
            discoveries = _load_discoveries(db, integration_instance_id=request.integration_instance_id)
            selected_ids = {item.strip() for item in request.selected_external_ids if item.strip()}
            device_candidates: list[dict[str, Any]] = []
            devices: list[dict[str, Any]] = []

            for discovery in discoveries:
                if selected_ids and (discovery.external_device_id or "") not in selected_ids:
                    continue
                metadata = _load_payload_dict(discovery.metadata_json)
                capability_tags = _load_text_list(discovery.capability_tags_json)
                candidate = {
                    "external_device_id": discovery.external_device_id or discovery.discovery_key,
                    "primary_entity_id": discovery.external_entity_id or discovery.discovery_key,
                    "name": discovery.title,
                    "room_name": None,
                    "device_type": "speaker",
                    "entity_count": 1,
                }
                if request.sync_scope == "device_candidates":
                    device_candidates.append(candidate)
                    continue
                if request.sync_scope != "device_sync":
                    continue
                devices.append(
                    {
                        **candidate,
                        "controllable": True,
                        "status": _map_status(str(metadata.get("connection_status") or "unknown")),
                        "capabilities": {
                            "vendor_code": "xiaomi",
                            "adapter_type": metadata.get("adapter_type") or "open_xiaoai",
                            "gateway_id": metadata.get("gateway_id"),
                            "model": metadata.get("model"),
                            "sn": metadata.get("sn"),
                            "runtime_version": metadata.get("runtime_version"),
                            "connection_status": metadata.get("connection_status"),
                            "last_seen_at": discovery.last_seen_at,
                            "capability_tags": capability_tags,
                        },
                    }
                )

            return {
                "schema_version": "integration-sync-result.v1",
                "plugin_id": request.plugin_id,
                "platform": "open_xiaoai",
                "device_candidates": device_candidates if request.sync_scope == "device_candidates" else [],
                "room_candidates": [],
                "devices": devices if request.sync_scope == "device_sync" else [],
                "rooms": [],
                "failures": [],
                "records": [],
            }
    finally:
        engine.dispose()


def _load_discoveries(db, *, integration_instance_id: str) -> list[IntegrationDiscovery]:
    stmt = (
        select(IntegrationDiscovery)
        .where(
            IntegrationDiscovery.integration_instance_id == integration_instance_id,
            IntegrationDiscovery.plugin_id == "open-xiaoai-speaker",
        )
        .order_by(IntegrationDiscovery.updated_at.desc(), IntegrationDiscovery.id.desc())
    )
    return list(db.scalars(stmt).all())


def _load_payload_dict(raw_value: str | None) -> dict[str, Any]:
    loaded = load_json(raw_value)
    return loaded if isinstance(loaded, dict) else {}


def _load_text_list(raw_value: str | None) -> list[str]:
    loaded = load_json(raw_value)
    if not isinstance(loaded, list):
        return []
    return [str(item).strip() for item in loaded if str(item).strip()]


def _plugin_error_result(*, plugin_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "integration-sync-result.v1",
        "plugin_id": plugin_id,
        "platform": "open_xiaoai",
        "device_candidates": [],
        "room_candidates": [],
        "devices": [],
        "rooms": [],
        "failures": [{"external_ref": None, "reason": reason}],
        "records": [],
    }


def _map_status(connection_status: str) -> str:
    if connection_status == "online":
        return "active"
    if connection_status == "offline":
        return "offline"
    return "inactive"
