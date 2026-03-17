from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from app.db.utils import load_json
from app.modules.conversation.models import ConversationMessage


@dataclass(slots=True, frozen=True)
class ConversationDeviceContextTarget:
    source_type: str
    message_id: str
    request_id: str | None
    created_at: str
    device_id: str
    device_name: str
    device_type: str | None = None
    entity_id: str | None = None
    room_id: str | None = None
    room_name: str | None = None
    status: str | None = None
    action: str | None = None
    confidence: float | None = None
    resolved_by_execution: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "message_id": self.message_id,
            "request_id": self.request_id,
            "created_at": self.created_at,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "entity_id": self.entity_id,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "status": self.status,
            "action": self.action,
            "confidence": self.confidence,
            "resolved_by_execution": self.resolved_by_execution,
        }

    def to_prompt_line(self) -> str:
        parts = [
            f"设备={self.device_name}",
            f"device_id={self.device_id}",
            f"来源={self.source_type}",
        ]
        if self.entity_id:
            parts.append(f"entity_id={self.entity_id}")
        if self.device_type:
            parts.append(f"device_type={self.device_type}")
        if self.action:
            parts.append(f"最近动作={self.action}")
        if self.status:
            parts.append(f"最近状态={self.status}")
        if self.room_name:
            parts.append(f"房间={self.room_name}")
        return "；".join(parts)

    @classmethod
    def from_payload(cls, value: object) -> "ConversationDeviceContextTarget | None":
        if not isinstance(value, dict):
            return None

        device_id = str(value.get("device_id") or "").strip()
        device_name = str(value.get("device_name") or "").strip()
        source_type = str(value.get("source_type") or "").strip()
        created_at = str(value.get("created_at") or "").strip()
        message_id = str(value.get("message_id") or "").strip()
        if not device_id or not device_name or not source_type:
            return None

        return cls(
            source_type=source_type,
            message_id=message_id,
            request_id=str(value.get("request_id") or "").strip() or None,
            created_at=created_at,
            device_id=device_id,
            device_name=device_name,
            device_type=str(value.get("device_type") or "").strip() or None,
            entity_id=str(value.get("entity_id") or "").strip() or None,
            room_id=str(value.get("room_id") or "").strip() or None,
            room_name=str(value.get("room_name") or "").strip() or None,
            status=str(value.get("status") or "").strip() or None,
            action=str(value.get("action") or "").strip() or None,
            confidence=_coerce_optional_float(value.get("confidence")),
            resolved_by_execution=bool(value.get("resolved_by_execution")),
        )


