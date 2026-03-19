from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.integration import repository as integration_repository
from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance
from app.modules.integration.schemas import IntegrationDiscoveryItemRead, IntegrationDiscoveryListRead
from app.modules.plugin.models import PluginConfigInstance
from app.modules.voice.binding_service import (
    OPEN_XIAOAI_BINDING_PLATFORM,
    OPEN_XIAOAI_PLUGIN_ID,
    VoiceTerminalBindingSnapshot,
    get_voice_terminal_binding,
)

OPEN_XIAOAI_DISCOVERY_TYPE = "speaker_terminal"


def list_integration_discoveries(
    db: Session,
    *,
    household_id: str,
) -> IntegrationDiscoveryListRead:
    rows = integration_repository.list_integration_discoveries(
        db,
        household_id=household_id,
        include_unbound=True,
    )
    items = [
        item
        for item in rows
        if item.household_id == household_id
        or (item.household_id is None and item.plugin_id == OPEN_XIAOAI_PLUGIN_ID)
    ]
    return IntegrationDiscoveryListRead(
        household_id=household_id,
        items=[_to_discovery_read(item) for item in items],
    )


def find_open_xiaoai_instance_by_gateway_id(db: Session, *, gateway_id: str) -> IntegrationInstance | None:
    normalized_gateway_id = gateway_id.strip()
    if not normalized_gateway_id:
        return None

    stmt = select(PluginConfigInstance).where(
        PluginConfigInstance.plugin_id == OPEN_XIAOAI_PLUGIN_ID,
        PluginConfigInstance.scope_type.in_(("plugin", "integration_instance")),
        PluginConfigInstance.integration_instance_id.is_not(None),
    )
    for config in db.scalars(stmt).all():
        payload = load_json(config.data_json)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("gateway_id") or "").strip() != normalized_gateway_id:
            continue
        if not config.integration_instance_id:
            continue
        instance = integration_repository.get_integration_instance(db, config.integration_instance_id)
        if instance is not None:
            return instance
    return None


def upsert_open_xiaoai_discovery(
    db: Session,
    *,
    gateway_id: str,
    fingerprint: str,
    model: str,
    sn: str,
    runtime_version: str,
    capabilities: list[str],
    remote_addr: str | None,
    discovered_at: str | None,
    last_seen_at: str | None,
    connection_status: str,
) -> tuple[IntegrationDiscovery | None, VoiceTerminalBindingSnapshot | None]:
    instance = find_open_xiaoai_instance_by_gateway_id(db, gateway_id=gateway_id)
    binding = get_voice_terminal_binding(db, fingerprint=fingerprint)
    now = utc_now_iso()

    normalized_gateway_id = gateway_id.strip()
    normalized_fingerprint = fingerprint.strip()
    normalized_model = model.strip()
    normalized_sn = sn.strip()
    normalized_runtime_version = runtime_version.strip()
    normalized_capabilities = list(dict.fromkeys(capabilities))
    normalized_discovered_at = discovered_at or now
    normalized_last_seen_at = last_seen_at or now

    payload = {
        "gateway_id": normalized_gateway_id,
        "fingerprint": normalized_fingerprint,
        "model": normalized_model,
        "sn": normalized_sn,
        "runtime_version": normalized_runtime_version,
        "capabilities": normalized_capabilities,
        "remote_addr": remote_addr,
        "connection_status": connection_status,
    }
    title = _build_terminal_title(model=model, sn=sn)
    subtitle = f"网关 {normalized_gateway_id}"

    discovery = integration_repository.get_integration_discovery_by_plugin_and_key(
        db,
        plugin_id=OPEN_XIAOAI_PLUGIN_ID,
        discovery_key=normalized_fingerprint,
    )
    if discovery is None:
        discovery = IntegrationDiscovery(
            id=new_uuid(),
            household_id=(instance.household_id if instance is not None else None),
            integration_instance_id=(instance.id if instance is not None else None),
            plugin_id=OPEN_XIAOAI_PLUGIN_ID,
            gateway_id=normalized_gateway_id,
            discovery_key=normalized_fingerprint,
            discovery_type=OPEN_XIAOAI_DISCOVERY_TYPE,
            resource_type="device",
            status=("claimed" if binding is not None else "pending"),
            title=title,
            subtitle=subtitle,
            external_device_id=normalized_sn,
            external_entity_id=normalized_fingerprint,
            adapter_type=OPEN_XIAOAI_BINDING_PLATFORM,
            capability_tags_json=dump_json(normalized_capabilities) or "[]",
            metadata_json=dump_json(
                {
                    "model": normalized_model,
                    "sn": normalized_sn,
                    "runtime_version": normalized_runtime_version,
                    "remote_addr": remote_addr,
                    "connection_status": connection_status,
                    "gateway_id": normalized_gateway_id,
                }
            )
            or "{}",
            payload_json=dump_json(payload) or "{}",
            claimed_device_id=(binding.terminal_id if binding is not None else None),
            discovered_at=normalized_discovered_at,
            last_seen_at=normalized_last_seen_at,
            created_at=now,
            updated_at=now,
        )
        integration_repository.add_integration_discovery(db, discovery)
        db.flush()
        return discovery, binding

    if instance is not None:
        discovery.household_id = instance.household_id
        discovery.integration_instance_id = instance.id
    discovery.gateway_id = normalized_gateway_id
    discovery.title = title
    discovery.subtitle = subtitle
    discovery.status = "claimed" if binding is not None else "pending"
    discovery.external_device_id = normalized_sn
    discovery.external_entity_id = normalized_fingerprint
    discovery.adapter_type = OPEN_XIAOAI_BINDING_PLATFORM
    discovery.capability_tags_json = dump_json(normalized_capabilities) or "[]"
    discovery.metadata_json = dump_json(
        {
            "model": normalized_model,
            "sn": normalized_sn,
            "runtime_version": normalized_runtime_version,
            "remote_addr": remote_addr,
            "connection_status": connection_status,
            "gateway_id": normalized_gateway_id,
        }
    ) or "{}"
    discovery.payload_json = dump_json(payload) or "{}"
    discovery.claimed_device_id = binding.terminal_id if binding is not None else None
    discovery.discovered_at = normalized_discovered_at if not discovery.discovered_at else discovery.discovered_at
    discovery.last_seen_at = normalized_last_seen_at
    discovery.updated_at = now
    db.add(discovery)
    db.flush()
    return discovery, binding


