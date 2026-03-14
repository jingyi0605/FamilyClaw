from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Literal, cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import new_uuid
from app.modules.account.service import AuthenticatedActor
from app.modules.agent.service import resolve_effective_agent
from app.modules.household.models import Household
from app.modules.member import service as member_service
from app.modules.member.models import Member
from app.modules.plugin.service import list_registered_plugins_for_household
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
    owner_scope: Literal["household", "member"] | None
    owner_member_id: str | None
    intent_summary: str
    missing_fields: list[str]
    draft_payload: dict[str, object]
    status: Literal["drafting", "awaiting_confirm", "confirmed", "cancelled"]


_DRAFT_STORE: dict[str, DraftRecord] = {}

_MISSING_FIELD_LABELS = {
    "name": "任务内容",
    "schedule_expr": "执行时间",
    "target_ref_id": "执行目标",
}

_ROLE_ALIASES = {
    "孩子": "child",
    "小朋友": "child",
    "儿童": "child",
    "老人": "elder",
    "长辈": "elder",
    "管理员": "admin",
}


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


def preview_draft_from_conversation(
    db: Session,
    *,
    actor: AuthenticatedActor,
    payload: ScheduledTaskDraftFromConversationRequest,
) -> ScheduledTaskDraftRead:
    if actor.household_id != payload.household_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot create draft for another household")
    record = _DRAFT_STORE.get(payload.draft_id or "") if payload.draft_id else None
    parsed = _parse_text_to_draft(db, actor=actor, household_id=payload.household_id, text=payload.text, existing=record)
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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_build_incomplete_detail(parsed.missing_fields))

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
    timezone_name = _resolve_household_timezone(db, household_id=household_id)
    members = _load_active_members(db, household_id=household_id)
    owner_scope, owner_member_id = _extract_owner_context(normalized, actor=actor, members=members)
    trigger_type, schedule_type, schedule_expr, heartbeat_interval_seconds, rule_type, rule_config = _extract_trigger_context(
        normalized,
        members=members,
        timezone_name=timezone_name,
    )
    name = _extract_name(normalized, owner_scope=owner_scope, owner_member_id=owner_member_id, members=members)
    target_type, target_ref_id = _resolve_target_context(db, household_id=household_id, text=normalized)
    draft_payload: dict[str, object] = {
        "household_id": household_id,
        "owner_scope": owner_scope,
        "owner_member_id": owner_member_id,
        "code": f"draft-{draft_id[:8]}",
        "name": name,
        "description": normalized,
        "trigger_type": trigger_type,
        "schedule_type": schedule_type,
        "schedule_expr": schedule_expr,
        "heartbeat_interval_seconds": heartbeat_interval_seconds,
        "timezone": timezone_name,
        "target_type": target_type,
        "target_ref_id": target_ref_id,
        "rule_type": rule_type,
        "rule_config": rule_config,
        "payload_template": {"message": _build_payload_message(name=name, owner_scope=owner_scope, owner_member_id=owner_member_id, members=members, fallback=normalized), "source_text": normalized},
    }
    if existing is not None:
        merged = dict(existing.draft_payload)
        for key, value in draft_payload.items():
            if value is None:
                continue
            if key == "owner_member_id" and merged.get("owner_scope") == "household":
                continue
            if key in {"owner_scope", "owner_member_id", "target_type", "target_ref_id"} and merged.get(key) not in {None, ""}:
                continue
            merged[key] = value
        draft_payload = merged

    missing_fields = _collect_missing_fields(draft_payload)
    status_value: Literal["drafting", "awaiting_confirm"] = "awaiting_confirm" if not missing_fields else "drafting"
    return DraftRecord(
        draft_id=draft_id,
        household_id=household_id,
        creator_account_id=actor.account_id,
        owner_scope=cast(Literal["household", "member"], owner_scope),
        owner_member_id=cast(str | None, draft_payload.get("owner_member_id")),
        intent_summary=_build_intent_summary(
            owner_scope=cast(str, draft_payload.get("owner_scope") or owner_scope),
            owner_member_id=cast(str | None, draft_payload.get("owner_member_id")),
            creator_member_id=actor.member_id,
            name=cast(str | None, draft_payload.get("name")),
            schedule_expr=cast(str | None, draft_payload.get("schedule_expr")),
            trigger_type=cast(str, draft_payload.get("trigger_type") or trigger_type),
            rule_type=cast(str, draft_payload.get("rule_type") or rule_type),
            rule_config=cast(dict[str, object], draft_payload.get("rule_config") or {}),
            members=members,
        ),
        missing_fields=missing_fields,
        draft_payload=draft_payload,
        status=status_value,
    )


