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
_SHORTCUT_PUNCTUATION_PATTERN = re.compile(r"[\W_]+", re.UNICODE)
_SHORTCUT_FILLER_TOKENS = ("请", "帮我", "给我", "一下", "立刻", "马上", "现在", "麻烦", "把", "将")
_SHORTCUT_SEMANTIC_MIN_SCORE = 24
_SHORTCUT_SEMANTIC_MIN_MARGIN = 8
_SHORTCUT_DEVICE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "light": ("灯", "灯光", "照明"),
    "ac": ("空调", "冷气"),
    "speaker": ("音箱", "音响", "小爱"),
    "curtain": ("窗帘",),
    "lock": ("门锁",),
}
_SHORTCUT_ACTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "unlock": ("确认解锁", "解锁"),
    "lock": ("锁上", "上锁", "锁门"),
    "stop": ("停止", "停下"),
}


@dataclass(frozen=True, slots=True)
class _SemanticShortcutMatch:
    shortcut: ConversationDeviceControlShortcut
    score: int


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
    for token in _SHORTCUT_FILLER_TOKENS:
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
    matched = _select_first_valid_shortcut(db, candidates=candidates)
    if matched is not None:
        return matched
    return _match_device_shortcut_semantically(
        db,
        household_id=household_id,
        member_id=member_id,
        source_text=source_text,
        normalized_text=normalized_text,
    )


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


def _select_first_valid_shortcut(
    db: Session,
    *,
    candidates: list[ConversationDeviceControlShortcut] | tuple[ConversationDeviceControlShortcut, ...],
) -> ConversationDeviceControlShortcut | None:
    for candidate in candidates:
        if _is_shortcut_target_valid(db, shortcut=candidate):
            return candidate
        mark_device_shortcut_status(db, shortcut=candidate, status=DeviceShortcutStatus.STALE)
    return None


def _match_device_shortcut_semantically(
    db: Session,
    *,
    household_id: str,
    member_id: str | None,
    source_text: str,
    normalized_text: str,
) -> ConversationDeviceControlShortcut | None:
    candidates = conversation_repository.list_device_control_shortcuts(
        db,
        household_id=household_id,
        member_id=member_id,
        statuses=[DeviceShortcutStatus.ACTIVE.value],
    )
    matches: list[_SemanticShortcutMatch] = []
    for candidate in candidates:
        if candidate.normalized_text == normalized_text:
            continue
        if not _is_shortcut_target_valid(db, shortcut=candidate):
            mark_device_shortcut_status(db, shortcut=candidate, status=DeviceShortcutStatus.STALE)
            continue
        score = _score_semantic_shortcut_match(db, shortcut=candidate, source_text=source_text)
        if score < _SHORTCUT_SEMANTIC_MIN_SCORE:
            continue
        matches.append(_SemanticShortcutMatch(shortcut=candidate, score=score))
    if not matches:
        return None
    matches.sort(
        key=lambda item: (
            -item.score,
            -max(0, item.shortcut.hit_count),
            item.shortcut.last_used_at or "",
            item.shortcut.created_at,
        )
    )
    best = matches[0]
    best_destination = (best.shortcut.device_id, best.shortcut.entity_id, best.shortcut.action)
    same_score_destinations = {
        (item.shortcut.device_id, item.shortcut.entity_id, item.shortcut.action)
        for item in matches[1:]
        if item.score == best.score
    }
    if same_score_destinations and best_destination not in same_score_destinations:
        return None
    if len(matches) > 1:
        second = matches[1]
        second_destination = (second.shortcut.device_id, second.shortcut.entity_id, second.shortcut.action)
        if best.score - second.score < _SHORTCUT_SEMANTIC_MIN_MARGIN and best_destination != second_destination:
            return None
    return best.shortcut


def _score_semantic_shortcut_match(
    db: Session,
    *,
    shortcut: ConversationDeviceControlShortcut,
    source_text: str,
) -> int:
    device = db.get(Device, shortcut.device_id)
    if device is None:
        return 0
    requested_device_types = _infer_requested_device_types(source_text)
    normalized_device_type = _normalize_device_type(device.device_type)
    if requested_device_types and normalized_device_type not in requested_device_types:
        return 0
    requested_target_text = _build_semantic_target_text(
        source_text,
        action=shortcut.action,
        device_type=normalized_device_type,
    )
    if not requested_target_text:
        return 0
    target_texts = _collect_shortcut_target_texts(
        db,
        shortcut=shortcut,
        device=device,
        device_type=normalized_device_type,
    )
    if not target_texts:
        return 0
    return max(_score_target_overlap(requested_target_text, candidate_text) for candidate_text in target_texts)