def list_unbound_open_xiaoai_gateway_ids(db: Session) -> list[str]:
    stmt = (
        select(IntegrationDiscovery.gateway_id)
        .where(
            IntegrationDiscovery.plugin_id == OPEN_XIAOAI_PLUGIN_ID,
            IntegrationDiscovery.integration_instance_id.is_(None),
            IntegrationDiscovery.gateway_id.is_not(None),
        )
        .distinct()
        .order_by(IntegrationDiscovery.gateway_id.asc())
    )
    return [item.strip() for item in db.scalars(stmt).all() if isinstance(item, str) and item.strip()]


def attach_open_xiaoai_discoveries_to_instance(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str,
    gateway_id: str,
) -> None:
    normalized_gateway_id = gateway_id.strip()
    if not normalized_gateway_id:
        return

    stmt = select(IntegrationDiscovery).where(
        IntegrationDiscovery.plugin_id == OPEN_XIAOAI_PLUGIN_ID,
        IntegrationDiscovery.gateway_id == normalized_gateway_id,
    )
    now = utc_now_iso()
    for discovery in db.scalars(stmt).all():
        discovery.household_id = household_id
        discovery.integration_instance_id = integration_instance_id
        discovery.updated_at = now
        db.add(discovery)


def mark_discovery_claimed(
    db: Session,
    *,
    integration_instance_id: str,
    plugin_id: str,
    external_device_id: str | None,
    external_entity_id: str | None,
    device_id: str,
) -> None:
    stmt = select(IntegrationDiscovery).where(
        IntegrationDiscovery.integration_instance_id == integration_instance_id,
        IntegrationDiscovery.plugin_id == plugin_id,
    )
    rows = list(db.scalars(stmt).all())
    now = utc_now_iso()
    normalized_device_id = (external_device_id or "").strip()
    normalized_entity_id = (external_entity_id or "").strip()
    for row in rows:
        if normalized_device_id and row.external_device_id == normalized_device_id:
            row.status = "claimed"
            row.claimed_device_id = device_id
            row.updated_at = now
            db.add(row)
            continue
        if normalized_entity_id and row.external_entity_id == normalized_entity_id:
            row.status = "claimed"
            row.claimed_device_id = device_id
            row.updated_at = now
            db.add(row)


def _to_discovery_read(row: IntegrationDiscovery) -> IntegrationDiscoveryItemRead:
    metadata = load_json(row.metadata_json)
    capability_tags = load_json(row.capability_tags_json)
    return IntegrationDiscoveryItemRead(
        id=row.id,
        household_id=row.household_id,
        plugin_id=row.plugin_id,
        integration_instance_id=row.integration_instance_id,
        discovery_type=row.discovery_type,
        status=row.status,  # type: ignore[arg-type]
        title=row.title,
        subtitle=row.subtitle,
        resource_type=row.resource_type,  # type: ignore[arg-type]
        suggested_room_id=None,
        capability_tags=capability_tags if isinstance(capability_tags, list) else [],
        metadata=metadata if isinstance(metadata, dict) else {},
        discovered_at=row.discovered_at,
        updated_at=row.updated_at,
    )


def _build_terminal_title(*, model: str, sn: str) -> str:
    normalized_model = model.strip() or "小爱音箱"
    normalized_sn = sn.strip()
    if not normalized_sn:
        return normalized_model
    return f"{normalized_model} {normalized_sn[-4:]}"
