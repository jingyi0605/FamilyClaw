from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.context.schemas import ContextOverviewRead
from app.modules.context.service import build_context_overview
from app.modules.scheduler.models import ScheduledTaskDefinition, ScheduledTaskRun

RuleEvaluationStatus = Literal["matched", "skipped", "suppressed", "error"]


class RuleEvaluationResult(BaseModel):
    status: RuleEvaluationStatus
    summary: str
    matched: bool = False
    suppressed_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


def evaluate_heartbeat_rule(
    db: Session,
    *,
    definition: ScheduledTaskDefinition,
    now_iso: str | None = None,
    overview: ContextOverviewRead | None = None,
) -> RuleEvaluationResult:
    try:
        context_overview = overview or build_context_overview(db, definition.household_id)
        snapshot = _build_base_snapshot(definition=definition, overview=context_overview, now_iso=now_iso)
        suppressed = _check_suppression(db=db, definition=definition, overview=context_overview, snapshot=snapshot, now_iso=now_iso)
        if suppressed is not None:
            return suppressed

        if definition.rule_type == "context_insight":
            return _evaluate_context_insight(definition=definition, overview=context_overview, snapshot=snapshot)
        if definition.rule_type == "presence":
            return _evaluate_presence(definition=definition, overview=context_overview, snapshot=snapshot)
        if definition.rule_type == "device_summary":
            return _evaluate_device_summary(definition=definition, overview=context_overview, snapshot=snapshot)
        return RuleEvaluationResult(
            status="matched",
            matched=True,
            summary="heartbeat task without rule_type defaults to matched",
            snapshot=snapshot,
        )
    except HTTPException as exc:
        return RuleEvaluationResult(
            status="error",
            summary="规则评估失败",
            error_code="scheduled_task_rule_eval_failed",
            error_message=str(exc.detail),
            snapshot={"task_id": definition.id, "rule_type": definition.rule_type},
        )
    except Exception as exc:
        return RuleEvaluationResult(
            status="error",
            summary="规则评估失败",
            error_code="scheduled_task_rule_eval_failed",
            error_message=str(exc),
            snapshot={"task_id": definition.id, "rule_type": definition.rule_type},
        )


def _evaluate_context_insight(
    *,
    definition: ScheduledTaskDefinition,
    overview: ContextOverviewRead,
    snapshot: dict[str, Any],
) -> RuleEvaluationResult:
    config = _get_rule_config(definition)
    codes = _get_string_list(config, "codes")
    if not codes:
        single = config.get("code")
        if isinstance(single, str) and single.strip():
            codes = [single.strip()]
    if not codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="context_insight rule requires code or codes")

    match_mode = str(config.get("match_mode") or "any").lower()
    insight_codes = {item.code for item in overview.insights}
    matched_codes = [code for code in codes if code in insight_codes]
    snapshot["rule_input"] = {
        "requested_codes": codes,
        "insight_codes": sorted(insight_codes),
        "matched_codes": matched_codes,
    }

    matched = len(matched_codes) == len(codes) if match_mode == "all" else bool(matched_codes)
    if matched:
        return RuleEvaluationResult(status="matched", matched=True, summary=f"命中 insight 规则：{', '.join(matched_codes)}", snapshot=snapshot)
    return RuleEvaluationResult(status="skipped", matched=False, summary="当前家庭状态没有命中指定 insight", snapshot=snapshot)


