from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.account.service import AuthenticatedActor
from app.modules.agent.service import resolve_effective_agent
from app.modules.scheduler.schemas import (
    ScheduledTaskDefinitionCreate,
    ScheduledTaskDraftConfirmRequest,
    ScheduledTaskDraftFromConversationRequest,
    ScheduledTaskDraftRead,
)
from app.modules.scheduler.service import create_task_definition


@dataclass
class DraftRecord:
    draft_id: str
    household_id: str
    creator_account_id: str
    owner_scope: str | None
    owner_member_id: str | None
    intent_summary: str
    missing_fields: list[str]
    draft_payload: dict[str, object]
    status: str


_DRAFT_STORE: dict[str, DraftRecord] = {}


def create_draft_from_conversation(
    db: Session,
    *,
    actor: AuthenticatedActor,
    payload: ScheduledTaskDraftFromConversationRequest,
) -> ScheduledTaskDraftRead:
    if actor.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot create draft for another household")
    record = _DRAFT_STORE.get(payload.draft_id or "") if payload.draft_id else None
    parsed = _parse_text_to_draft(db, actor=actor, household_id=payload.household_id, text=payload.text, existing=record)
    _DRAFT_STORE[parsed.draft_id] = parsed
    return _to_draft_read(parsed)


def confirm_draft_from_conversation(
    db: Session,
    *,
    actor: AuthenticatedActor,
    draft_id: str,
    payload: ScheduledTaskDraftConfirmRequest,
) -> tuple[ScheduledTaskDraftRead, str]:
    record = _DRAFT_STORE.get(draft_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scheduled task draft not found")
    if record.creator_account_id != actor.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot confirm another user's draft")

    text = payload.text or _build_followup_text(record, payload)
    parsed = _parse_text_to_draft(db, actor=actor, household_id=record.household_id, text=text, existing=record)

    if payload.name:
        parsed.draft_payload["name"] = payload.name.strip()
    if payload.schedule_expr:
        parsed.draft_payload["schedule_expr"] = payload.schedule_expr.strip()
    if payload.target_ref_id:
        parsed.draft_payload["target_ref_id"] = payload.target_ref_id.strip()

    parsed.missing_fields = _collect_missing_fields(parsed.draft_payload)
    if parsed.missing_fields:
        parsed.status = "drafting"
        _DRAFT_STORE[parsed.draft_id] = parsed
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="scheduled_task_draft_incomplete")

    definition = create_task_definition(
        db,
        actor=actor,
        payload=ScheduledTaskDefinitionCreate.model_validate(parsed.draft_payload),
    )
    parsed.status = "confirmed"
    _DRAFT_STORE[parsed.draft_id] = parsed
    return _to_draft_read(parsed), definition.id


def _parse_text_to_draft(
    db: Session,
    *,
    actor: AuthenticatedActor,
    household_id: str,
    text: str,
    existing: DraftRecord | None,
) -> DraftRecord:
    normalized = text.strip()
    draft_id = existing.draft_id if existing is not None else new_uuid()
    name = _extract_name(normalized)
    schedule_expr = _extract_daily_time(normalized)
    target_ref_id = _resolve_default_agent_id(db, household_id=household_id)
    draft_payload: dict[str, object] = {
        "household_id": household_id,
        "owner_scope": "member",
        "owner_member_id": actor.member_id,
        "code": f"draft-{draft_id[:8]}",
        "name": name,
        "description": normalized,
        "trigger_type": "schedule",
        "schedule_type": "daily",
        "schedule_expr": schedule_expr,
        "target_type": "agent_reminder",
        "target_ref_id": target_ref_id,
        "payload_template": {"message": f"提醒你{name}" if name else normalized, "source_text": normalized},
    }
    if existing is not None:
        merged = dict(existing.draft_payload)
        merged.update({key: value for key, value in draft_payload.items() if value is not None})
        draft_payload = merged

    missing_fields = _collect_missing_fields(draft_payload)
    status_value = "awaiting_confirm" if not missing_fields else "drafting"
    return DraftRecord(
        draft_id=draft_id,
        household_id=household_id,
        creator_account_id=actor.account_id,
        owner_scope="member",
        owner_member_id=actor.member_id,
        intent_summary=f"按固定时间提醒你{name or '完成一件事'}",
        missing_fields=missing_fields,
        draft_payload=draft_payload,
        status=status_value,
    )


def _extract_name(text: str) -> str | None:
    match = re.search(r"提醒我(?P<content>.+)$", text)
    if not match:
        return None
    return match.group("content").strip(" 。！!?") or None


def _extract_daily_time(text: str) -> str | None:
    exact = re.search(r"(?P<hour>\d{1,2}):( ?)?(?P<minute>\d{2})", text)
    if exact:
        hour = int(exact.group("hour"))
        minute = int(exact.group("minute"))
        return f"{hour:02d}:{minute:02d}"
    normalized_text = _normalize_chinese_hour_text(text)
    zh = re.search(r"(早上|上午|中午|下午|晚上)?(?P<hour>\d{1,2})点(?P<minute>半|[0-5]?\d分?)?", normalized_text)
    if not zh:
        return None
    hour = int(zh.group("hour"))
    prefix = zh.group(1) or ""
    if prefix in {"下午", "晚上"} and hour < 12:
        hour += 12
    minute_part = zh.group("minute") or ""
    minute = 30 if minute_part == "半" else int(re.sub(r"[^0-9]", "", minute_part) or "0")
    return f"{hour:02d}:{minute:02d}"


def _normalize_chinese_hour_text(text: str) -> str:
    normalized = text
    replacements = {
        "十二点": "12点",
        "十一点": "11点",
        "十点": "10点",
        "九点": "9点",
        "八点": "8点",
        "七点": "7点",
        "六点": "6点",
        "五点": "5点",
        "四点": "4点",
        "三点": "3点",
        "两点": "2点",
        "二点": "2点",
        "一点": "1点",
        "零点": "0点",
    }
    for raw, replacement in replacements.items():
        normalized = normalized.replace(raw, replacement)
    return normalized


def _resolve_default_agent_id(db: Session, *, household_id: str) -> str | None:
    try:
        return resolve_effective_agent(db, household_id=household_id).id
    except Exception:
        return None


def _collect_missing_fields(payload: dict[str, object]) -> list[str]:
    missing: list[str] = []
    for field in ["name", "schedule_expr", "target_ref_id"]:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return missing


def _build_followup_text(record: DraftRecord, payload: ScheduledTaskDraftConfirmRequest) -> str:
    current = str(record.draft_payload.get("description") or record.intent_summary)
    parts = [current]
    if payload.name:
        parts.append(f"提醒我{payload.name}")
    if payload.schedule_expr:
        parts.append(payload.schedule_expr)
    return " ".join(parts)


def _to_draft_read(record: DraftRecord) -> ScheduledTaskDraftRead:
    return ScheduledTaskDraftRead(
        draft_id=record.draft_id,
        household_id=record.household_id,
        creator_account_id=record.creator_account_id,
        owner_scope=record.owner_scope,
        owner_member_id=record.owner_member_id,
        intent_summary=record.intent_summary,
        missing_fields=record.missing_fields,
        draft_payload=record.draft_payload,
        status=record.status,
        can_confirm=not record.missing_fields,
    )
