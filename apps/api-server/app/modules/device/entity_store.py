from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso

from .models import DeviceBinding, DeviceEntity


def list_device_entity_rows(
    db: Session,
    *,
    device_id: str,
) -> list[DeviceEntity]:
    return list(
        db.scalars(
            select(DeviceEntity)
            .where(DeviceEntity.device_id == device_id)
            .order_by(
                DeviceEntity.binding_id.asc(),
                DeviceEntity.sort_order.asc(),
                DeviceEntity.id.asc(),
            )
        ).all()
    )


def list_binding_entity_rows(
    db: Session,
    *,
    binding_id: str,
    ) -> list[DeviceEntity]:
    return list(
        db.scalars(
            select(DeviceEntity)
            .where(DeviceEntity.binding_id == binding_id)
            .order_by(DeviceEntity.sort_order.asc(), DeviceEntity.id.asc())
        ).all()
    )


def list_binding_entity_payloads(
    db: Session,
    *,
    binding: DeviceBinding,
    capabilities: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = list_binding_entity_rows(db, binding_id=binding.id)
    if rows:
        return [build_entity_payload_from_row(row) for row in rows]

    current_capabilities = capabilities or _load_binding_capabilities(binding.capabilities)
    raw_entities = current_capabilities.get("entities")
    if not isinstance(raw_entities, list):
        return []
    return [
        normalized
        for raw_entity in raw_entities
        for normalized in [_normalize_storage_entity_payload(raw_entity)]
        if normalized is not None
    ]


def build_binding_entity_ids(
    db: Session,
    *,
    binding: DeviceBinding,
    capabilities: dict[str, Any] | None = None,
) -> set[str]:
    entity_ids = {
        row.entity_id
        for row in list_binding_entity_rows(db, binding_id=binding.id)
        if row.entity_id.strip()
    }
    if entity_ids:
        return entity_ids
    return _build_legacy_binding_entity_ids(binding=binding, capabilities=capabilities)


def summarize_binding_capabilities(capabilities: dict[str, Any]) -> dict[str, Any]:
    summary = dict(capabilities)
    raw_entities = summary.pop("entities", None)
    if not isinstance(raw_entities, list):
        return summary

    entity_ids: list[str] = []
    for raw_entity in raw_entities:
        normalized = _normalize_storage_entity_payload(raw_entity)
        if normalized is None:
            continue
        entity_id = normalized["entity_id"]
        if entity_id not in entity_ids:
            entity_ids.append(entity_id)

    if entity_ids:
        summary["entity_ids"] = entity_ids
        summary["primary_entity_id"] = _normalize_optional_text(summary.get("primary_entity_id")) or entity_ids[0]
    return summary


def replace_binding_entities_from_capabilities(
    db: Session,
    *,
    binding: DeviceBinding,
    capabilities: dict[str, Any],
) -> list[DeviceEntity]:
    raw_entities = capabilities.get("entities")
    if not isinstance(raw_entities, list):
        return []
    primary_entity_id = _normalize_optional_text(capabilities.get("primary_entity_id"))
    return replace_binding_entities(
        db,
        binding=binding,
        raw_entities=raw_entities,
        primary_entity_id=primary_entity_id,
    )


def replace_binding_entities(
    db: Session,
    *,
    binding: DeviceBinding,
    raw_entities: list[Any],
    primary_entity_id: str | None = None,
) -> list[DeviceEntity]:
    existing_rows = list_binding_entity_rows(db, binding_id=binding.id)
    existing_map = {row.entity_id: row for row in existing_rows}
    next_entity_ids: set[str] = set()
    rows: list[DeviceEntity] = []

    for sort_order, raw_entity in enumerate(raw_entities):
        normalized = _normalize_storage_entity_payload(raw_entity)
        if normalized is None:
            continue
        entity_id = normalized["entity_id"]
        next_entity_ids.add(entity_id)
        row = existing_map.get(entity_id)
        if row is None:
            row = DeviceEntity(
                id=new_uuid(),
                device_id=binding.device_id,
                binding_id=binding.id,
                integration_instance_id=binding.integration_instance_id,
                entity_id=entity_id,
                created_at=utc_now_iso(),
            )
        row.integration_instance_id = binding.integration_instance_id
        row.name = normalized["name"]
        row.domain = normalized["domain"]
        row.state = normalized["state"]
        row.state_display = normalized["state_display"]
        row.unit = normalized["unit"]
        row.control = normalized["control"]
        row.metadata_payload = normalized["metadata"]
        row.is_primary = 1 if entity_id == primary_entity_id else 0
        row.sort_order = sort_order
        row.updated_at = normalized["updated_at"]
        db.add(row)
        rows.append(row)

    for row in existing_rows:
        if row.entity_id not in next_entity_ids:
            db.delete(row)

    return rows


def update_binding_entity_state_snapshot(
    db: Session,
    *,
    binding: DeviceBinding,
    resolved_entity_id: str,
    patch: dict[str, Any],
) -> bool:
    row = db.scalar(
        select(DeviceEntity).where(
            DeviceEntity.binding_id == binding.id,
            DeviceEntity.entity_id == resolved_entity_id,
        )
    )
    if row is None:
        return False

    changed = False
    state_value = _normalize_optional_text(patch.get("state"))
    if state_value is not None:
        row.state = state_value
        row.state_display = _friendly_state_display(state_value)
        changed = True

    if "value" in patch:
        control = row.control
        if isinstance(control, dict):
            control["value"] = patch.get("value")
            row.control = control
            changed = True

    if not changed:
        return False

    row.updated_at = utc_now_iso()
    db.add(row)
    return True


def build_entity_payload_from_row(row: DeviceEntity) -> dict[str, Any]:
    return {
        "entity_id": row.entity_id,
        "name": row.name,
        "domain": row.domain,
        "state": row.state,
        "state_display": row.state_display,
        "unit": row.unit,
        "metadata": row.metadata_payload,
        "control": row.control,
        "updated_at": row.updated_at,
    }


def _normalize_storage_entity_payload(raw_entity: Any) -> dict[str, Any] | None:
    if not isinstance(raw_entity, dict):
        return None
    entity_id = _normalize_optional_text(raw_entity.get("entity_id"))
    if entity_id is None:
        return None
    state = _normalize_optional_text(raw_entity.get("state")) or "unknown"
    return {
        "entity_id": entity_id,
        "name": _normalize_optional_text(raw_entity.get("name")) or entity_id,
        "domain": _normalize_optional_text(raw_entity.get("domain")) or entity_id.split(".", 1)[0],
        "state": state,
        "state_display": _normalize_optional_text(raw_entity.get("state_display")) or _friendly_state_display(state),
        "unit": _normalize_optional_text(raw_entity.get("unit")),
        "metadata": raw_entity.get("metadata") if isinstance(raw_entity.get("metadata"), dict) else {},
        "control": raw_entity.get("control") if isinstance(raw_entity.get("control"), dict) else {"kind": "none"},
        "updated_at": _normalize_optional_text(raw_entity.get("updated_at")) or utc_now_iso(),
    }


def _build_legacy_binding_entity_ids(
    *,
    binding: DeviceBinding,
    capabilities: dict[str, Any] | None = None,
) -> set[str]:
    current_capabilities = capabilities or _load_binding_capabilities(binding.capabilities)
    entity_ids: set[str] = set()
    for candidate in (
        binding.external_entity_id,
        current_capabilities.get("primary_entity_id"),
    ):
        normalized = _normalize_optional_text(candidate)
        if normalized:
            entity_ids.add(normalized)
    raw_entity_ids = current_capabilities.get("entity_ids")
    if isinstance(raw_entity_ids, list):
        for candidate in raw_entity_ids:
            normalized = _normalize_optional_text(candidate)
            if normalized:
                entity_ids.add(normalized)
    raw_entities = current_capabilities.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            normalized = _normalize_optional_text(raw_entity.get("entity_id"))
            if normalized:
                entity_ids.add(normalized)
    return entity_ids


def _load_binding_capabilities(raw_value: str | None) -> dict[str, Any]:
    loaded = load_json(raw_value)
    return loaded if isinstance(loaded, dict) else {}


def _friendly_state_display(state: str) -> str:
    mapping = {
        "on": "开启",
        "off": "关闭",
        "open": "打开",
        "closed": "关闭",
        "locked": "已上锁",
        "unlocked": "未上锁",
        "playing": "播放中",
        "paused": "已暂停",
        "idle": "空闲",
        "cool": "制冷",
        "heat": "制热",
        "auto": "自动",
        "dry": "除湿",
        "fan_only": "送风",
        "unavailable": "离线",
        "unknown": "未知",
    }
    normalized = state.strip().lower()
    return mapping.get(normalized, state.strip() or "未知")


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