def _evaluate_presence(
    *,
    definition: ScheduledTaskDefinition,
    overview: ContextOverviewRead,
    snapshot: dict[str, Any],
) -> RuleEvaluationResult:
    config = _get_rule_config(definition)
    condition = str(config.get("condition") or "").strip()
    home_members = [item for item in overview.member_states if item.presence == "home"]
    home_member_ids = {item.member_id for item in home_members}
    snapshot["rule_input"] = {
        "condition": condition,
        "home_member_ids": sorted(home_member_ids),
        "active_member_id": overview.active_member.member_id if overview.active_member else None,
    }

    if condition == "role_present":
        role = str(config.get("role") or "").strip()
        matched_members = [item.member_id for item in home_members if item.role == role]
        snapshot["rule_input"]["role"] = role
        snapshot["rule_input"]["matched_member_ids"] = matched_members
        if matched_members:
            return RuleEvaluationResult(status="matched", matched=True, summary=f"命中 presence 规则：存在角色 {role} 的在家成员", snapshot=snapshot)
        return RuleEvaluationResult(status="skipped", matched=False, summary=f"当前没有角色 {role} 的在家成员", snapshot=snapshot)

    if condition == "member_present":
        member_id = str(config.get("member_id") or "").strip()
        snapshot["rule_input"]["member_id"] = member_id
        if member_id in home_member_ids:
            return RuleEvaluationResult(status="matched", matched=True, summary="命中 presence 规则：指定成员在家", snapshot=snapshot)
        return RuleEvaluationResult(status="skipped", matched=False, summary="指定成员当前不在家", snapshot=snapshot)

    if condition == "nobody_home":
        if not home_members:
            return RuleEvaluationResult(status="matched", matched=True, summary="命中 presence 规则：当前无人在家", snapshot=snapshot)
        return RuleEvaluationResult(status="skipped", matched=False, summary="当前仍有人在家", snapshot=snapshot)

    if condition == "elder_alone":
        elders_home = [item.member_id for item in home_members if item.role == "elder"]
        snapshot["rule_input"]["elder_member_ids"] = elders_home
        if elders_home and len(elders_home) == len(home_members):
            return RuleEvaluationResult(status="matched", matched=True, summary="命中 presence 规则：老人独自在家", snapshot=snapshot)
        return RuleEvaluationResult(status="skipped", matched=False, summary="当前不满足老人独自在家条件", snapshot=snapshot)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="presence rule condition is unsupported")


def _evaluate_device_summary(
    *,
    definition: ScheduledTaskDefinition,
    overview: ContextOverviewRead,
    snapshot: dict[str, Any],
) -> RuleEvaluationResult:
    config = _get_rule_config(definition)
    metric = str(config.get("metric") or "").strip()
    operator = str(config.get("operator") or "gte").strip()
    expected_value = config.get("value")
    if not isinstance(expected_value, int):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_summary rule requires integer value")
    metric_value = _resolve_device_metric(overview, metric)
    snapshot["rule_input"] = {"metric": metric, "metric_value": metric_value, "operator": operator, "value": expected_value}
    if _compare_number(metric_value, operator, expected_value):
        return RuleEvaluationResult(status="matched", matched=True, summary=f"命中 device_summary 规则：{metric} {operator} {expected_value}", snapshot=snapshot)
    return RuleEvaluationResult(status="skipped", matched=False, summary=f"当前设备摘要未命中 {metric} {operator} {expected_value}", snapshot=snapshot)


def _check_suppression(
    *,
    db: Session,
    definition: ScheduledTaskDefinition,
    overview: ContextOverviewRead,
    snapshot: dict[str, Any],
    now_iso: str | None,
) -> RuleEvaluationResult | None:
    config = _get_rule_config(definition)
    if overview.guest_mode_enabled and bool(config.get("suppress_when_guest_mode", False)):
        snapshot["suppression"] = {"reason": "guest_mode_enabled"}
        return RuleEvaluationResult(status="suppressed", matched=False, summary="当前处于访客模式，规则命中被抑制", suppressed_reason="guest_mode_enabled", snapshot=snapshot)
    if definition.quiet_hours_policy != "allow" and overview.quiet_hours_enabled and _is_within_quiet_hours(overview, now_iso=now_iso, timezone_name=definition.timezone):
        snapshot["suppression"] = {"reason": "quiet_hours", "policy": definition.quiet_hours_policy}
        return RuleEvaluationResult(status="suppressed", matched=False, summary="当前处于静默时段，规则命中被抑制", suppressed_reason="quiet_hours", snapshot=snapshot)
    if definition.cooldown_seconds > 0 and _hit_cooldown_window(db, definition=definition, now_iso=now_iso):
        snapshot["suppression"] = {"reason": "cooldown", "cooldown_seconds": definition.cooldown_seconds}
        return RuleEvaluationResult(status="suppressed", matched=False, summary="当前仍在冷却窗口内，规则命中被抑制", suppressed_reason="cooldown", snapshot=snapshot)
    return None