def _extract_name(
    text: str,
    *,
    owner_scope: str,
    owner_member_id: str | None,
    members: list[Member],
) -> str | None:
    owner_tokens = ["我", "全家", "家里"]
    if owner_scope == "member" and owner_member_id:
        owner_name = _resolve_member_display_name(owner_member_id, members)
        if owner_name:
            owner_tokens.extend([owner_name])
    match = re.search(rf"提醒(?:{'|'.join(re.escape(token) for token in owner_tokens)})(?P<content>.+)$", text)
    if not match:
        return _extract_rule_name(text)
    content = match.group("content").strip(" 。！!?") or None
    if not content:
        return _extract_rule_name(text)
    return _strip_leading_owner_alias(content, members=members)


def _extract_owner_context(
    text: str,
    *,
    actor: AuthenticatedActor,
    members: list[Member],
) -> tuple[Literal["household", "member"], str | None]:
    if re.search(r"提醒(全家|家里)", text):
        return cast(Literal["household", "member"], "household"), None
    explicit_member = _match_member_from_text(text, members)
    if explicit_member is not None:
        return cast(Literal["household", "member"], "member"), explicit_member.id
    return cast(Literal["household", "member"], "member"), actor.member_id


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


def _extract_trigger_context(
    text: str,
    *,
    members: list[Member],
    timezone_name: str,
) -> tuple[str, str | None, str | None, int | None, str, dict[str, object]]:
    if re.search(r"如果|当", text):
        presence_rule = _extract_presence_rule(text, members=members)
        if presence_rule is not None:
            return "heartbeat", None, None, 300, "presence", presence_rule
    once_expr = _extract_once_schedule_expr(text, timezone_name=timezone_name)
    if once_expr is not None:
        return "schedule", "once", once_expr, None, "none", {}
    schedule_expr = _extract_daily_time(text)
    return "schedule", "daily", schedule_expr, None, "none", {}


def _extract_presence_rule(text: str, *, members: list[Member]) -> dict[str, object] | None:
    if any(keyword in text for keyword in ("没人", "无人在家", "都不在家")):
        return {"condition": "nobody_home"}
    matched_member = _match_member_from_text(text, members)
    if matched_member is not None and any(keyword in text for keyword in ("在家", "到家", "回家")):
        return {"condition": "member_present", "member_id": matched_member.id}
    for alias, role in _ROLE_ALIASES.items():
        if alias in text and any(keyword in text for keyword in ("在家", "到家", "回家")):
            return {"condition": "role_present", "role": role}
    return None


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


def _extract_once_schedule_expr(text: str, *, timezone_name: str) -> str | None:
    if re.search(r"每(天|周|月)|定时|固定", text):
        return None
    time_expr = _extract_daily_time(text)
    if time_expr is None:
        return None
    hour_text, minute_text = time_expr.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    base = datetime.now(_get_zoneinfo(timezone_name))
    target_date = _extract_target_date(text, base=base)
    if target_date is None:
        return None
    return f"{target_date.isoformat()}T{hour:02d}:{minute:02d}"


def _extract_target_date(text: str, *, base: datetime) -> date | None:
    normalized = text.strip()
    if "明天" in normalized:
        return (base + timedelta(days=1)).date()
    if "后天" in normalized:
        return (base + timedelta(days=2)).date()
    if any(keyword in normalized for keyword in ("今天", "今晚")):
        return base.date()
    month_day = re.search(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]?", normalized)
    if month_day:
        month = int(month_day.group("month"))
        day = int(month_day.group("day"))
        year = base.year
        candidate = datetime(year=year, month=month, day=day)
        if candidate.date() < base.date():
            candidate = datetime(year=year + 1, month=month, day=day)
        return candidate.date()
    return None


