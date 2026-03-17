from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationDeviceControlShortcut
from app.modules.device.models import Device, DeviceBinding
from app.modules.device_control.protocol import device_control_protocol_registry


class DeviceShortcutStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    DISABLED = "disabled"


class DeviceShortcutResolutionSource(StrEnum):
    SHORTCUT = "shortcut"
    TOOL_PLANNER = "tool_planner"
    LEGACY_RULE = "legacy_rule"
    MANUAL_SEED = "manual_seed"


_SHORTCUT_SPACE_PATTERN = re.compile(r"\s+")
_SHORTCUT_PUNCTUATION_PATTERN = re.compile(r"[，。！？、；：,.!?;:\"'“”‘’()（）【】\[\]{}<>《》]+")


@dataclass(slots=True)
class DeviceShortcutUpsertPayload:
    household_id: str
    member_id: str | None
    source_text: str
    device_id: str
    entity_id: str
    action: str
    params: dict[str, Any]
    normalized_text: str | None = None
    resolution_source: DeviceShortcutResolutionSource | str = DeviceShortcutResolutionSource.TOOL_PLANNER
    confidence: float | None = None
    status: DeviceShortcutStatus | str = DeviceShortcutStatus.ACTIVE
    hit_count_increment: int = 1


def normalize_device_shortcut_text(text: str) -> str:
    normalized = _SHORTCUT_SPACE_PATTERN.sub("", text.strip().lower())
    normalized = _SHORTCUT_PUNCTUATION_PATTERN.sub("", normalized)
    for token in ("请", "帮我", "给我", "一下", "立刻", "马上", "现在", "麻烦", "把", "将"):
        normalized = normalized.replace(token, "")
    return normalized.strip()


def match_device_shortcut(
    db: Session,
    *,
    household_id: str,
    member_id: str | None,
    source_text: str,
) -> ConversationDeviceControlShortcut | None:
    normalized_text = normalize_device_shortcut_text(source_text)
    if not normalized_text:
        return None
    candidates = conversation_repository.list_device_control_shortcuts_by_phrase(
        db,
        household_id=household_id,
        member_id=member_id,
        normalized_text=normalized_text,
        statuses=[DeviceShortcutStatus.ACTIVE.value],
    )
    for candidate in candidates:
        if _is_shortcut_target_valid(db, shortcut=candidate):
            return candidate
        mark_device_shortcut_status(db, shortcut=candidate, status=DeviceShortcutStatus.STALE)
    return None


def upsert_device_shortcut(
    db: Session,
    *,
    payload: DeviceShortcutUpsertPayload,
) -> ConversationDeviceControlShortcut:
    now = utc_now_iso()
    normalized_text = payload.normalized_text or normalize_device_shortcut_text(payload.source_text)
    existing = conversation_repository.find_device_control_shortcut_for_upsert(
        db,
        household_id=payload.household_id,
        member_id=payload.member_id,
        normalized_text=normalized_text,
        device_id=payload.device_id,
        entity_id=payload.entity_id,
        action=payload.action,
    )
    params_json = dump_json(payload.params or {}) or "{}"
    resolution_source = str(payload.resolution_source)
    status = str(payload.status)
    if existing is not None:
        existing.source_text = payload.source_text
        existing.normalized_text = normalized_text
        existing.params_json = params_json
        existing.resolution_source = resolution_source
        existing.confidence = payload.confidence
        existing.status = status
        existing.hit_count = max(0, existing.hit_count) + max(0, payload.hit_count_increment)
        existing.last_used_at = now
        existing.updated_at = now
        db.add(existing)
        return existing

    shortcut = ConversationDeviceControlShortcut(
        id=new_uuid(),
        household_id=payload.household_id,
        member_id=payload.member_id,
        source_text=payload.source_text,
        normalized_text=normalized_text,
        device_id=payload.device_id,
        entity_id=payload.entity_id,
        action=payload.action,
        params_json=params_json,
        resolution_source=resolution_source,
        confidence=payload.confidence,
        hit_count=max(0, payload.hit_count_increment),
        last_used_at=now,
        status=status,
        created_at=now,
        updated_at=now,
    )
    return conversation_repository.add_device_control_shortcut(db, shortcut)


def touch_device_shortcut_hit(
    db: Session,
    *,
    shortcut: ConversationDeviceControlShortcut,
) -> ConversationDeviceControlShortcut:
    now = utc_now_iso()
    shortcut.hit_count = max(0, shortcut.hit_count) + 1
    shortcut.last_used_at = now
    shortcut.updated_at = now
    shortcut.status = DeviceShortcutStatus.ACTIVE.value
    db.add(shortcut)
    db.flush()
    return shortcut


def mark_device_shortcut_status(
    db: Session,
    *,
    shortcut: ConversationDeviceControlShortcut,
    status: DeviceShortcutStatus | str,
) -> ConversationDeviceControlShortcut:
    normalized_status = str(status)
    if shortcut.status == normalized_status:
        return shortcut
    shortcut.status = normalized_status
    shortcut.updated_at = utc_now_iso()
    db.add(shortcut)
    db.flush()
    return shortcut


def load_device_shortcut_params(shortcut: ConversationDeviceControlShortcut) -> dict[str, Any]:
    loaded = load_json(shortcut.params_json)
    return loaded if isinstance(loaded, dict) else {}


def _is_shortcut_target_valid(
    db: Session,
    *,
    shortcut: ConversationDeviceControlShortcut,
) -> bool:
    device = db.get(Device, shortcut.device_id)
    if device is None:
        return False
    if device.household_id != shortcut.household_id:
        return False
    if device.status != "active" or not bool(device.controllable):
        return False
    try:
        device_control_protocol_registry.validate_action_for_device(
            device_type=device.device_type,
            action=shortcut.action,
            params=load_device_shortcut_params(shortcut),
        )
    except Exception:
        return False
    return _device_has_entity_binding(db, device_id=device.id, entity_id=shortcut.entity_id)


def _device_has_entity_binding(db: Session, *, device_id: str, entity_id: str) -> bool:
    bindings = list(
        db.scalars(
            select(DeviceBinding).where(DeviceBinding.device_id == device_id).order_by(DeviceBinding.id.asc())
        ).all()
    )
    for binding in bindings:
        capabilities = load_json(binding.capabilities)
        if not isinstance(capabilities, dict):
            capabilities = {}
        if _binding_contains_entity_id(binding=binding, capabilities=capabilities, entity_id=entity_id):
            return True
    return False


def _binding_contains_entity_id(
    *,
    binding: DeviceBinding,
    capabilities: dict[str, Any],
    entity_id: str,
) -> bool:
    normalized_entity_id = str(entity_id or "").strip()
    if not normalized_entity_id:
        return False
    for candidate in (
        binding.external_entity_id,
        capabilities.get("primary_entity_id"),
    ):
        if str(candidate or "").strip() == normalized_entity_id:
            return True
    raw_entity_ids = capabilities.get("entity_ids")
    if isinstance(raw_entity_ids, list):
        for candidate in raw_entity_ids:
            if str(candidate or "").strip() == normalized_entity_id:
                return True
    raw_entities = capabilities.get("entities")
    if isinstance(raw_entities, list):
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            if str(raw_entity.get("entity_id") or "").strip() == normalized_entity_id:
                return True
    return False
