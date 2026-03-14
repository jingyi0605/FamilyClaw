from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import utc_now_iso
from app.modules.agent.service import build_agent_runtime_context
from app.core.logging import dump_conversation_debug_event, get_conversation_debug_logger
from app.modules.device.models import Device
from app.modules.device.service import list_devices
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_action.service import aexecute_device_action, execute_device_action
from app.modules.context.service import get_context_overview
from app.modules.conversation.models import ConversationSession
from app.modules.family_qa.schemas import FamilyQaQueryRequest, FamilyQaQueryResponse
from app.modules.family_qa.service import query_family_qa, stream_family_qa
from app.modules.llm_task import ainvoke_llm, invoke_llm, stream_llm
from app.modules.llm_task.output_models import (
    ConversationIntentCandidateActionOutput,
    ConversationIntentDetectionOutput,
    ReminderExtractionOutput,
)
from app.modules.memory.context_engine import build_memory_context_bundle
from app.modules.member import service as member_service


INTENT_FALLBACK_THRESHOLD = 0.6
INTENT_HISTORY_LIMIT = 6
INTENT_DETECTION_TIMEOUT_MS = 4000
FREE_CHAT_DEGRADED_TIMEOUT_MS = 8000


class ConversationIntentLabel(StrEnum):
    FREE_CHAT = "free_chat"
    STRUCTURED_QA = "structured_qa"
    CONFIG_CHANGE = "config_change"
    MEMORY_WRITE = "memory_write"
    REMINDER_CREATE = "reminder_create"


class ConversationIntent(StrEnum):
    FAST_ACTION = "fast_action"
    STRUCTURED_QA = "structured_qa"
    FREE_CHAT = "free_chat"
    CONFIG_EXTRACTION = "config_extraction"
    MEMORY_EXTRACTION = "memory_extraction"
    REMINDER_EXTRACTION = "reminder_extraction"


class ConversationLane(StrEnum):
    FAST_ACTION = "fast_action"
    REALTIME_QUERY = "realtime_query"
    FREE_CHAT = "free_chat"


@dataclass
class ConversationLaneSelection:
    lane: ConversationLane
    confidence: float = 0.0
    reason: str = ""
    target_kind: str = "none"
    requires_clarification: bool = False
    source: str = "intent_mapping"

    def to_payload(self) -> dict:
        return {
            "lane": self.lane.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "target_kind": self.target_kind,
            "requires_clarification": self.requires_clarification,
            "source": self.source,
        }


@dataclass(frozen=True)
class FastActionPlan:
    device: Device
    action: str
    confirm_high_risk: bool


@dataclass
class ConversationIntentDetection:
    primary_intent: ConversationIntentLabel
    secondary_intents: list[ConversationIntentLabel] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    candidate_actions: list[ConversationIntentCandidateActionOutput] = field(default_factory=list)
    route_intent: ConversationIntent = ConversationIntent.FREE_CHAT
    guardrail_rule: str | None = None
    lane_selection: ConversationLaneSelection | None = None

    def to_payload(self) -> dict:
        return {
            "primary_intent": self.primary_intent.value,
            "secondary_intents": [item.value for item in self.secondary_intents],
            "confidence": self.confidence,
            "reason": self.reason,
            "candidate_actions": [item.model_dump(mode="json") for item in self.candidate_actions],
            "route_intent": self.route_intent.value,
            "guardrail_rule": self.guardrail_rule,
            "lane_selection": self.lane_selection.to_payload() if self.lane_selection is not None else None,
        }


@dataclass
class ConversationOrchestratorResult:
    intent: ConversationIntent
    text: str
    degraded: bool
    facts: list[dict]
    suggestions: list[str]
    memory_candidate_payloads: list[dict]
    config_suggestion: dict | None
    action_payloads: list[dict]
    ai_trace_id: str | None
    ai_provider_code: str | None
    effective_agent_id: str | None
    effective_agent_name: str | None
    intent_detection: ConversationIntentDetection | None = None
    lane_selection: ConversationLaneSelection | None = None

    def __post_init__(self) -> None:
        if self.intent_detection is None:
            self.intent_detection = _build_default_intent_detection(self.intent)
        if self.lane_selection is None:
            self.lane_selection = (
                self.intent_detection.lane_selection
                if self.intent_detection is not None and self.intent_detection.lane_selection is not None
                else _build_default_lane_selection(self.intent)
            )


