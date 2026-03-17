from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.modules.conversation.device_context_summary import (
    ConversationDeviceContextSummary,
    EMPTY_CONVERSATION_DEVICE_CONTEXT_SUMMARY,
)
from app.modules.conversation.device_control_toolkit import (
    ConversationDeviceExecutionPlan,
    device_control_tool_registry,
)
from app.modules.device.service import get_device_or_404, list_device_entities
from app.modules.llm_task import invoke_llm
from app.modules.llm_task.output_models import (
    ConversationDevicePlannerPlanOutput,
    ConversationDevicePlannerStepOutput,
)


DEVICE_CONTROL_PLANNER_TASK = "conversation_device_control_planner"
DEVICE_CONTROL_PLANNER_MAX_STEPS = 4
DEVICE_CONTROL_PLANNER_ALLOWED_TOOLS = {
    "search_controllable_entities",
    "get_device_entity_profile",
}


class ConversationDevicePlannerError(RuntimeError):
    def __init__(self, code: str, *, debug_payload: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.debug_payload = debug_payload or {}

    """规划器内部失败，允许编排层回退到旧兜底。"""


class ConversationDevicePlannerValidationError(RuntimeError):
    """规划器给出了非法计划，本轮必须收口，不允许偷偷纠偏执行。"""


@dataclass(frozen=True, slots=True)
class ConversationDevicePlannerClarification:
    code: str
    message: str
    suggestions: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ConversationDevicePlannerResult:
    plan: ConversationDeviceExecutionPlan | None = None
    clarification: ConversationDevicePlannerClarification | None = None
    resolution_trace: dict[str, Any] = field(default_factory=dict)


def plan_device_control(
    db: Session,
    *,
    household_id: str,
    message: str,
    device_context_summary: ConversationDeviceContextSummary | None = None,
    request_context: dict[str, Any] | None = None,
) -> ConversationDevicePlannerResult:
    device_context_summary = device_context_summary or EMPTY_CONVERSATION_DEVICE_CONTEXT_SUMMARY
    tool_definitions = [
        tool
        for tool in device_control_tool_registry.list_tools()
        if tool.name in DEVICE_CONTROL_PLANNER_ALLOWED_TOOLS
    ]
    tool_history: list[dict[str, Any]] = []

    for step_index in range(DEVICE_CONTROL_PLANNER_MAX_STEPS):
        result = invoke_llm(
            db,
            task_type=DEVICE_CONTROL_PLANNER_TASK,
            variables={
                "user_message": message,
                "tool_catalog": _serialize_tool_catalog(tool_definitions),
                "tool_history": _serialize_tool_history(tool_history),
                "step_index": step_index + 1,
                "max_steps": DEVICE_CONTROL_PLANNER_MAX_STEPS,
                "action_guide": _build_action_guide(),
                "device_context_summary": device_context_summary.to_prompt_text(),
            },
            household_id=household_id,
            request_context=request_context,
        )
        parsed = result.data
        if not isinstance(parsed, ConversationDevicePlannerStepOutput):
            raise ConversationDevicePlannerError(
                "planner_parse_failed",
                debug_payload=_build_parse_failed_payload(result=result, step_index=step_index + 1),
            )

        if parsed.outcome == "tool_call":
            tool_call = parsed.tool_call
            if tool_call is None:
                raise ConversationDevicePlannerError("planner_tool_call_missing")
            tool_name = tool_call.tool_name.strip()
            if tool_name not in DEVICE_CONTROL_PLANNER_ALLOWED_TOOLS:
                raise ConversationDevicePlannerError(f"planner_tool_not_allowed:{tool_name}")
            tool_result = device_control_tool_registry.execute(
                db,
                household_id=household_id,
                tool_name=tool_name,
                arguments=tool_call.arguments,
            )
            tool_history.append(
                {
                    "step": step_index + 1,
                    "tool_name": tool_name,
                    "arguments": tool_call.arguments,
                    "summary": tool_result.summary,
                    "truncated": tool_result.truncated,
                    "items": tool_result.items,
                }
            )
            continue

        if parsed.outcome == "clarification":
            clarification = ConversationDevicePlannerClarification(
                code="device_resolution_ambiguous",
                message=parsed.clarification_question or parsed.reason or "我还需要你再说得更明确一点。",
                suggestions=parsed.suggestions,
                reason=parsed.reason,
            )
            return ConversationDevicePlannerResult(
                clarification=clarification,
                resolution_trace=_build_resolution_trace(
                    step_type="clarification",
                    reason=parsed.reason,
                    tool_history=tool_history,
                ),
            )

        if parsed.outcome == "not_found":
            clarification = ConversationDevicePlannerClarification(
                code="device_resolution_not_found",
                message=parsed.reason or "我还没找到你要控制的设备。",
                suggestions=parsed.suggestions,
                reason=parsed.reason,
            )
            return ConversationDevicePlannerResult(
                clarification=clarification,
                resolution_trace=_build_resolution_trace(
                    step_type="not_found",
                    reason=parsed.reason,
                    tool_history=tool_history,
                ),
            )

        if parsed.outcome == "failed":
            raise ConversationDevicePlannerError(parsed.reason or "planner_failed")

        if parsed.outcome != "final_plan" or parsed.final_plan is None:
            raise ConversationDevicePlannerError("planner_final_plan_missing")

        try:
            plan = _validate_final_plan(
                db,
                household_id=household_id,
                final_plan=parsed.final_plan,
            )
        except ConversationDevicePlannerValidationError as exc:
            recovered_plan = _recover_plan_from_tool_history(
                db,
                household_id=household_id,
                message=message,
                invalid_plan=parsed.final_plan,
                tool_history=tool_history,
            )
            if recovered_plan is not None:
                resolution_trace = _build_resolution_trace(
                    step_type="recovered_plan",
                    reason=f"recovered_after:{exc}",
                    tool_history=tool_history,
                    final_plan=recovered_plan,
                )
                return ConversationDevicePlannerResult(
                    plan=ConversationDeviceExecutionPlan(
                        device_id=recovered_plan.device_id,
                        entity_id=recovered_plan.entity_id,
                        action=recovered_plan.action,
                        params=recovered_plan.params,
                        reason="conversation.fast_action.tool_planner",
                        resolution_trace=resolution_trace,
                    ),
                    resolution_trace=resolution_trace,
                )
            clarification = ConversationDevicePlannerClarification(
                code="device_resolution_invalid",
                message="我还不能安全确定这次该控制哪个实体，请把设备说得再具体一点。",
                suggestions=parsed.suggestions,
                reason=str(exc),
            )
            return ConversationDevicePlannerResult(
                clarification=clarification,
                resolution_trace=_build_resolution_trace(
                    step_type="invalid_plan",
                    reason=str(exc),
                    tool_history=tool_history,
                    final_plan=parsed.final_plan,
                ),
            )
        return ConversationDevicePlannerResult(
            plan=ConversationDeviceExecutionPlan(
                device_id=plan.device_id,
                entity_id=plan.entity_id,
                action=plan.action,
                params=plan.params,
                reason="conversation.fast_action.tool_planner",
                resolution_trace=_build_resolution_trace(
                    step_type="final_plan",
                    reason=plan.reason,
                    tool_history=tool_history,
                    final_plan=plan,
                ),
            ),
            resolution_trace=_build_resolution_trace(
                step_type="final_plan",
                reason=plan.reason,
                tool_history=tool_history,
                final_plan=plan,
            ),
        )

    raise ConversationDevicePlannerError("planner_step_limit_exceeded")


def _build_parse_failed_payload(*, result: Any, step_index: int) -> dict[str, Any]:
    raw_text = str(getattr(result, "raw_text", "") or "")
    display_text = str(getattr(result, "text", "") or "")
    provider = str(getattr(result, "provider", "") or "")
    payload: dict[str, Any] = {
        "planner_step": step_index,
        "provider": provider,
    }
    if raw_text:
        payload["raw_text_preview"] = _truncate_debug_preview(raw_text)
    if display_text:
        payload["display_text_preview"] = _truncate_debug_preview(display_text)
    return payload


def _truncate_debug_preview(value: str, limit: int = 500) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _validate_final_plan(
    db: Session,
    *,
    household_id: str,
    final_plan: ConversationDevicePlannerPlanOutput,
) -> ConversationDevicePlannerPlanOutput:
    device = get_device_or_404(db, final_plan.device_id)
    if device.household_id != household_id:
        raise ConversationDevicePlannerValidationError("planner_device_out_of_household")
    if device.status != "active" or not bool(device.controllable):
        raise ConversationDevicePlannerValidationError("planner_device_not_controllable")

    entity_list = list_device_entities(db, device_id=device.id, view="all")
    matched_entity = next((entity for entity in entity_list.items if entity.entity_id == final_plan.entity_id), None)
    if matched_entity is None:
        raise ConversationDevicePlannerValidationError("planner_entity_not_found")
    if matched_entity.read_only:
        raise ConversationDevicePlannerValidationError("planner_entity_not_controllable")
    if not any(item.get("action") == final_plan.action for item in _extract_entity_actions(matched_entity.control)):
        raise ConversationDevicePlannerValidationError("planner_action_not_supported")
    return final_plan


def _recover_plan_from_tool_history(
    db: Session,
    *,
    household_id: str,
    message: str,
    invalid_plan: ConversationDevicePlannerPlanOutput,
    tool_history: list[dict[str, Any]],
) -> ConversationDevicePlannerPlanOutput | None:
    candidate = _select_unique_candidate_from_tool_history(tool_history)
    if candidate is None:
        return None

    recovered_action = _recover_action_from_candidate(message=message, candidate=candidate, invalid_plan=invalid_plan)
    if recovered_action is None:
        return None

    recovered_plan = ConversationDevicePlannerPlanOutput(
        device_id=str(candidate.get("device_id") or ""),
        entity_id=str(candidate.get("entity_id") or ""),
        action=recovered_action,
        params={},
        confidence=max(invalid_plan.confidence, 0.85),
        reason="工具结果已收敛到唯一实体，按显式动作归一化执行计划。",
        requires_high_risk_confirmation=invalid_plan.requires_high_risk_confirmation,
    )
    try:
        return _validate_final_plan(db, household_id=household_id, final_plan=recovered_plan)
    except ConversationDevicePlannerValidationError:
        return None


def _select_unique_candidate_from_tool_history(tool_history: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest_search_items: list[dict[str, Any]] | None = None
    for item in reversed(tool_history):
        if item.get("tool_name") != "search_controllable_entities":
            continue
        raw_items = item.get("items")
        if not isinstance(raw_items, list):
            continue
        latest_search_items = [candidate for candidate in raw_items if isinstance(candidate, dict)]
        break
    if not latest_search_items:
        return None
    unique_candidates = {
        (str(item.get("device_id") or ""), str(item.get("entity_id") or "")): item
        for item in latest_search_items
        if str(item.get("device_id") or "").strip() and str(item.get("entity_id") or "").strip()
    }
    if len(unique_candidates) != 1:
        return None
    return next(iter(unique_candidates.values()))


def _recover_action_from_candidate(
    *,
    message: str,
    candidate: dict[str, Any],
    invalid_plan: ConversationDevicePlannerPlanOutput,
) -> str | None:
    supported_actions = {
        str(item.get("action") or "").strip()
        for item in candidate.get("action_candidates", [])
        if isinstance(item, dict) and str(item.get("action") or "").strip()
    }
    if not supported_actions:
        return None
    if invalid_plan.action in supported_actions:
        return invalid_plan.action
    inferred_action = _infer_action_from_message(message=message, supported_actions=supported_actions)
    if inferred_action is not None:
        return inferred_action
    if len(supported_actions) == 1:
        return next(iter(supported_actions))
    return None


def _infer_action_from_message(*, message: str, supported_actions: set[str]) -> str | None:
    normalized = _normalize_action_message(message)
    keyword_groups: list[tuple[str, tuple[str, ...]]] = [
        ("unlock", ("确认解锁", "解锁")),
        ("lock", ("锁上", "上锁", "锁门")),
        ("stop", ("停止", "停下")),
        ("open", ("拉开", "打开")),
        ("close", ("拉上", "合上", "关闭")),
        ("turn_on", ("打开", "开启", "开一下", "开")),
        ("turn_off", ("关掉", "关闭", "关上", "关")),
    ]
    for action, keywords in keyword_groups:
        if action not in supported_actions:
            continue
        if any(keyword in normalized for keyword in keywords):
            return action
    return None


def _normalize_action_message(message: str) -> str:
    normalized = message.strip().lower()
    for token in (" ", "，", "。", "？", "！", ",", ".", "?", "!", "请", "帮我", "给我", "一下", "立刻", "马上", "把", "将"):
        normalized = normalized.replace(token, "")
    return normalized


def _extract_entity_actions(control) -> list[dict[str, Any]]:
    if control.kind == "toggle":
        items: list[dict[str, Any]] = []
        if control.action_on:
            items.append({"action": control.action_on})
        if control.action_off:
            items.append({"action": control.action_off})
        return items
    if control.kind == "action_set":
        return [{"action": option.action} for option in control.options]
    if control.action:
        return [{"action": control.action}]
    return []


def _serialize_tool_catalog(tool_definitions: list[Any]) -> str:
    return json.dumps(
        [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tool_definitions
        ],
        ensure_ascii=False,
        indent=2,
    )


def _serialize_tool_history(tool_history: list[dict[str, Any]]) -> str:
    if not tool_history:
        return "暂无工具结果。"
    return json.dumps(tool_history, ensure_ascii=False, indent=2)


def _build_action_guide() -> str:
    return json.dumps(
        {
            "light": ["turn_on", "turn_off"],
            "ac": ["turn_on", "turn_off"],
            "speaker": ["turn_on", "turn_off"],
            "curtain": ["open", "close", "stop"],
            "lock": ["lock", "unlock"],
        },
        ensure_ascii=False,
        indent=2,
    )


def _build_resolution_trace(
    *,
    step_type: str,
    reason: str,
    tool_history: list[dict[str, Any]],
    final_plan: ConversationDevicePlannerPlanOutput | None = None,
) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "source": "tool_planner",
        "planner_outcome": step_type,
        "reason": reason,
        "tool_steps": [
            {
                "step": item["step"],
                "tool_name": item["tool_name"],
                "arguments": item["arguments"],
                "summary": item["summary"],
                "truncated": item["truncated"],
                "item_count": len(item["items"]),
            }
            for item in tool_history
        ],
    }
    if final_plan is not None:
        trace["final_plan"] = {
            "device_id": final_plan.device_id,
            "entity_id": final_plan.entity_id,
            "action": final_plan.action,
            "params": final_plan.params,
            "confidence": final_plan.confidence,
            "requires_high_risk_confirmation": final_plan.requires_high_risk_confirmation,
        }
    return trace
