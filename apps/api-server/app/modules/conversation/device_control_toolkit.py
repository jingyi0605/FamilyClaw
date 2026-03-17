from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.modules.device.schemas import DeviceEntityControlRead, DeviceEntityRead
from app.modules.device.service import get_device_or_404, list_device_entities, list_devices
from app.modules.device_action.schemas import DeviceActionExecuteRequest, DeviceActionExecuteResponse
from app.modules.device_action.service import execute_device_action
from app.modules.device_control.protocol import DeviceActionDefinition, device_control_protocol_registry


_SEARCH_SPACE_PATTERN = re.compile(r"\s+")
_SEARCH_PUNCTUATION_PATTERN = re.compile(r"[，。！？、；：,.!?;:\"'“”‘’()（）【】\[\]{}<>《》]+")


@dataclass(frozen=True, slots=True)
class ConversationDeviceExecutionPlan:
    device_id: str
    entity_id: str
    action: str
    params: dict[str, Any]
    reason: str
    resolution_trace: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DeviceControlToolResult:
    tool_name: str
    items: list[dict[str, Any]]
    truncated: bool = False
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceControlToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


class ConversationDeviceControlToolRegistry:
    def list_tools(self) -> list[DeviceControlToolDefinition]:
        return [
            DeviceControlToolDefinition(
                name="search_controllable_entities",
                description="搜索当前家庭下可控制的设备和实体候选。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "room_id": {"type": "string"},
                        "device_types": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["query"],
                },
            ),
            DeviceControlToolDefinition(
                name="get_device_entity_profile",
                description="读取某个设备下的实体画像、状态和控制能力。",
                input_schema={
                    "type": "object",
                    "properties": {"device_id": {"type": "string"}},
                    "required": ["device_id"],
                },
            ),
            DeviceControlToolDefinition(
                name="execute_planned_device_action",
                description="把已经确认的 device_id/entity_id/action/params 落到统一执行链。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "action": {"type": "string"},
                        "params": {"type": "object"},
                        "reason": {"type": "string"},
                    },
                    "required": ["device_id", "entity_id", "action", "params", "reason"],
                },
            ),
        ]

    def execute(
        self,
        db: Session,
        *,
        household_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> DeviceControlToolResult:
        if tool_name == "search_controllable_entities":
            return search_controllable_entities(
                db,
                household_id=household_id,
                query=str(arguments.get("query") or ""),
                room_id=_normalize_optional_text(arguments.get("room_id")),
                device_types=_normalize_string_list(arguments.get("device_types")),
                limit=_coerce_limit(arguments.get("limit")),
            )
        if tool_name == "get_device_entity_profile":
            return get_device_entity_profile(
                db,
                household_id=household_id,
                device_id=str(arguments.get("device_id") or ""),
            )
        if tool_name == "execute_planned_device_action":
            response = execute_planned_device_action(
                db,
                household_id=household_id,
                plan=ConversationDeviceExecutionPlan(
                    device_id=str(arguments.get("device_id") or ""),
                    entity_id=str(arguments.get("entity_id") or ""),
                    action=str(arguments.get("action") or ""),
                    params=arguments.get("params") if isinstance(arguments.get("params"), dict) else {},
                    reason=str(arguments.get("reason") or ""),
                    resolution_trace=arguments.get("resolution_trace")
                    if isinstance(arguments.get("resolution_trace"), dict)
                    else {},
                ),
            )
            return DeviceControlToolResult(
                tool_name=tool_name,
                items=[response.model_dump(mode="json")],
                summary=f"已执行 {response.action} -> {response.entity_id}",
            )
        raise ValueError(f"unknown tool: {tool_name}")


device_control_tool_registry = ConversationDeviceControlToolRegistry()


def entity_supports_action(entity: DeviceEntityRead, action: str) -> bool:
    return any(item.get("action") == action for item in _extract_action_candidates(entity.control))


def search_controllable_entities(
    db: Session,
    *,
    household_id: str,
    query: str,
    room_id: str | None = None,
    device_types: list[str] | None = None,
    limit: int = 8,
) -> DeviceControlToolResult:
    devices, _ = list_devices(
        db,
        household_id=household_id,
        page=1,
        page_size=500,
        room_id=room_id,
    )
    normalized_query = _normalize_search_text(query)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for device in devices:
        if device.status != "active" or not bool(device.controllable):
            continue
        if device_types and device.device_type not in device_types:
            continue
        entity_list = list_device_entities(db, device_id=device.id, view="all")
        for entity in entity_list.items:
            action_candidates = _extract_action_candidates(entity.control)
            if entity.read_only or not action_candidates:
                continue
            score = _score_entity_match(query=normalized_query, device_name=device.name, entity=entity)
            if score <= 0 and normalized_query:
                continue
            candidates.append(
                (
                    score,
                    {
                        "device_id": device.id,
                        "device_name": device.name,
                        "device_type": device.device_type,
                        "room_id": device.room_id,
                        "entity_id": entity.entity_id,
                        "entity_name": entity.name,
                        "domain": entity.domain,
                        "state": entity.state,
                        "state_display": entity.state_display,
                        "disabled": entity.control.disabled,
                        "disabled_reason": entity.control.disabled_reason,
                        "supports_control": True,
                        "currently_available": not entity.control.disabled,
                        "availability_reason": entity.control.disabled_reason,
                        "action_candidates": action_candidates,
                    },
                )
            )
    candidates.sort(key=lambda item: (-item[0], item[1]["device_name"], item[1]["entity_name"]))
    limited_items = [item for _, item in candidates[:limit]]
    return DeviceControlToolResult(
        tool_name="search_controllable_entities",
        items=limited_items,
        truncated=len(candidates) > limit,
        summary=f"找到 {len(limited_items)} 个候选实体",
    )


def get_device_entity_profile(
    db: Session,
    *,
    household_id: str,
    device_id: str,
) -> DeviceControlToolResult:
    device = get_device_or_404(db, device_id)
    if device.household_id != household_id:
        raise ValueError("device must belong to the same household")
    entity_list = list_device_entities(db, device_id=device_id, view="all")
    item = {
        "device_id": device.id,
        "device_name": device.name,
        "device_type": device.device_type,
        "room_id": device.room_id,
        "status": device.status,
        "controllable": bool(device.controllable),
        "supported_actions": _list_supported_actions(device.device_type),
        "entities": [
            {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "domain": entity.domain,
                "state": entity.state,
                "state_display": entity.state_display,
                "read_only": entity.read_only,
                "disabled": entity.control.disabled,
                "disabled_reason": entity.control.disabled_reason,
                "supports_control": not entity.read_only and bool(_extract_action_candidates(entity.control)),
                "currently_available": not entity.control.disabled,
                "availability_reason": entity.control.disabled_reason,
                "action_candidates": _extract_action_candidates(entity.control),
            }
            for entity in entity_list.items
        ],
    }
    return DeviceControlToolResult(
        tool_name="get_device_entity_profile",
        items=[item],
        summary=f"读取到 {len(entity_list.items)} 个实体",
    )


def execute_planned_device_action(
    db: Session,
    *,
    household_id: str,
    plan: ConversationDeviceExecutionPlan,
) -> DeviceActionExecuteResponse:
    response, _ = execute_device_action(
        db,
        payload=DeviceActionExecuteRequest(
            household_id=household_id,
            device_id=plan.device_id,
            entity_id=plan.entity_id,
            action=plan.action,
            params=plan.params,
            reason=plan.reason,
            confirm_high_risk=bool(plan.resolution_trace.get("confirm_high_risk")),
        ),
    )
    return response


def _score_entity_match(*, query: str, device_name: str, entity: DeviceEntityRead) -> int:
    if not query:
        return 1
    haystacks = [
        _normalize_search_text(device_name),
        _normalize_search_text(entity.name),
        _normalize_search_text(entity.entity_id),
    ]
    if any(query == haystack for haystack in haystacks):
        return 20
    if any(query in haystack for haystack in haystacks):
        return 12
    score = 0
    max_char_overlap = 0
    token_matched = False
    for haystack in haystacks:
        if not haystack:
            continue
        matched_tokens = [token for token in _split_query_tokens(query) if token and token in haystack]
        if matched_tokens:
            token_matched = True
            score += 4
        max_char_overlap = max(max_char_overlap, sum(1 for char in set(query) if char in haystack))
    if token_matched:
        return score + max_char_overlap
    if len(query) <= 1 and max_char_overlap >= 1:
        return max_char_overlap
    if max_char_overlap >= 2:
        return max_char_overlap
    return 0


def _extract_action_candidates(control: DeviceEntityControlRead) -> list[dict[str, Any]]:
    if control.kind == "toggle":
        items: list[dict[str, Any]] = []
        if control.action_on:
            items.append({"action": control.action_on, "params": {}, "label": "打开"})
        if control.action_off:
            items.append({"action": control.action_off, "params": {}, "label": "关闭"})
        return items
    if control.kind == "range" and control.action:
        return [
            {
                "action": control.action,
                "params_schema": {
                    "min_value": control.min_value,
                    "max_value": control.max_value,
                    "step": control.step,
                    "unit": control.unit,
                },
                "label": control.action,
            }
        ]
    if control.kind == "action_set":
        return [
            {
                "action": option.action,
                "params": option.params,
                "label": option.label,
                "value": option.value,
            }
            for option in control.options
        ]
    if control.action:
        return [{"action": control.action, "params": {}, "label": control.action}]
    return []


def _list_supported_actions(device_type: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for definition in device_control_protocol_registry.list_definitions():
        if device_type not in definition.supported_device_types:
            continue
        actions.append(_serialize_action_definition(definition))
    return actions


def _serialize_action_definition(definition: DeviceActionDefinition) -> dict[str, Any]:
    return {
        "action": definition.action,
        "risk_level": definition.risk_level,
        "params_schema": definition.params_schema,
    }


def _normalize_search_text(value: str) -> str:
    normalized = _SEARCH_SPACE_PATTERN.sub("", value.strip().lower())
    normalized = _SEARCH_PUNCTUATION_PATTERN.sub("", normalized)
    return normalized


def _split_query_tokens(value: str) -> list[str]:
    normalized = _normalize_search_text(value)
    if not normalized:
        return []
    return [token for token in (normalized[i : i + 2] for i in range(max(len(normalized) - 1, 1))) if token]


def _normalize_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or None


def _coerce_limit(value: Any) -> int:
    if isinstance(value, int):
        return min(max(value, 1), 20)
    return 8