def detect_conversation_intent(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
    request_context: dict | None = None,
) -> ConversationIntentDetection:
    normalized_message = message.strip()
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="intent_detection.started",
        message="开始执行 AI 意图识别。",
        payload={"message": normalized_message},
    )
    if session.session_mode == "agent_config":
        detection = _build_guardrail_intent_detection(
            primary_intent=ConversationIntentLabel.CONFIG_CHANGE,
            route_intent=ConversationIntent.CONFIG_EXTRACTION,
            reason="当前会话处于 agent_config 模式，本轮直接按配置修改处理。",
            guardrail_rule="session_mode.agent_config",
        )
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection
    if not normalized_message:
        detection = _build_fallback_intent_detection("用户消息为空，按 free_chat 处理。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    try:
        result = invoke_llm(
            db,
            task_type="conversation_intent_detection",
            variables=_build_intent_detection_variables(
                session=session,
                message=normalized_message,
                conversation_history=conversation_history or [],
            ),
            household_id=session.household_id,
            request_context=request_context,
            timeout_ms_override=INTENT_DETECTION_TIMEOUT_MS,
            honor_timeout_override=True,
        )
    except Exception:
        detection = _build_fallback_intent_detection("意图识别模型调用失败，按 free_chat 回落。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    if not isinstance(result.data, ConversationIntentDetectionOutput):
        detection = _build_fallback_intent_detection("意图识别结果不可解析，按 free_chat 回落。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    detection = _normalize_intent_detection(result.data)
    _log_intent_detection_result(request_context=request_context, detection=detection)
    return detection


async def adetect_conversation_intent(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    conversation_history: list[dict[str, str]],
    request_context: dict | None = None,
) -> ConversationIntentDetection:
    normalized_message = message.strip()
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="intent_detection.started",
        message="开始执行 AI 意图识别。",
        payload={"message": normalized_message},
    )
    if session.session_mode == "agent_config":
        detection = _build_guardrail_intent_detection(
            primary_intent=ConversationIntentLabel.CONFIG_CHANGE,
            route_intent=ConversationIntent.CONFIG_EXTRACTION,
            reason="当前会话处于 agent_config 模式，本轮直接按配置修改处理。",
            guardrail_rule="session_mode.agent_config",
        )
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection
    if not normalized_message:
        detection = _build_fallback_intent_detection("用户消息为空，按 free_chat 处理。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    try:
        result = await ainvoke_llm(
            db,
            task_type="conversation_intent_detection",
            variables=_build_intent_detection_variables(
                session=session,
                message=normalized_message,
                conversation_history=conversation_history or [],
            ),
            household_id=session.household_id,
            request_context=request_context,
            timeout_ms_override=INTENT_DETECTION_TIMEOUT_MS,
            honor_timeout_override=True,
        )
    except Exception:
        detection = _build_fallback_intent_detection("意图识别模型调用失败，按 free_chat 回落。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    if not isinstance(result.data, ConversationIntentDetectionOutput):
        detection = _build_fallback_intent_detection("意图识别结果不可解析，按 free_chat 回落。")
        _log_intent_detection_result(request_context=request_context, detection=detection)
        return detection

    detection = _normalize_intent_detection(result.data)
    _log_intent_detection_result(request_context=request_context, detection=detection)
    return detection


def run_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    detection = detect_conversation_intent(
        db,
        session=session,
        message=message,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    lane_selection = select_conversation_lane(
        session=session,
        message=message,
        detection=detection,
        request_context=request_context,
    )
    _log_route_selection(request_context=request_context, detection=detection)
    if settings.conversation_lane_shadow_enabled and not settings.conversation_lane_takeover_enabled:
        _log_lane_shadow_result(request_context=request_context, detection=detection, lane_selection=lane_selection)
    if lane_selection.lane == ConversationLane.REALTIME_QUERY and settings.conversation_lane_takeover_enabled:
        result = _run_structured_qa(
            db,
            session=session,
            message=message,
            actor=actor,
            conversation_history=conversation_history,
            request_context=request_context,
        )
        return _attach_lane_selection(
            _from_family_qa_result(ConversationIntent.STRUCTURED_QA, result, detection=detection),
            lane_selection=lane_selection,
        )
    if lane_selection.lane == ConversationLane.FAST_ACTION and settings.conversation_lane_takeover_enabled:
        return _run_fast_action_lane(
            db,
            session=session,
            message=message,
            actor=actor,
            detection=detection,
            lane_selection=lane_selection,
            request_context=request_context,
        )
    return _run_non_realtime_lane(
        db,
        session=session,
        message=message,
        actor=actor,
        conversation_history=conversation_history,
        detection=detection,
        lane_selection=lane_selection,
        request_context=request_context,
    )


async def stream_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    request_context: dict | None = None,
):
    detection = await adetect_conversation_intent(
        db,
        session=session,
        message=message,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    lane_selection = select_conversation_lane(
        session=session,
        message=message,
        detection=detection,
        request_context=request_context,
    )
    _log_route_selection(request_context=request_context, detection=detection)
    if settings.conversation_lane_shadow_enabled and not settings.conversation_lane_takeover_enabled:
        _log_lane_shadow_result(request_context=request_context, detection=detection, lane_selection=lane_selection)
    if lane_selection.lane == ConversationLane.REALTIME_QUERY and settings.conversation_lane_takeover_enabled:
        async for event_type, event_payload in stream_family_qa(
            db,
            FamilyQaQueryRequest(
                household_id=session.household_id,
                requester_member_id=session.requester_member_id,
                agent_id=session.active_agent_id,
                question=message,
                channel="conversation_turn",
                context={"conversation_history": conversation_history, "request_context": request_context or {}},
            ),
            actor,
        ):
            if event_type == "done":
                yield event_type, _attach_lane_selection(
                    _from_family_qa_result(
                        ConversationIntent.STRUCTURED_QA,
                        cast(FamilyQaQueryResponse, event_payload),
                        detection=detection,
                    ),
                    lane_selection=lane_selection,
                )
            else:
                yield event_type, event_payload
        return
    if lane_selection.lane == ConversationLane.FAST_ACTION and settings.conversation_lane_takeover_enabled:
        yield "done", await _arun_fast_action_lane(
            db,
            session=session,
            message=message,
            actor=actor,
            detection=detection,
            lane_selection=lane_selection,
            request_context=request_context,
        )
        return
    async for event_type, event_payload in _stream_non_realtime_lane(
        db,
        session=session,
        message=message,
        actor=actor,
        conversation_history=conversation_history,
        detection=detection,
        lane_selection=lane_selection,
        request_context=request_context,
    ):
        yield event_type, event_payload


def _run_structured_qa(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    request_context: dict | None = None,
) -> FamilyQaQueryResponse:
    return query_family_qa(
        db,
        FamilyQaQueryRequest(
            household_id=session.household_id,
            requester_member_id=session.requester_member_id,
            agent_id=session.active_agent_id,
            question=message,
            channel="conversation_turn",
            context={"conversation_history": conversation_history, "request_context": request_context or {}},
        ),
        actor,
    )


def select_conversation_lane(
    *,
    session: ConversationSession,
    message: str,
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationLaneSelection:
    _ = request_context
    if session.session_mode == "agent_config":
        selection = ConversationLaneSelection(
            lane=ConversationLane.FREE_CHAT,
            confidence=1.0,
            reason="当前会话处于 agent_config 模式，主回复先按 free_chat 处理，配置变更走后续兼容链路。",
            target_kind="none",
            requires_clarification=False,
            source="session_mode",
        )
        detection.lane_selection = selection
        return selection
    if _looks_like_fast_action_request(message):
        selection = ConversationLaneSelection(
            lane=ConversationLane.FAST_ACTION,
            confidence=0.78,
            reason="命中设备快控硬信号，优先进入 fast_action 车道。",
            target_kind="device_action",
            requires_clarification=False,
            source="hard_signal",
        )
        detection.lane_selection = selection
        return selection
    selection = _build_lane_selection_from_intent(detection.route_intent)
    detection.lane_selection = selection
    return selection


def _run_non_realtime_lane(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    if settings.conversation_lane_takeover_enabled:
        return _attach_lane_selection(
            _run_non_qa_chat(
                db,
                intent=ConversationIntent.FREE_CHAT,
                session=session,
                message=message,
                actor=actor,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
    intent = detection.route_intent
    if intent == ConversationIntent.CONFIG_EXTRACTION:
        return _attach_lane_selection(
            _run_config_extraction(
                db,
                session=session,
                message=message,
                actor=actor,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
    if intent == ConversationIntent.MEMORY_EXTRACTION:
        return _attach_lane_selection(
            _run_memory_extraction(
                db,
                session=session,
                message=message,
                actor=actor,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
    if intent == ConversationIntent.REMINDER_EXTRACTION:
        return _attach_lane_selection(
            _run_reminder_extraction(
                db,
                session=session,
                message=message,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
    return _attach_lane_selection(
        _run_non_qa_chat(
            db,
            intent=intent,
            session=session,
            message=message,
            actor=actor,
            conversation_history=conversation_history,
            detection=detection,
            request_context=request_context,
        ),
        lane_selection=lane_selection,
    )


def _run_fast_action_lane(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    plan, clarification = _resolve_fast_action_plan(
        db,
        session=session,
        message=message,
        actor=actor,
    )
    if clarification is not None:
        return _attach_lane_selection(clarification, lane_selection=lane_selection)
    assert plan is not None
    try:
        response, _ = execute_device_action(
            db,
            payload=DeviceActionExecuteRequest(
                household_id=session.household_id,
                device_id=plan.device.id,
                action=cast(str, plan.action),
                params={},
                reason="conversation.fast_action",
                confirm_high_risk=plan.confirm_high_risk,
            ),
        )
    except Exception as exc:
        return _attach_lane_selection(
            ConversationOrchestratorResult(
                intent=ConversationIntent.FAST_ACTION,
                text=f"我知道你想立刻控制设备，但这次执行失败了：{exc}",
                degraded=False,
                facts=[],
                suggestions=["换个更明确的说法", "稍后再试一次"],
                memory_candidate_payloads=[],
                config_suggestion=None,
                action_payloads=[],
                ai_trace_id=None,
                ai_provider_code=None,
                effective_agent_id=session.active_agent_id,
                effective_agent_name=None,
                intent_detection=detection,
            ),
            lane_selection=lane_selection,
        )
    receipt = {
        "type": "fast_action_receipt",
        "label": "设备动作执行结果",
        "source": "conversation_fast_action",
        "extra": response.model_dump(mode="json"),
    }
    return _attach_lane_selection(
        ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text=_build_fast_action_success_reply(device_name=response.device.name, action=response.action),
            degraded=False,
            facts=[receipt],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        ),
        lane_selection=lane_selection,
    )


async def _arun_fast_action_lane(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    plan, clarification = _resolve_fast_action_plan(
        db,
        session=session,
        message=message,
        actor=actor,
    )
    if clarification is not None:
        return _attach_lane_selection(clarification, lane_selection=lane_selection)
    assert plan is not None
    try:
        response, _ = await aexecute_device_action(
            db,
            payload=DeviceActionExecuteRequest(
                household_id=session.household_id,
                device_id=plan.device.id,
                action=cast(str, plan.action),
                params={},
                reason="conversation.fast_action",
                confirm_high_risk=plan.confirm_high_risk,
            ),
        )
    except Exception as exc:
        return _attach_lane_selection(
            ConversationOrchestratorResult(
                intent=ConversationIntent.FAST_ACTION,
                text=f"我知道你想立刻控制设备，但这次执行失败了：{exc}",
                degraded=False,
                facts=[],
                suggestions=["换个更明确的说法", "稍后再试一次"],
                memory_candidate_payloads=[],
                config_suggestion=None,
                action_payloads=[],
                ai_trace_id=None,
                ai_provider_code=None,
                effective_agent_id=session.active_agent_id,
                effective_agent_name=None,
                intent_detection=detection,
            ),
            lane_selection=lane_selection,
        )
    receipt = {
        "type": "fast_action_receipt",
        "label": "设备动作执行结果",
        "source": "conversation_fast_action",
        "extra": response.model_dump(mode="json"),
    }
    return _attach_lane_selection(
        ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text=_build_fast_action_success_reply(device_name=response.device.name, action=response.action),
            degraded=False,
            facts=[receipt],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        ),
        lane_selection=lane_selection,
    )


async def _stream_non_realtime_lane(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
    request_context: dict | None = None,
):
    if settings.conversation_lane_takeover_enabled:
        async for event_type, event_payload in _stream_non_qa_chat(
            db,
            intent=ConversationIntent.FREE_CHAT,
            session=session,
            message=message,
            actor=actor,
            conversation_history=conversation_history,
            detection=detection,
            lane_selection=lane_selection,
            request_context=request_context,
        ):
            yield event_type, event_payload
        return
    intent = detection.route_intent
    if intent == ConversationIntent.CONFIG_EXTRACTION:
        yield "done", _attach_lane_selection(
            await _arun_config_extraction(
                db,
                session=session,
                message=message,
                actor=actor,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
        return
    if intent == ConversationIntent.MEMORY_EXTRACTION:
        yield "done", _attach_lane_selection(
            await _arun_memory_extraction(
                db,
                session=session,
                message=message,
                actor=actor,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
        return
    if intent == ConversationIntent.REMINDER_EXTRACTION:
        yield "done", _attach_lane_selection(
            await _arun_reminder_extraction(
                db,
                session=session,
                message=message,
                conversation_history=conversation_history,
                detection=detection,
                request_context=request_context,
            ),
            lane_selection=lane_selection,
        )
        return
    async for event_type, event_payload in _stream_non_qa_chat(
        db,
        intent=intent,
        session=session,
        message=message,
        actor=actor,
        conversation_history=conversation_history,
        detection=detection,
        lane_selection=lane_selection,
        request_context=request_context,
    ):
        yield event_type, event_payload


def _attach_lane_selection(
    result: ConversationOrchestratorResult,
    *,
    lane_selection: ConversationLaneSelection,
) -> ConversationOrchestratorResult:
    result.lane_selection = lane_selection
    if result.intent_detection is not None:
        result.intent_detection.lane_selection = lane_selection
    return result


def _build_default_lane_selection(intent: ConversationIntent) -> ConversationLaneSelection:
    return _build_lane_selection_from_intent(intent)


def _build_lane_selection_from_intent(intent: ConversationIntent) -> ConversationLaneSelection:
    if intent == ConversationIntent.FAST_ACTION:
        return ConversationLaneSelection(
            lane=ConversationLane.FAST_ACTION,
            confidence=1.0,
            reason="当前编排默认把 fast_action 结果归到快执行车道。",
            target_kind="device_action",
            requires_clarification=False,
            source="intent_mapping",
        )
    if intent == ConversationIntent.STRUCTURED_QA:
        return ConversationLaneSelection(
            lane=ConversationLane.REALTIME_QUERY,
            confidence=1.0,
            reason="当前编排默认把 structured_qa 归到 realtime_query 车道。",
            target_kind="state_query",
            requires_clarification=False,
            source="intent_mapping",
        )
    return ConversationLaneSelection(
        lane=ConversationLane.FREE_CHAT,
        confidence=1.0,
        reason="当前编排默认把 free_chat、memory、config、reminder 归到 free_chat 车道。",
        target_kind="none",
        requires_clarification=False,
        source="intent_mapping",
    )


def _resolve_fast_action_plan(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
) -> tuple[FastActionPlan | None, ConversationOrchestratorResult | None]:
    if actor.account_type != "system" and actor.member_role != "admin":
        return None, ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text="当前账号没有设备快控权限。请让管理员执行，或者改成普通聊天确认后再操作。",
            degraded=False,
            facts=[],
            suggestions=["请管理员执行", "改成普通聊天确认后操作"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )

    devices, _ = list_devices(
        db,
        household_id=session.household_id,
        page=1,
        page_size=500,
    )
    controllable_devices = [item for item in devices if bool(item.controllable) and item.status == "active"]
    action = _infer_fast_action(message=message, devices=controllable_devices)
    if action is None:
        return None, ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text="我知道你像是在控制设备，但动作还不够明确。请直接说“打开/关闭/停止/锁上/解锁 + 设备名”。",
            degraded=False,
            facts=[],
            suggestions=["把客厅灯关掉", "打开卧室空调", "锁上门锁"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )

    matched_devices = _match_fast_action_devices(message=message, devices=controllable_devices, action=action)
    if not matched_devices:
        return None, ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text="我还没定位到你要控制的设备。请把设备名说得更明确一点，比如“把客厅灯关掉”。",
            degraded=False,
            facts=[],
            suggestions=[item.name for item in controllable_devices[:3]],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )
    if len(matched_devices) > 1:
        return None, ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text="我找到了多个可能的设备，还不敢直接执行。请你明确指定其中一个。",
            degraded=False,
            facts=[],
            suggestions=[item.name for item in matched_devices[:3]],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )

    device = matched_devices[0]
    if action == "unlock" and not _is_high_risk_confirmation_present(message):
        return None, ConversationOrchestratorResult(
            intent=ConversationIntent.FAST_ACTION,
            text=f"解锁 {device.name} 属于高风险动作。请明确说“确认解锁{device.name}”后我再执行。",
            degraded=False,
            facts=[],
            suggestions=[f"确认解锁{device.name}", f"先查询{device.name}状态"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )
    return FastActionPlan(
        device=device,
        action=action,
        confirm_high_risk=action == "unlock" and _is_high_risk_confirmation_present(message),
    ), None


def _infer_fast_action(message: str, devices: list[Device]) -> str | None:
    normalized = _normalize_fast_action_text(message)
    device_types = {item.device_type for item in devices}
    keyword_groups: list[tuple[str, tuple[str, ...], set[str] | None]] = [
        ("unlock", ("确认解锁", "解锁"), {"lock"}),
        ("lock", ("锁上", "上锁", "锁门"), {"lock"}),
        ("stop", ("停止", "停下"), {"curtain"}),
        ("open", ("拉开", "打开"), {"curtain"}),
        ("close", ("拉上", "合上", "关闭"), {"curtain"}),
        ("turn_on", ("打开", "开启", "开一下", "开"), {"light", "ac", "speaker"}),
        ("turn_off", ("关掉", "关闭", "关上", "关"), {"light", "ac", "speaker"}),
    ]
    for action, keywords, supported_types in keyword_groups:
        if supported_types is not None and not (device_types & supported_types):
            continue
        if any(keyword in normalized for keyword in keywords):
            return action
    return None


def _match_fast_action_devices(message: str, devices: list[Device], action: str) -> list[Device]:
    normalized = _normalize_fast_action_text(message)
    scored_devices: list[tuple[int, Device]] = []
    for device in devices:
        if action not in _supported_actions_for_device_type(device.device_type):
            continue
        score = _score_device_match(normalized, device)
        if score <= 0:
            continue
        scored_devices.append((score, device))
    if not scored_devices:
        return []
    scored_devices.sort(key=lambda item: (-item[0], item[1].name))
    top_score = scored_devices[0][0]
    if top_score < 2:
        return []
    return [device for score, device in scored_devices if score == top_score]


def _score_device_match(message: str, device: Device) -> int:
    normalized_name = _normalize_fast_action_text(device.name)
    if not normalized_name:
        return 0
    if normalized_name in message:
        return 10
    score = 0
    if _device_type_alias(device.device_type) in message:
        score += 2
    for char in set(normalized_name):
        if char in message and char not in {"开", "关", "打", "停", "锁"}:
            score += 1
    if normalized_name.endswith(_device_type_alias(device.device_type)):
        short_alias = normalized_name.replace("主", "")
        if short_alias and short_alias in message:
            score += 3
    return score


def _supported_actions_for_device_type(device_type: str) -> set[str]:
    mapping = {
        "light": {"turn_on", "turn_off"},
        "ac": {"turn_on", "turn_off"},
        "curtain": {"open", "close", "stop"},
        "speaker": {"turn_on", "turn_off"},
        "lock": {"lock", "unlock"},
    }
    return mapping.get(device_type, set())


def _device_type_alias(device_type: str) -> str:
    aliases = {
        "light": "灯",
        "ac": "空调",
        "curtain": "窗帘",
        "speaker": "音箱",
        "lock": "门锁",
    }
    return aliases.get(device_type, "")


def _normalize_fast_action_text(text: str) -> str:
    normalized = text.strip().lower()
    for token in (" ", "，", "。", "？", "！", ",", ".", "?", "!", "请", "帮我", "给我", "一下", "立刻", "马上", "把", "将"):
        normalized = normalized.replace(token, "")
    return normalized


def _is_high_risk_confirmation_present(message: str) -> bool:
    normalized = _normalize_fast_action_text(message)
    return "确认" in normalized or "确定" in normalized


def _build_fast_action_success_reply(*, device_name: str, action: str) -> str:
    action_text = {
        "turn_on": "打开",
        "turn_off": "关闭",
        "open": "打开",
        "close": "关闭",
        "stop": "停止",
        "lock": "锁上",
        "unlock": "解锁",
    }.get(action, "执行")
    return f"已为你{action_text}{device_name}。"


def _looks_like_fast_action_request(message: str) -> bool:
    normalized = _normalize_fast_action_text(message)
    action_keywords = ("打开", "开启", "关掉", "关闭", "关上", "停止", "锁上", "解锁", "拉开", "拉上")
    device_keywords = ("灯", "空调", "窗帘", "门锁", "音箱", "设备")
    return any(keyword in normalized for keyword in action_keywords) and any(keyword in normalized for keyword in device_keywords)


async def _stream_non_qa_chat(
    db: Session,
    *,
    intent: ConversationIntent,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
    request_context: dict | None = None,
):
    if intent == ConversationIntent.FREE_CHAT and detection.guardrail_rule == "fallback.free_chat":
        _log_orchestrator_debug_event(
            request_context=request_context,
            stage="orchestrator.free_chat.degraded",
            message="意图识别已降级，本轮 free_chat 改走非流式短超时兜底。",
            payload={"timeout_ms": FREE_CHAT_DEGRADED_TIMEOUT_MS},
        )
        result = _run_non_qa_chat(
            db,
            intent=intent,
            session=session,
            message=message,
            actor=actor,
            conversation_history=conversation_history,
            detection=detection,
            request_context=request_context,
            timeout_ms_override=FREE_CHAT_DEGRADED_TIMEOUT_MS,
            honor_timeout_override=True,
        )
        if result.text:
            yield "chunk", result.text
        yield "done", _attach_lane_selection(result, lane_selection=lane_selection)
        return

    full_text = ""
    async for event in stream_llm(
        db,
        task_type="free_chat",
        variables=_build_free_chat_variables(
            db,
            session=session,
            actor=actor,
            user_message=message,
            request_context=request_context,
            log_memory_context=True,
        ),
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
    ):
        if event.event_type == "chunk":
            full_text += event.content
            yield "chunk", event.content
            continue
        if event.event_type == "done" and event.result is not None:
            text = event.result.text or full_text
            yield "done", _attach_lane_selection(
                ConversationOrchestratorResult(
                    intent=intent,
                    text=text,
                    degraded=False,
                    facts=[],
                    suggestions=[],
                    memory_candidate_payloads=[],
                    config_suggestion=None,
                    action_payloads=[],
                    ai_trace_id=None,
                    ai_provider_code=getattr(event.result, "provider", None) or None,
                    effective_agent_id=session.active_agent_id,
                    effective_agent_name=None,
                    intent_detection=detection,
                ),
                lane_selection=lane_selection,
            )


def _run_non_qa_chat(
    db: Session,
    *,
    intent: ConversationIntent,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
    timeout_ms_override: int | None = None,
    honor_timeout_override: bool = False,
) -> ConversationOrchestratorResult:
    result = invoke_llm(
        db,
        task_type="free_chat",
        variables=_build_free_chat_variables(
            db,
            session=session,
            actor=actor,
            user_message=message,
            request_context=request_context,
            log_memory_context=True,
        ),
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
        timeout_ms_override=timeout_ms_override,
        honor_timeout_override=honor_timeout_override,
    )
    return ConversationOrchestratorResult(
        intent=intent,
        text=result.text,
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


def _run_config_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    _ = actor
    variables = _build_free_chat_variables(
        db,
        session=session,
        actor=actor,
        user_message=message,
        request_context=request_context,
        log_memory_context=False,
    )
    current_config = _build_current_config_snapshot(db, session=session, actor=actor, user_message=message)
    user_evidence = _build_user_only_conversation_excerpt(conversation_history, message)
    extraction_result = invoke_llm(
        db,
        task_type="config_extraction",
        variables={
            "agent_context": variables["agent_context"],
            "current_config": _render_config_draft(current_config),
            "conversation_excerpt": user_evidence,
            "user_message": message,
        },
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    parsed = extraction_result.data
    suggestion = _normalize_config_suggestion(
        suggestion=_retain_config_values_with_user_evidence(
            suggestion=_build_config_suggestion(parsed),
            user_evidence=user_evidence,
        ),
        current_config=current_config,
    )
    text = _build_config_dialogue_reply(message=message, suggestion=suggestion)
    facts = (
        [{"type": "config_suggestion", "label": "Agent 配置建议", "source": "conversation_orchestrator", "extra": suggestion}]
        if any(suggestion.values())
        else []
    )
    suggestions = (
        ["继续补充配置要求", "确认配置建议"]
        if any(suggestion.values())
        else ["修改名字", "调整说话风格", "补充性格标签"]
    )
    return ConversationOrchestratorResult(
        intent=ConversationIntent.CONFIG_EXTRACTION,
        text=text,
        degraded=False,
        facts=facts,
        suggestions=suggestions,
        memory_candidate_payloads=[],
        config_suggestion=suggestion if any(suggestion.values()) else None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(extraction_result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


async def _arun_config_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    variables = _build_free_chat_variables(
        db,
        session=session,
        actor=actor,
        user_message=message,
        request_context=request_context,
        log_memory_context=False,
    )
    current_config = _build_current_config_snapshot(db, session=session, actor=actor, user_message=message)
    user_evidence = _build_user_only_conversation_excerpt(conversation_history, message)
    extraction_result = await ainvoke_llm(
        db,
        task_type="config_extraction",
        variables={
            "agent_context": variables["agent_context"],
            "current_config": _render_config_draft(current_config),
            "conversation_excerpt": user_evidence,
            "user_message": message,
        },
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    parsed = extraction_result.data
    suggestion = _normalize_config_suggestion(
        suggestion=_retain_config_values_with_user_evidence(
            suggestion=_build_config_suggestion(parsed),
            user_evidence=user_evidence,
        ),
        current_config=current_config,
    )
    text = _build_config_dialogue_reply(message=message, suggestion=suggestion)
    facts = (
        [{"type": "config_suggestion", "label": "Agent 配置建议", "source": "conversation_orchestrator", "extra": suggestion}]
        if any(suggestion.values())
        else []
    )
    suggestions = (
        ["继续补充配置要求", "确认配置建议"]
        if any(suggestion.values())
        else ["修改名字", "调整说话风格", "补充性格标签"]
    )
    return ConversationOrchestratorResult(
        intent=ConversationIntent.CONFIG_EXTRACTION,
        text=text,
        degraded=False,
        facts=facts,
        suggestions=suggestions,
        memory_candidate_payloads=[],
        config_suggestion=suggestion if any(suggestion.values()) else None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(extraction_result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


def _run_memory_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    _ = actor
    result = invoke_llm(
        db,
        task_type="memory_extraction",
        variables={
            "conversation": _build_conversation_excerpt(conversation_history, message),
            "member_context": _build_member_context(db, household_id=session.household_id),
        },
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    parsed = result.data
    if parsed is None or not parsed.memories:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="我没有从这轮话里整理出足够稳的长期记忆。你可以直接告诉我“记住什么”，别让我猜。",
            degraded=False,
            facts=[],
            suggestions=["明确告诉我要记住什么", "换一种更直接的说法"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=getattr(result, "provider", None) or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        )

    candidates: list[dict] = []
    for item in parsed.memories[:5]:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("content") or "").strip()
        if not summary:
            continue
        candidates.append(
            {
                "memory_type": str(item.get("type") or item.get("memory_type") or "fact"),
                "title": str(item.get("title") or "").strip() or summary[:18],
                "summary": summary,
                "content": item,
                "confidence": float(item.get("confidence") or 0.75),
            }
        )
    return ConversationOrchestratorResult(
        intent=ConversationIntent.MEMORY_EXTRACTION,
        text="我已经整理出记忆候选了。它们现在只是候选，不会自己落库。",
        degraded=False,
        facts=[],
        suggestions=["确认写入记忆", "忽略这次提取"],
        memory_candidate_payloads=candidates,
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


async def _arun_memory_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    _ = actor
    result = await ainvoke_llm(
        db,
        task_type="memory_extraction",
        variables={
            "conversation": _build_conversation_excerpt(conversation_history, message),
            "member_context": _build_member_context(db, household_id=session.household_id),
        },
        household_id=session.household_id,
        conversation_history=conversation_history,
        request_context=request_context,
    )
    parsed = result.data
    if parsed is None or not parsed.memories:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="我没有从这轮话里整理出足够稳的长期记忆。你可以直接告诉我“记住什么”，别让我猜。",
            degraded=False,
            facts=[],
            suggestions=["明确告诉我要记住什么", "换一种更直接的说法"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=getattr(result, "provider", None) or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        )

    candidates: list[dict] = []
    for item in parsed.memories[:5]:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("content") or "").strip()
        if not summary:
            continue
        candidates.append(
            {
                "memory_type": str(item.get("type") or item.get("memory_type") or "fact"),
                "title": str(item.get("title") or "").strip() or summary[:18],
                "summary": summary,
                "content": item,
                "confidence": float(item.get("confidence") or 0.75),
            }
        )
    return ConversationOrchestratorResult(
        intent=ConversationIntent.MEMORY_EXTRACTION,
        text="我已经整理出记忆候选了。它们现在只是候选，不会自己落库。",
        degraded=False,
        facts=[],
        suggestions=["确认写入记忆", "忽略这次提取"],
        memory_candidate_payloads=candidates,
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


def _run_reminder_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    result = invoke_llm(
        db,
        task_type="reminder_extraction",
        variables={
            "current_time": utc_now_iso(),
            "conversation_excerpt": _build_conversation_excerpt(conversation_history, message),
            "user_message": message,
        },
        household_id=session.household_id,
        request_context=request_context,
    )
    parsed = result.data
    if not isinstance(parsed, ReminderExtractionOutput) or not parsed.should_create or not parsed.title or not parsed.trigger_at:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.REMINDER_EXTRACTION,
            text="我理解你像是在创建提醒，但这轮信息还不够完整。请直接告诉我提醒内容和具体时间，比如“明天早上 8 点提醒我带钥匙”。",
            degraded=False,
            facts=[],
            suggestions=["补充提醒时间", "补充提醒内容"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=getattr(result, "provider", None) or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        )

    reminder_payload = {
        "action_type": "reminder_create",
        "title": parsed.title.strip(),
        "description": (parsed.description or "").strip() or None,
        "trigger_at": parsed.trigger_at,
        "schedule_kind": "once",
    }
    text_lines = [
        "我已经把这轮话整理成提醒动作：",
        f"- 提醒内容：{reminder_payload['title']}",
        f"- 触发时间：{reminder_payload['trigger_at']}",
        "接下来是否执行，仍然交给策略层处理，不会因为识别到了就偷偷建提醒。",
    ]
    if reminder_payload["description"]:
        text_lines.insert(2, f"- 说明：{reminder_payload['description']}")
    return ConversationOrchestratorResult(
        intent=ConversationIntent.REMINDER_EXTRACTION,
        text="\n".join(text_lines),
        degraded=False,
        facts=[{"type": "reminder_draft", "label": "提醒草稿", "source": "conversation_orchestrator", "extra": reminder_payload}],
        suggestions=["确认提醒", "修改提醒时间"],
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[reminder_payload],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


async def _arun_reminder_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    conversation_history: list[dict[str, str]],
    detection: ConversationIntentDetection,
    request_context: dict | None = None,
) -> ConversationOrchestratorResult:
    result = await ainvoke_llm(
        db,
        task_type="reminder_extraction",
        variables={
            "current_time": utc_now_iso(),
            "conversation_excerpt": _build_conversation_excerpt(conversation_history, message),
            "user_message": message,
        },
        household_id=session.household_id,
        request_context=request_context,
    )
    parsed = result.data
    if not isinstance(parsed, ReminderExtractionOutput) or not parsed.should_create or not parsed.title or not parsed.trigger_at:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.REMINDER_EXTRACTION,
            text="我理解你像是在创建提醒，但这轮信息还不够完整。请直接告诉我提醒内容和具体时间，比如“明天早上 8 点提醒我带钥匙”。",
            degraded=False,
            facts=[],
            suggestions=["补充提醒时间", "补充提醒内容"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code=getattr(result, "provider", None) or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
            intent_detection=detection,
        )

    return ConversationOrchestratorResult(
        intent=ConversationIntent.REMINDER_EXTRACTION,
        text=f"我整理出一个提醒候选：{parsed.title}，时间是 {parsed.trigger_at}。确认后我再真正创建。",
        degraded=False,
        facts=[],
        suggestions=["确认创建提醒", "修改提醒内容"],
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[parsed.model_dump(mode="json")],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


def _from_family_qa_result(
    intent: ConversationIntent,
    result: FamilyQaQueryResponse,
    *,
    detection: ConversationIntentDetection,
) -> ConversationOrchestratorResult:
    return ConversationOrchestratorResult(
        intent=intent,
        text=result.answer,
        degraded=result.degraded or result.ai_degraded,
        facts=[item.model_dump(mode="json") for item in result.facts],
        suggestions=result.suggestions,
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=result.ai_trace_id,
        ai_provider_code=result.ai_provider_code,
        effective_agent_id=result.effective_agent_id,
        effective_agent_name=result.effective_agent_name,
        intent_detection=detection,
    )


def _build_free_chat_variables(
    db: Session,
    *,
    session: ConversationSession,
    actor: ActorContext,
    user_message: str,
    request_context: dict | None = None,
    log_memory_context: bool = False,
) -> dict[str, str]:
    agent_context = build_agent_runtime_context(
        db,
        household_id=session.household_id,
        agent_id=session.active_agent_id,
        requester_member_id=session.requester_member_id,
    )
    overview = get_context_overview(db, session.household_id)
    memory_bundle = build_memory_context_bundle(
        db,
        household_id=session.household_id,
        actor=actor,
        requester_member_id=session.requester_member_id,
        question=user_message,
        capability="conversation_free_chat",
    )
    identity = agent_context.get("identity", {}) if isinstance(agent_context, dict) else {}
    agent = agent_context.get("agent", {}) if isinstance(agent_context, dict) else {}
    memory_highlights = memory_bundle.hot_summary.preference_highlights[:3] or memory_bundle.hot_summary.recent_event_highlights[:3]
    memory_context_text = f"当前长期记忆摘要：{'；'.join(memory_highlights) if memory_highlights else '暂无明显长期记忆摘要。'}"
    if log_memory_context:
        _log_memory_context_usage(
            request_context=request_context,
            user_message=user_message,
            memory_bundle=memory_bundle,
            memory_highlights=memory_highlights,
            memory_context_text=memory_context_text,
        )
    return {
        "user_message": user_message,
        "agent_context": (
            f"当前角色：{agent.get('name') or 'AI 管家'}。\n"
            f"角色定位：{identity.get('role_summary') or '家庭 AI 管家'}。\n"
            f"说话风格：{identity.get('speaking_style') or '自然亲切'}。"
        ),
        "memory_context": memory_context_text,
        "household_context": (
            f"当前家庭概况：活跃成员 {overview.active_member.name if overview.active_member else '暂无'}；"
            f"家庭模式 {overview.home_mode}；"
            f"Home Assistant 状态 {overview.home_assistant_status}。"
        ),
    }


def _build_intent_detection_variables(
    *,
    session: ConversationSession,
    message: str,
    conversation_history: list[dict[str, str]],
) -> dict[str, str]:
    return {
        "session_mode": session.session_mode,
        "conversation_excerpt": _build_conversation_excerpt(conversation_history, message),
        "user_message": message,
    }


def _build_conversation_excerpt(
    conversation_history: list[dict[str, str]],
    latest_user_message: str,
) -> str:
    excerpt_lines: list[str] = []
    for item in conversation_history[-INTENT_HISTORY_LIMIT:]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if not role or not content:
            continue
        excerpt_lines.append(f"{_render_history_role(role)}：{content}")
    excerpt_lines.append(f"用户：{latest_user_message.strip()}")
    return "\n".join(excerpt_lines) if excerpt_lines else f"用户：{latest_user_message.strip()}"


def _render_history_role(role: str) -> str:
    if role == "assistant":
        return "助手"
    if role == "system":
        return "系统"
    return "用户"


def _build_member_context(db: Session, *, household_id: str) -> str:
    members, _ = member_service.list_members(db, household_id=household_id, page=1, page_size=100, status_value="active")
    if not members:
        return "当前家庭还没有有效成员。"
    return "\n".join(f"- {(member.nickname or member.name)}（{member.role}）" for member in members)


def _build_config_suggestion(parsed: object) -> dict:
    if parsed is None:
        return {
            "display_name": None,
            "speaking_style": None,
            "personality_traits": [],
        }
    return {
        "display_name": getattr(parsed, "display_name", None),
        "speaking_style": getattr(parsed, "speaking_style", None),
        "personality_traits": getattr(parsed, "personality_traits", []),
    }


def _normalize_config_suggestion(*, suggestion: dict, current_config: dict) -> dict:
    next_display_name = str(suggestion.get("display_name") or "").strip()
    current_display_name = str(current_config.get("display_name") or "").strip()
    if not next_display_name or next_display_name == current_display_name:
        next_display_name = None

    next_speaking_style = str(suggestion.get("speaking_style") or "").strip()
    current_speaking_style = str(current_config.get("speaking_style") or "").strip()
    if not next_speaking_style or next_speaking_style == current_speaking_style:
        next_speaking_style = None

    current_traits = {
        str(item).strip()
        for item in (current_config.get("personality_traits") or [])
        if str(item).strip()
    }
    next_traits = [
        str(item).strip()
        for item in (suggestion.get("personality_traits") or [])
        if str(item).strip()
    ]
    next_traits = [item for item in next_traits if item not in current_traits]

    return {
        "display_name": next_display_name,
        "speaking_style": next_speaking_style,
        "personality_traits": next_traits,
    }


def _retain_config_values_with_user_evidence(*, suggestion: dict, user_evidence: str) -> dict:
    normalized_evidence = user_evidence.strip().lower()

    next_display_name = str(suggestion.get("display_name") or "").strip()
    if next_display_name and next_display_name.lower() not in normalized_evidence:
        next_display_name = None

    next_speaking_style = str(suggestion.get("speaking_style") or "").strip()
    if next_speaking_style and next_speaking_style.lower() not in normalized_evidence:
        next_speaking_style = None

    next_traits = [
        str(item).strip()
        for item in (suggestion.get("personality_traits") or [])
        if str(item).strip() and str(item).strip().lower() in normalized_evidence
    ]

    return {
        "display_name": next_display_name,
        "speaking_style": next_speaking_style,
        "personality_traits": next_traits,
    }


def _render_config_draft(suggestion: dict) -> str:
    lines: list[str] = []
    display_name = str(suggestion.get("display_name") or "").strip()
    speaking_style = str(suggestion.get("speaking_style") or "").strip()
    personality_traits = suggestion.get("personality_traits") if isinstance(suggestion.get("personality_traits"), list) else []
    if display_name:
        lines.append(f"- 名字草稿：{display_name}")
    if speaking_style:
        lines.append(f"- 说话风格草稿：{speaking_style}")
    cleaned_traits = [str(item).strip() for item in personality_traits if str(item).strip()]
    if cleaned_traits:
        lines.append(f"- 性格标签草稿：{'、'.join(cleaned_traits)}")
    return "\n".join(lines) if lines else "当前还没有明确配置草稿。"


def _build_current_config_snapshot(
    db: Session,
    *,
    session: ConversationSession,
    actor: ActorContext,
    user_message: str,
) -> dict:
    variables = _build_free_chat_variables(db, session=session, actor=actor, user_message=user_message)
    agent_context = build_agent_runtime_context(
        db,
        household_id=session.household_id,
        agent_id=session.active_agent_id,
        requester_member_id=session.requester_member_id,
    )
    identity = agent_context.get("identity", {}) if isinstance(agent_context, dict) else {}
    agent = agent_context.get("agent", {}) if isinstance(agent_context, dict) else {}
    _ = variables
    return {
        "display_name": agent.get("name"),
        "speaking_style": identity.get("speaking_style"),
        "personality_traits": identity.get("personality_traits") if isinstance(identity.get("personality_traits"), list) else [],
    }


def _build_user_only_conversation_excerpt(
    conversation_history: list[dict[str, str]],
    latest_user_message: str,
) -> str:
    excerpt_lines: list[str] = []
    for item in conversation_history[-INTENT_HISTORY_LIMIT:]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role != "user" or not content:
            continue
        excerpt_lines.append(f"用户：{content}")
    excerpt_lines.append(f"用户：{latest_user_message.strip()}")
    return "\n".join(excerpt_lines)


def _build_config_dialogue_reply(*, message: str, suggestion: dict) -> str:
    display_name = str(suggestion.get("display_name") or "").strip()
    speaking_style = str(suggestion.get("speaking_style") or "").strip()
    personality_traits = [str(item).strip() for item in (suggestion.get("personality_traits") or []) if str(item).strip()]

    if display_name and speaking_style and personality_traits:
        return (
            f"好，那我以后就叫{display_name}。"
            f"说话风格我会调整成“{speaking_style}”，性格上更偏{'、'.join(personality_traits)}。"
            "你还想补充别的设定吗？"
        )
    if display_name and speaking_style:
        return f"好，那我以后就叫{display_name}。说话风格我会往“{speaking_style}”调整。你还想再补几个性格标签吗？"
    if display_name and personality_traits:
        return f"好，那我以后就叫{display_name}。性格上我会更偏{'、'.join(personality_traits)}。你还想顺手调整一下说话风格吗？"
    if display_name:
        return f"好，那我以后就叫{display_name}。你还想顺手调整一下我说话的风格，或者补几个性格标签吗？"
    if speaking_style and personality_traits:
        return f"可以，我会把说话风格调整成“{speaking_style}”，性格上更偏{'、'.join(personality_traits)}。你要不要也顺手给我换个名字？"
    if speaking_style:
        return f"可以，我会把说话风格往“{speaking_style}”调整。你要不要也顺手给我换个名字，或者补几个性格标签？"
    if personality_traits:
        return f"好，我会更偏{'、'.join(personality_traits)}这种感觉。你还想顺手改名字，或者调整一下说话风格吗？"

    lowered_message = message.strip().lower()
    if any(keyword in lowered_message for keyword in ("改名", "改个名", "名字", "起名", "叫你")):
        return "当然可以，你想给我起什么新名字？也可以顺手告诉我想换成什么说话风格。"
    if any(keyword in lowered_message for keyword in ("风格", "语气", "说话")):
        return "可以，你想让我说话更偏什么感觉？比如温柔一点、直接一点，还是更活泼一点？"
    if any(keyword in lowered_message for keyword in ("性格", "人设", "特点")):
        return "好，你希望我更偏什么性格？比如稳重一点、幽默一点，还是更贴心一点？"
    return "可以，我们慢慢来。你想先改名字、说话风格，还是性格感觉？"


def _normalize_intent_detection(
    parsed: ConversationIntentDetectionOutput,
) -> ConversationIntentDetection:
    primary_intent = _parse_intent_label(parsed.primary_intent)
    secondary_intents = _normalize_secondary_intents(primary_intent, parsed.secondary_intents)
    confidence = max(0.0, min(float(parsed.confidence), 1.0))
    reason = parsed.reason.strip() or "模型没有给出明确原因。"
    candidate_actions = list(parsed.candidate_actions)
    if primary_intent in {
        ConversationIntentLabel.CONFIG_CHANGE,
        ConversationIntentLabel.MEMORY_WRITE,
        ConversationIntentLabel.REMINDER_CREATE,
    } and not candidate_actions:
        candidate_actions = [
            ConversationIntentCandidateActionOutput(
                action_type=primary_intent.value,
                confidence=confidence,
                reason=reason,
            )
        ]

    route_intent = _map_intent_label_to_route(primary_intent)
    if primary_intent != ConversationIntentLabel.FREE_CHAT and confidence < INTENT_FALLBACK_THRESHOLD:
        route_intent = ConversationIntent.FREE_CHAT
        reason = f"{reason} 当前置信度只有 {confidence:.2f}，不够稳，先按 free_chat 回落。"

    return ConversationIntentDetection(
        primary_intent=primary_intent,
        secondary_intents=secondary_intents,
        confidence=confidence,
        reason=reason,
        candidate_actions=candidate_actions,
        route_intent=route_intent,
        guardrail_rule=None,
    )


def _parse_intent_label(raw_value: str) -> ConversationIntentLabel:
    try:
        return ConversationIntentLabel(raw_value)
    except ValueError:
        return ConversationIntentLabel.FREE_CHAT


def _normalize_secondary_intents(
    primary_intent: ConversationIntentLabel,
    items: list[str],
) -> list[ConversationIntentLabel]:
    normalized: list[ConversationIntentLabel] = []
    for item in items:
        intent = _parse_intent_label(item)
        if intent == primary_intent or intent in normalized:
            continue
        normalized.append(intent)
    return normalized


def _build_guardrail_intent_detection(
    *,
    primary_intent: ConversationIntentLabel,
    route_intent: ConversationIntent,
    reason: str,
    guardrail_rule: str,
) -> ConversationIntentDetection:
    candidate_actions: list[ConversationIntentCandidateActionOutput] = []
    if primary_intent in {
        ConversationIntentLabel.CONFIG_CHANGE,
        ConversationIntentLabel.MEMORY_WRITE,
        ConversationIntentLabel.REMINDER_CREATE,
    }:
        candidate_actions.append(
            ConversationIntentCandidateActionOutput(
                action_type=primary_intent.value,
                confidence=1.0,
                reason=reason,
            )
        )
    return ConversationIntentDetection(
        primary_intent=primary_intent,
        secondary_intents=[],
        confidence=1.0,
        reason=reason,
        candidate_actions=candidate_actions,
        route_intent=route_intent,
        guardrail_rule=guardrail_rule,
    )


def _build_fallback_intent_detection(reason: str) -> ConversationIntentDetection:
    return ConversationIntentDetection(
        primary_intent=ConversationIntentLabel.FREE_CHAT,
        secondary_intents=[],
        confidence=0.0,
        reason=reason,
        candidate_actions=[],
        route_intent=ConversationIntent.FREE_CHAT,
        guardrail_rule="fallback.free_chat",
    )


def _build_default_intent_detection(route_intent: ConversationIntent) -> ConversationIntentDetection:
    primary_intent = {
        ConversationIntent.FAST_ACTION: ConversationIntentLabel.FREE_CHAT,
        ConversationIntent.FREE_CHAT: ConversationIntentLabel.FREE_CHAT,
        ConversationIntent.STRUCTURED_QA: ConversationIntentLabel.STRUCTURED_QA,
        ConversationIntent.CONFIG_EXTRACTION: ConversationIntentLabel.CONFIG_CHANGE,
        ConversationIntent.MEMORY_EXTRACTION: ConversationIntentLabel.MEMORY_WRITE,
        ConversationIntent.REMINDER_EXTRACTION: ConversationIntentLabel.REMINDER_CREATE,
    }[route_intent]
    return ConversationIntentDetection(
        primary_intent=primary_intent,
        secondary_intents=[],
        confidence=1.0,
        reason="这是当前编排结果对应的默认意图映射。",
        candidate_actions=[],
        route_intent=route_intent,
        guardrail_rule="route.default_mapping",
    )


def _map_intent_label_to_route(intent: ConversationIntentLabel) -> ConversationIntent:
    mapping = {
        ConversationIntentLabel.FREE_CHAT: ConversationIntent.FREE_CHAT,
        ConversationIntentLabel.STRUCTURED_QA: ConversationIntent.STRUCTURED_QA,
        ConversationIntentLabel.CONFIG_CHANGE: ConversationIntent.CONFIG_EXTRACTION,
        ConversationIntentLabel.MEMORY_WRITE: ConversationIntent.MEMORY_EXTRACTION,
        ConversationIntentLabel.REMINDER_CREATE: ConversationIntent.REMINDER_EXTRACTION,
    }
    return mapping[intent]


def _log_intent_detection_result(
    *,
    request_context: dict | None,
    detection: ConversationIntentDetection,
) -> None:
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="intent_detection.completed",
        message="AI 意图识别完成。",
        payload=detection.to_payload(),
    )


def _log_route_selection(
    *,
    request_context: dict | None,
    detection: ConversationIntentDetection,
) -> None:
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="orchestrator.route.selected",
        message="编排层已选择主路由。",
        payload={
            "primary_intent": detection.primary_intent.value,
            "route_intent": detection.route_intent.value,
            "confidence": detection.confidence,
            "guardrail_rule": detection.guardrail_rule,
            "lane_selection": detection.lane_selection.to_payload() if detection.lane_selection is not None else None,
        },
    )


def _log_lane_shadow_result(
    *,
    request_context: dict | None,
    detection: ConversationIntentDetection,
    lane_selection: ConversationLaneSelection,
) -> None:
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="lane.shadow.evaluated",
        message="车道选择器已影子运行，但当前未接管主路由。",
        payload={
            "legacy_route_intent": detection.route_intent.value,
            "shadow_lane": lane_selection.lane.value,
            "shadow_confidence": lane_selection.confidence,
            "shadow_reason": lane_selection.reason,
            "shadow_target_kind": lane_selection.target_kind,
            "requires_clarification": lane_selection.requires_clarification,
        },
    )


def _log_memory_context_usage(
    *,
    request_context: dict | None,
    user_message: str,
    memory_bundle,
    memory_highlights: list[str],
    memory_context_text: str,
) -> None:
    top_memories = [
        {
            "memory_id": item.memory_id,
            "title": item.title,
            "memory_type": item.memory_type,
            "summary": item.summary,
            "updated_at": item.updated_at,
        }
        for item in memory_bundle.hot_summary.top_memories
    ]
    query_hits = [
        {
            "memory_id": hit.card.id,
            "title": hit.card.title,
            "memory_type": hit.card.memory_type,
            "score": hit.score,
            "matched_terms": hit.matched_terms,
            "summary": hit.card.summary,
        }
        for hit in memory_bundle.query_result.items
    ]
    highlight_source = "preference_highlights" if memory_bundle.hot_summary.preference_highlights[:3] else (
        "recent_event_highlights" if memory_bundle.hot_summary.recent_event_highlights[:3] else "none"
    )
    _log_orchestrator_debug_event(
        request_context=request_context,
        stage="memory_context.read",
        message="free_chat 已读取长期记忆上下文。",
        payload={
            "question": user_message,
            "capability": memory_bundle.capability,
            "total_visible_cards": memory_bundle.hot_summary.total_visible_cards,
            "top_memories": top_memories,
            "preference_highlights": memory_bundle.hot_summary.preference_highlights[:3],
            "recent_event_highlights": memory_bundle.hot_summary.recent_event_highlights[:3],
            "query_result_total": memory_bundle.query_result.total,
            "query_hits": query_hits,
            "injected_highlight_source": highlight_source,
            "injected_highlights": memory_highlights,
            "injected_memory_context": memory_context_text,
        },
    )


def _log_orchestrator_debug_event(
    *,
    request_context: dict | None,
    stage: str,
    message: str,
    payload: dict | None = None,
) -> None:
    context = request_context if isinstance(request_context, dict) else {}
    event_payload = {
        "session_id": str(context.get("session_id") or "-"),
        "request_id": str(context.get("request_id") or "-"),
        "stage": stage,
        "source": "orchestrator",
        "level": "info",
        "message": message,
        "payload": payload or {},
    }
    get_conversation_debug_logger().info(dump_conversation_debug_event(event_payload))