def _resolve_default_agent_id(db: Session, *, household_id: str) -> str | None:
    try:
        return resolve_effective_agent(db, household_id=household_id).id
    except Exception:
        return None


def _resolve_household_timezone(db: Session, *, household_id: str) -> str:
    household = db.get(Household, household_id)
    return household.timezone if household is not None else "Asia/Shanghai"


def _get_zoneinfo(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        fallback_offsets = {
            "UTC": 0,
            "Asia/Shanghai": 8,
            "Asia/Taipei": 8,
            "Asia/Hong_Kong": 8,
        }
        if timezone_name in fallback_offsets:
            return dt_timezone(timedelta(hours=fallback_offsets[timezone_name]), name=timezone_name)
        return dt_timezone.utc


def _resolve_target_context(db: Session, *, household_id: str, text: str) -> tuple[str, str | None]:
    plugin_target = _resolve_plugin_target(db, household_id=household_id, text=text)
    if plugin_target is not None:
        return "plugin_job", plugin_target
    return "agent_reminder", _resolve_default_agent_id(db, household_id=household_id)


def _resolve_plugin_target(db: Session, *, household_id: str, text: str) -> str | None:
    if not any(keyword in text for keyword in ("插件", "plugin", "通过")):
        return None
    try:
        registry = list_registered_plugins_for_household(db, household_id=household_id)
    except Exception:
        return None
    normalized = text.lower()
    for item in registry.items:
        if item.id.lower() in normalized or item.name.lower() in normalized:
            return item.id
    return None


def _load_active_members(db: Session, *, household_id: str) -> list[Member]:
    members, _ = member_service.list_members(db, household_id=household_id, page=1, page_size=100, status_value="active")
    return members


def _match_member_from_text(text: str, members: list[Member]) -> Member | None:
    normalized = text.strip()
    for member in members:
        aliases = [member.nickname, member.name]
        for alias in aliases:
            alias_text = str(alias or "").strip()
            if alias_text and alias_text in normalized:
                return member
    return None


def _resolve_member_display_name(member_id: str | None, members: list[Member]) -> str | None:
    if not member_id:
        return None
    for member in members:
        if member.id == member_id:
            return str(member.nickname or member.name or "").strip() or None
    return None


def _strip_leading_owner_alias(content: str, *, members: list[Member]) -> str:
    normalized = content.strip()
    for prefix in ["我", "全家", "家里", *(str(member.nickname or member.name or "").strip() for member in members)]:
        if prefix and normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized.lstrip("去要把让，,、 ") or content.strip()


def _extract_rule_name(text: str) -> str | None:
    for marker in ("提醒我", "提醒全家", "提醒家里"):
        if marker in text:
            candidate = text.split(marker, 1)[1].strip(" 。！!?")
            if candidate:
                return candidate
    return None


def _extract_renamed_task_name(text: str) -> str | None:
    match = re.search(r"(?:改名|名字改成|名称改成|改成)(?P<name>.+)$", text)
    if not match:
        return None
    return match.group("name").strip(" 。！!?") or None


def _build_payload_message(
    *,
    name: str | None,
    owner_scope: str,
    owner_member_id: str | None,
    members: list[Member],
    fallback: str,
) -> str:
    target_name = "全家" if owner_scope == "household" else (_resolve_member_display_name(owner_member_id, members) or "你")
    if name:
        return f"提醒{target_name}{name}"
    return fallback


def _collect_missing_fields(payload: dict[str, object]) -> list[str]:
    missing: list[str] = []
    required_fields = ["name", "target_ref_id"]
    if str(payload.get("trigger_type") or "schedule") == "schedule":
        required_fields.append("schedule_expr")
    for field in required_fields:
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


def looks_like_scheduled_task_intent(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if "提醒" not in normalized:
        return False
    if _extract_once_schedule_expr(normalized, timezone_name="Asia/Shanghai") is not None:
        return True
    if re.search(r"如果|当", normalized) and any(keyword in normalized for keyword in ("在家", "到家", "回家", "没人", "无人在家")):
        return True
    if _extract_daily_time(normalized) or re.search(r"每天|每晚|每早|每周|每月|定时|固定", normalized):
        return True
    if not re.match(r"^提醒(我|全家|家里)", normalized):
        return False
    return not bool(re.search(r"明天|后天|今天|今晚|下周|周[一二三四五六日天]|星期|\d{1,2}[月号日]", normalized))


def looks_like_scheduled_task_followup(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return bool(
        _extract_daily_time(normalized)
        or re.search(r"改成|改为|换成|每|分钟|小时|全家|家里|如果|当|在家|到家|回家|没人|无人在家", normalized)
    )


def build_partial_update_payload_from_text(
    db: Session,
    *,
    actor: AuthenticatedActor,
    household_id: str,
    text: str,
) -> dict[str, object]:
    normalized = text.strip()
    timezone_name = _resolve_household_timezone(db, household_id=household_id)
    members = _load_active_members(db, household_id=household_id)
    payload: dict[str, object] = {}
    owner_scope, owner_member_id = _extract_owner_context(normalized, actor=actor, members=members)
    if re.search(r"提醒(全家|家里)", normalized) or _match_member_from_text(normalized, members) is not None:
        payload["owner_scope"] = owner_scope
        payload["owner_member_id"] = owner_member_id

    trigger_type, schedule_type, schedule_expr, heartbeat_interval_seconds, rule_type, rule_config = _extract_trigger_context(
        normalized,
        members=members,
        timezone_name=timezone_name,
    )
    if trigger_type == "heartbeat":
        payload.update(
            {
                "trigger_type": trigger_type,
                "schedule_type": None,
                "schedule_expr": None,
                "heartbeat_interval_seconds": heartbeat_interval_seconds,
                "rule_type": rule_type,
                "rule_config": rule_config,
            }
        )
    elif schedule_expr is not None:
        payload.update(
            {
                "trigger_type": trigger_type,
                "schedule_type": schedule_type,
                "schedule_expr": schedule_expr,
                "heartbeat_interval_seconds": None,
                "rule_type": "none",
                "rule_config": {},
            }
        )

    if "改名" in normalized or "名字改成" in normalized:
        renamed = _extract_renamed_task_name(normalized)
        if renamed:
            payload["name"] = renamed
    target_type, target_ref_id = _resolve_target_context(db, household_id=household_id, text=normalized)
    if target_type == "plugin_job" or any(keyword in normalized for keyword in ("助手", "插件", "plugin")):
        payload["target_type"] = target_type
        payload["target_ref_id"] = target_ref_id
    return payload


def build_conversation_proposal_payload(draft: ScheduledTaskDraftRead) -> dict[str, object]:
    return {
        "draft_id": draft.draft_id,
        "intent_summary": draft.intent_summary,
        "missing_fields": list(draft.missing_fields),
        "missing_field_labels": list(draft.missing_field_labels),
        "draft_payload": dict(draft.draft_payload),
        "can_confirm": draft.can_confirm,
        "owner_summary": draft.owner_summary,
        "schedule_summary": draft.schedule_summary,
        "target_summary": draft.target_summary,
        "confirm_block_reason": draft.confirm_block_reason,
    }


def build_conversation_proposal_title(draft: ScheduledTaskDraftRead) -> str:
    summary = draft.intent_summary.strip() or "创建计划任务"
    return f"创建计划任务：{summary}"[:200]


def build_conversation_proposal_summary(draft: ScheduledTaskDraftRead) -> str:
    parts = [
        part
        for part in [draft.schedule_summary, draft.owner_summary, draft.target_summary, draft.confirm_block_reason]
        if part
    ]
    return "；".join(parts) or draft.intent_summary


def _to_draft_read(record: DraftRecord) -> ScheduledTaskDraftRead:
    missing_field_labels = [_MISSING_FIELD_LABELS.get(field, field) for field in record.missing_fields]
    return ScheduledTaskDraftRead(
        draft_id=record.draft_id,
        household_id=record.household_id,
        creator_account_id=record.creator_account_id,
        owner_scope=cast(Literal["household", "member"] | None, record.owner_scope),
        owner_member_id=record.owner_member_id,
        intent_summary=record.intent_summary,
        missing_fields=record.missing_fields,
        missing_field_labels=missing_field_labels,
        draft_payload=record.draft_payload,
        status=cast(Literal["drafting", "awaiting_confirm", "confirmed", "cancelled"], record.status),
        can_confirm=not record.missing_fields,
        owner_summary=_build_owner_summary(record),
        schedule_summary=_build_schedule_summary(record),
        target_summary=_build_target_summary(record),
        confirm_block_reason=None if not record.missing_fields else _build_incomplete_detail(record.missing_fields),
    )


def _build_intent_summary(
    *,
    owner_scope: str,
    owner_member_id: str | None,
    creator_member_id: str | None,
    name: str | None,
    schedule_expr: str | None,
    trigger_type: str,
    rule_type: str,
    rule_config: dict[str, object],
    members: list[Member],
) -> str:
    owner_text = "全家" if owner_scope == "household" else (
        "你" if owner_member_id and creator_member_id and owner_member_id == creator_member_id else (_resolve_member_display_name(owner_member_id, members) or "你")
    )
    if trigger_type == "heartbeat" and rule_type == "presence":
        schedule_text = _build_presence_summary(rule_config, members=members)
        return f"{schedule_text}时提醒{owner_text}{name or '处理一件事'}"
    if trigger_type == "schedule" and schedule_expr and "T" in schedule_expr:
        return f"在 {schedule_expr.replace('T', ' ')} 提醒{owner_text}{name or '完成一件事'}"
    schedule_text = f"每天 {schedule_expr}" if schedule_expr else "按固定时间"
    return f"{schedule_text}提醒{owner_text}{name or '完成一件事'}"


def _build_owner_summary(record: DraftRecord) -> str:
    if record.owner_scope == "household":
        return "归属：家庭公共任务"
    return "归属：成员私有任务"


def _build_schedule_summary(record: DraftRecord) -> str:
    if str(record.draft_payload.get("trigger_type") or "schedule") == "heartbeat":
        return f"触发条件：{_build_presence_summary(cast(dict[str, object], record.draft_payload.get('rule_config') or {}), members=[])}"
    schedule_expr = str(record.draft_payload.get("schedule_expr") or "").strip()
    if schedule_expr and "T" in schedule_expr:
        return f"时间：{schedule_expr.replace('T', ' ')}（一次）"
    if schedule_expr:
        return f"时间：每天 {schedule_expr}"
    return "时间：还没补全"


def _build_target_summary(record: DraftRecord) -> str:
    target_type = str(record.draft_payload.get("target_type") or "").strip()
    if target_type == "agent_reminder":
        return "执行方式：由家庭助手发起提醒"
    if target_type == "plugin_job":
        return "执行方式：调用插件任务"
    return "执行方式：等待确认具体目标"


def _build_incomplete_detail(missing_fields: list[str]) -> str:
    labels = [_MISSING_FIELD_LABELS.get(field, field) for field in missing_fields]
    return f"这条计划任务还不能确认，还缺：{'、'.join(labels)}。"


def _build_presence_summary(rule_config: dict[str, object], *, members: list[Member]) -> str:
    condition = str(rule_config.get("condition") or "").strip()
    if condition == "nobody_home":
        return "当家里没人"
    if condition == "member_present":
        member_name = _resolve_member_display_name(str(rule_config.get("member_id") or ""), members)
        return f"当{member_name or '指定成员'}到家"
    if condition == "role_present":
        role = str(rule_config.get("role") or "").strip()
        role_name = next((alias for alias, role_value in _ROLE_ALIASES.items() if role_value == role), role or "指定角色")
        return f"当{role_name}到家"
    return "满足条件时"