@dataclass(slots=True)
class ConversationDeviceContextSummary:
    latest_target: ConversationDeviceContextTarget | None = None
    latest_execution_target: ConversationDeviceContextTarget | None = None
    latest_query_target: ConversationDeviceContextTarget | None = None
    latest_confirmation_target: ConversationDeviceContextTarget | None = None
    resume_target: ConversationDeviceContextTarget | None = None
    recent_targets: list[ConversationDeviceContextTarget] = field(default_factory=list)
    unique_device_ids: list[str] = field(default_factory=list)
    can_resume_control: bool = False
    can_resume_confirmation: bool = False
    resume_reason: str = "最近对话里没有可靠的设备上下文。"

    def to_payload(self) -> dict[str, Any]:
        return {
            "has_context": self.latest_target is not None,
            "can_resume_control": self.can_resume_control,
            "resume_reason": self.resume_reason,
            "unique_device_count": len(self.unique_device_ids),
            "unique_device_ids": list(self.unique_device_ids),
            "latest_target": self.latest_target.to_payload() if self.latest_target is not None else None,
            "latest_execution_target": (
                self.latest_execution_target.to_payload() if self.latest_execution_target is not None else None
            ),
            "latest_query_target": (
                self.latest_query_target.to_payload() if self.latest_query_target is not None else None
            ),
            "latest_confirmation_target": (
                self.latest_confirmation_target.to_payload() if self.latest_confirmation_target is not None else None
            ),
            "resume_target": self.resume_target.to_payload() if self.resume_target is not None else None,
            "recent_targets": [item.to_payload() for item in self.recent_targets],
        }

    def to_prompt_text(self) -> str:
        if self.latest_target is None:
            return "最近对话里没有可靠的设备上下文。"

        effective_resume_target = self.resume_target or self.latest_execution_target or self.latest_query_target or self.latest_target
        lines = ["最近设备上下文摘要："]
        if self.latest_execution_target is not None:
            lines.append(f"- 最近一次成功控制：{self.latest_execution_target.to_prompt_line()}")
        if self.latest_query_target is not None:
            lines.append(f"- 最近一次设备查询：{self.latest_query_target.to_prompt_line()}")
        if self.latest_confirmation_target is not None:
            lines.append(f"- 最近一次待确认控制：{self.latest_confirmation_target.to_prompt_line()}")
        if self.latest_execution_target is None and self.latest_query_target is None and self.latest_target is not None:
            lines.append(f"- 最近一次相关设备：{self.latest_target.to_prompt_line()}")
        if self.can_resume_confirmation and self.latest_confirmation_target is not None:
            lines.append(
                f"- 确认式设备控制可承接：是，回复“是的/确认”等可以继续执行 {self.latest_confirmation_target.device_name} 的 {self.latest_confirmation_target.action or '待确认动作'}。"
            )
        if self.can_resume_control and effective_resume_target is not None:
            lines.append(f"- 省略式设备控制可承接：是，当前唯一可靠目标是 {effective_resume_target.device_name}。")
        else:
            lines.append(f"- 省略式设备控制可承接：否，原因：{self.resume_reason}")
        return "\n".join(lines)

    @classmethod
    def from_payload(cls, value: object) -> "ConversationDeviceContextSummary":
        if not isinstance(value, dict):
            return cls()

        recent_targets: list[ConversationDeviceContextTarget] = []
        raw_recent_targets = value.get("recent_targets")
        if isinstance(raw_recent_targets, list):
            for item in raw_recent_targets:
                target = ConversationDeviceContextTarget.from_payload(item)
                if target is not None:
                    recent_targets.append(target)

        latest_target = ConversationDeviceContextTarget.from_payload(value.get("latest_target"))
        latest_execution_target = ConversationDeviceContextTarget.from_payload(value.get("latest_execution_target"))
        latest_query_target = ConversationDeviceContextTarget.from_payload(value.get("latest_query_target"))
        latest_confirmation_target = ConversationDeviceContextTarget.from_payload(value.get("latest_confirmation_target"))
        resume_target = ConversationDeviceContextTarget.from_payload(value.get("resume_target"))
        unique_device_ids = _normalize_unique_device_ids(value.get("unique_device_ids"))

        if latest_target is None and recent_targets:
            latest_target = recent_targets[0]
        if latest_execution_target is None:
            latest_execution_target = next((item for item in recent_targets if item.resolved_by_execution), None)
        if latest_query_target is None:
            latest_query_target = next((item for item in recent_targets if item.source_type == "device_state"), None)
        if latest_confirmation_target is None:
            latest_confirmation_target = next(
                (item for item in recent_targets if item.source_type == "fast_action_confirmation_request"),
                None,
            )
        if resume_target is None:
            resume_target = latest_execution_target or latest_query_target or latest_target
        if not unique_device_ids:
            for item in recent_targets:
                if item.device_id not in unique_device_ids:
                    unique_device_ids.append(item.device_id)

        resume_reason = str(value.get("resume_reason") or "").strip() or "最近对话里没有可靠的设备上下文。"
        return cls(
            latest_target=latest_target,
            latest_execution_target=latest_execution_target,
            latest_query_target=latest_query_target,
            latest_confirmation_target=latest_confirmation_target,
            resume_target=resume_target,
            recent_targets=recent_targets,
            unique_device_ids=unique_device_ids,
            can_resume_control=bool(value.get("can_resume_control")),
            can_resume_confirmation=bool(value.get("can_resume_confirmation")),
            resume_reason=resume_reason,
        )


EMPTY_CONVERSATION_DEVICE_CONTEXT_SUMMARY = ConversationDeviceContextSummary()


def build_conversation_device_context_summary(
    messages: Sequence[ConversationMessage],
    *,
    max_targets: int = 6,
) -> ConversationDeviceContextSummary:
    targets: list[ConversationDeviceContextTarget] = []
    for message in reversed(list(messages)):
        if message.role != "assistant" or message.status != "completed":
            continue
        targets.extend(_extract_targets_from_message(message))
        if len(targets) >= max_targets:
            break

    recent_targets = targets[:max_targets]
    latest_target = recent_targets[0] if recent_targets else None
    latest_execution_target = next((item for item in recent_targets if item.resolved_by_execution), None)
    latest_query_target = next((item for item in recent_targets if item.source_type == "device_state"), None)
    latest_confirmation_target = next(
        (item for item in recent_targets if item.source_type == "fast_action_confirmation_request"),
        None,
    )

    unique_device_ids: list[str] = []
    for item in recent_targets:
        if item.device_id not in unique_device_ids:
            unique_device_ids.append(item.device_id)

    resume_target = latest_execution_target or latest_query_target or latest_target
    if resume_target is None:
        return ConversationDeviceContextSummary()

    if len(unique_device_ids) > 1:
        return ConversationDeviceContextSummary(
            latest_target=latest_target,
            latest_execution_target=latest_execution_target,
            latest_query_target=latest_query_target,
            latest_confirmation_target=latest_confirmation_target,
            recent_targets=recent_targets,
            unique_device_ids=unique_device_ids,
            can_resume_control=False,
            can_resume_confirmation=_can_resume_confirmation(latest_confirmation_target, unique_device_ids),
            resume_reason=f"最近对话里提到了 {len(unique_device_ids)} 个设备，当前不能省略目标。",
        )

    return ConversationDeviceContextSummary(
        latest_target=latest_target,
        latest_execution_target=latest_execution_target,
        latest_query_target=latest_query_target,
        latest_confirmation_target=latest_confirmation_target,
        resume_target=resume_target,
        recent_targets=recent_targets,
        unique_device_ids=unique_device_ids,
        can_resume_control=True,
        can_resume_confirmation=_can_resume_confirmation(latest_confirmation_target, unique_device_ids),
        resume_reason="最近对话上下文只指向一个设备，可以承接省略式设备控制。",
    )