def _collect_shortcut_target_texts(
    db: Session,
    *,
    shortcut: ConversationDeviceControlShortcut,
    device: Device,
    device_type: str,
) -> list[str]:
    texts: list[str] = []
    for raw_text in (
        _build_semantic_target_text(shortcut.source_text, action=shortcut.action, device_type=device_type),
        normalize_device_shortcut_text(device.name),
    ):
        if raw_text and raw_text not in texts:
            texts.append(raw_text)
    for binding in _list_device_bindings(db, device_id=device.id):
        capabilities = load_json(binding.capabilities)
        if not isinstance(capabilities, dict):
            continue
        raw_entities = capabilities.get("entities")
        if not isinstance(raw_entities, list):
            continue
        for raw_entity in raw_entities:
            if not isinstance(raw_entity, dict):
                continue
            if str(raw_entity.get("entity_id") or "").strip() != shortcut.entity_id:
                continue
            normalized_name = normalize_device_shortcut_text(str(raw_entity.get("name") or ""))
            if normalized_name and normalized_name not in texts:
                texts.append(normalized_name)
    return texts


def _infer_requested_device_types(text: str) -> set[str]:
    normalized = normalize_device_shortcut_text(text)
    if not normalized:
        return set()
    matched_types: set[str] = set()
    for device_type, keywords in _SHORTCUT_DEVICE_TYPE_KEYWORDS.items():
        if any(normalize_device_shortcut_text(keyword) in normalized for keyword in keywords):
            matched_types.add(device_type)
    return matched_types


def _build_semantic_target_text(text: str, *, action: str, device_type: str) -> str:
    normalized = normalize_device_shortcut_text(text)
    if not normalized:
        return ""
    stripped = normalized
    removed = False
    for keyword in _get_action_keywords_for_device(action=action, device_type=device_type):
        normalized_keyword = normalize_device_shortcut_text(keyword)
        if not normalized_keyword or normalized_keyword not in stripped:
            continue
        stripped = stripped.replace(normalized_keyword, "")
        removed = True
    if not removed:
        return ""
    return stripped.strip()


def _get_action_keywords_for_device(*, action: str, device_type: str) -> tuple[str, ...]:
    if action in _SHORTCUT_ACTION_KEYWORDS:
        return _SHORTCUT_ACTION_KEYWORDS[action]
    if action == "open":
        return ("拉开", "打开") if device_type == "curtain" else ("拉开",)
    if action == "close":
        return ("拉上", "合上", "关闭") if device_type == "curtain" else ("拉上", "合上")
    if action == "turn_on":
        keywords = ["开启", "开一下", "开", "点亮"]
        if device_type != "curtain":
            keywords.append("打开")
        return tuple(keywords)
    if action == "turn_off":
        keywords = ["关掉", "关上", "关", "熄灭"]
        if device_type != "curtain":
            keywords.append("关闭")
        return tuple(keywords)
    return (action,)


def _score_target_overlap(requested_text: str, candidate_text: str) -> int:
    if not requested_text or not candidate_text:
        return 0
    if requested_text == candidate_text:
        return 100
    if requested_text in candidate_text or candidate_text in requested_text:
        return 80 + min(len(requested_text), len(candidate_text)) * 2 - abs(len(requested_text) - len(candidate_text))
    requested_tokens = set(_build_ngram_tokens(requested_text))
    candidate_tokens = set(_build_ngram_tokens(candidate_text))
    token_overlap = len(requested_tokens & candidate_tokens)
    char_overlap = len(set(requested_text) & set(candidate_text))
    if token_overlap == 0 and char_overlap < 2:
        return 0
    return token_overlap * 18 + char_overlap * 4


def _build_ngram_tokens(text: str) -> list[str]:
    if len(text) <= 1:
        return [text] if text else []
    return [text[index : index + 2] for index in range(len(text) - 1)]


def _normalize_device_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"air_conditioner", "airconditioner"}:
        return "ac"
    return normalized


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


def _list_device_bindings(db: Session, *, device_id: str) -> list[DeviceBinding]:
    return list(
        db.scalars(
            select(DeviceBinding).where(DeviceBinding.device_id == device_id).order_by(DeviceBinding.id.asc())
        ).all()
    )


def _device_has_entity_binding(db: Session, *, device_id: str, entity_id: str) -> bool:
    bindings = _list_device_bindings(db, device_id=device_id)
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