def _build_base_snapshot(*, definition: ScheduledTaskDefinition, overview: ContextOverviewRead, now_iso: str | None) -> dict[str, Any]:
    return {
        "task_id": definition.id,
        "rule_type": definition.rule_type,
        "household_id": definition.household_id,
        "evaluated_at": now_iso or overview.generated_at,
        "context_generated_at": overview.generated_at,
        "guest_mode_enabled": overview.guest_mode_enabled,
        "quiet_hours_enabled": overview.quiet_hours_enabled,
        "degraded": overview.degraded,
    }


def _is_within_quiet_hours(overview: ContextOverviewRead, *, now_iso: str | None, timezone_name: str) -> bool:
    reference = _parse_iso_datetime(now_iso or overview.generated_at).astimezone(_get_zoneinfo(timezone_name))
    minutes = reference.hour * 60 + reference.minute
    start = _parse_hhmm_to_minutes(overview.quiet_hours_start)
    end = _parse_hhmm_to_minutes(overview.quiet_hours_end)
    if start == end:
        return True
    if start < end:
        return start <= minutes < end
    return minutes >= start or minutes < end


def _resolve_device_metric(overview: ContextOverviewRead, metric: str) -> int:
    mapping = {
        "total": overview.device_summary.total,
        "active": overview.device_summary.active,
        "offline": overview.device_summary.offline,
        "inactive": overview.device_summary.inactive,
        "controllable": overview.device_summary.controllable,
        "controllable_active": overview.device_summary.controllable_active,
        "controllable_offline": overview.device_summary.controllable_offline,
    }
    if metric not in mapping:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_summary metric is unsupported")
    return mapping[metric]


def _compare_number(left: int, operator: str, right: int) -> bool:
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_summary operator is unsupported")


def _parse_hhmm_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":", 1)
    return int(hour_text) * 60 + int(minute_text)


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _get_zoneinfo(timezone_name: str) -> tzinfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        fallback_offsets = {
            "UTC": 0,
            "Asia/Shanghai": 8,
            "Asia/Taipei": 8,
            "Asia/Hong_Kong": 8,
            "Asia/Macau": 8,
            "Asia/Tokyo": 9,
        }
        if timezone_name in fallback_offsets:
            return timezone(timedelta(hours=fallback_offsets[timezone_name]), name=timezone_name)
    if timezone_name == "UTC":
        return timezone.utc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="timezone is invalid")


def _get_rule_config(definition: ScheduledTaskDefinition) -> dict[str, Any]:
    from app.db.utils import load_json

    raw = load_json(definition.rule_config_json)
    return raw if isinstance(raw, dict) else {}


def _get_string_list(config: dict[str, Any], key: str) -> list[str]:
    value = config.get(key)
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _hit_cooldown_window(db: Session, *, definition: ScheduledTaskDefinition, now_iso: str | None) -> bool:
    if definition.last_result not in {"queued", "dispatching", "succeeded"}:
        return False
    reference_text = definition.last_run_at
    if not reference_text:
        recent_run = db.scalar(
            select(ScheduledTaskRun)
            .where(
                ScheduledTaskRun.task_definition_id == definition.id,
                ScheduledTaskRun.status.in_(["queued", "dispatching", "succeeded"]),
            )
            .order_by(ScheduledTaskRun.created_at.desc())
            .limit(1)
        )
        reference_text = recent_run.finished_at or recent_run.created_at if recent_run is not None else None
    if not reference_text:
        return False
    reference_time = _parse_iso_datetime(reference_text)
    current_time = _parse_iso_datetime(now_iso or utc_now())
    return (current_time - reference_time).total_seconds() < definition.cooldown_seconds


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