def _extract_targets_from_message(message: ConversationMessage) -> list[ConversationDeviceContextTarget]:
    facts = load_json(message.facts_json) or []
    if not isinstance(facts, list):
        return []

    targets: list[ConversationDeviceContextTarget] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        fact_type = str(fact.get("type") or "").strip()
        if fact_type == "fast_action_receipt":
            target = _build_target_from_fast_action_receipt(message=message, fact=fact)
            if target is not None:
                targets.append(target)
            continue
        if fact_type == "device_state":
            target = _build_target_from_device_state_fact(message=message, fact=fact)
            if target is not None:
                targets.append(target)
            continue
        if fact_type == "fast_action_confirmation_request":
            target = _build_target_from_fast_action_confirmation_fact(message=message, fact=fact)
            if target is not None:
                targets.append(target)
    return targets


def _build_target_from_fast_action_receipt(
    *,
    message: ConversationMessage,
    fact: dict[str, Any],
) -> ConversationDeviceContextTarget | None:
    extra = fact.get("extra")
    if not isinstance(extra, dict):
        return None
    device = extra.get("device")
    if not isinstance(device, dict):
        return None

    device_id = str(device.get("id") or "").strip()
    device_name = str(device.get("name") or "").strip()
    if not device_id or not device_name:
        return None

    return ConversationDeviceContextTarget(
        source_type="fast_action_receipt",
        message_id=message.id,
        request_id=message.request_id,
        created_at=message.created_at,
        device_id=device_id,
        device_name=device_name,
        device_type=str(device.get("device_type") or "").strip() or None,
        entity_id=str(extra.get("entity_id") or "").strip() or None,
        room_id=str(device.get("room_id") or "").strip() or None,
        room_name=str(device.get("room_name") or "").strip() or None,
        status=None,
        action=str(extra.get("action") or "").strip() or None,
        confidence=_coerce_optional_float(
            ((extra.get("resolution_trace") or {}).get("final_plan") or {}).get("confidence")
            if isinstance(extra.get("resolution_trace"), dict)
            else None
        ),
        resolved_by_execution=True,
    )


def _build_target_from_device_state_fact(
    *,
    message: ConversationMessage,
    fact: dict[str, Any],
) -> ConversationDeviceContextTarget | None:
    extra = fact.get("extra")
    if not isinstance(extra, dict):
        return None

    device_id = str(extra.get("device_id") or "").strip()
    device_name = str(fact.get("label") or extra.get("device_name") or "").strip()
    if not device_id or not device_name:
        return None

    return ConversationDeviceContextTarget(
        source_type="device_state",
        message_id=message.id,
        request_id=message.request_id,
        created_at=message.created_at,
        device_id=device_id,
        device_name=device_name,
        device_type=str(extra.get("device_type") or "").strip() or None,
        entity_id=str(extra.get("entity_id") or "").strip() or None,
        room_id=str(extra.get("room_id") or "").strip() or None,
        room_name=str(extra.get("room_name") or "").strip() or None,
        status=str(extra.get("status") or "").strip() or None,
        action=None,
        confidence=None,
        resolved_by_execution=False,
    )


def _build_target_from_fast_action_confirmation_fact(
    *,
    message: ConversationMessage,
    fact: dict[str, Any],
) -> ConversationDeviceContextTarget | None:
    extra = fact.get("extra")
    if not isinstance(extra, dict):
        return None

    device_id = str(extra.get("device_id") or "").strip()
    device_name = str(extra.get("device_name") or fact.get("label") or "").strip()
    action = str(extra.get("action") or "").strip()
    entity_id = str(extra.get("entity_id") or "").strip()
    if not device_id or not device_name or not action or not entity_id:
        return None

    return ConversationDeviceContextTarget(
        source_type="fast_action_confirmation_request",
        message_id=message.id,
        request_id=message.request_id,
        created_at=message.created_at,
        device_id=device_id,
        device_name=device_name,
        device_type=str(extra.get("device_type") or "").strip() or None,
        entity_id=entity_id,
        room_id=str(extra.get("room_id") or "").strip() or None,
        room_name=str(extra.get("room_name") or "").strip() or None,
        status=None,
        action=action,
        confidence=_coerce_optional_float(extra.get("confidence")),
        resolved_by_execution=False,
    )


def _normalize_unique_device_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _can_resume_confirmation(
    latest_confirmation_target: ConversationDeviceContextTarget | None,
    unique_device_ids: list[str],
) -> bool:
    if latest_confirmation_target is None:
        return False
    if not latest_confirmation_target.entity_id or not latest_confirmation_target.action:
        return False
    return len(unique_device_ids) <= 1 or latest_confirmation_target.device_id in unique_device_ids
