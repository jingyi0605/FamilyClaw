from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.modules.agent.service import build_agent_runtime_context
from app.modules.context.service import get_context_overview
from app.modules.conversation.models import ConversationSession
from app.modules.family_qa.schemas import FamilyQaQueryRequest, FamilyQaQueryResponse
from app.modules.family_qa.service import query_family_qa, stream_family_qa
from app.modules.llm_task import invoke_llm, stream_llm
from app.modules.memory.context_engine import build_memory_context_bundle


class ConversationIntent(StrEnum):
    STRUCTURED_QA = "structured_qa"
    FREE_CHAT = "free_chat"
    CONFIG_EXTRACTION = "config_extraction"
    MEMORY_EXTRACTION = "memory_extraction"


@dataclass
class ConversationOrchestratorResult:
    intent: ConversationIntent
    text: str
    degraded: bool
    facts: list[dict]
    suggestions: list[str]
    memory_candidate_payloads: list[dict]
    config_suggestion: dict | None
    ai_trace_id: str | None
    ai_provider_code: str | None
    effective_agent_id: str | None
    effective_agent_name: str | None


def detect_conversation_intent(
    *,
    session: ConversationSession,
    message: str,
) -> ConversationIntent:
    normalized = message.strip().lower()
    if session.session_mode == "agent_config":
        return ConversationIntent.CONFIG_EXTRACTION
    if _looks_like_config_intent(normalized):
        return ConversationIntent.CONFIG_EXTRACTION
    if _looks_like_memory_intent(normalized):
        return ConversationIntent.MEMORY_EXTRACTION
    if _looks_like_structured_qa(normalized):
        return ConversationIntent.STRUCTURED_QA
    return ConversationIntent.FREE_CHAT


def run_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
) -> ConversationOrchestratorResult:
    intent = detect_conversation_intent(session=session, message=message)
    if intent == ConversationIntent.STRUCTURED_QA:
        result = _run_structured_qa(db, session=session, message=message, actor=actor, conversation_history=conversation_history)
        return _from_family_qa_result(intent, result)
    if intent == ConversationIntent.CONFIG_EXTRACTION:
        return _run_config_extraction(db, session=session, message=message, actor=actor, conversation_history=conversation_history)
    if intent == ConversationIntent.MEMORY_EXTRACTION:
        return _run_memory_extraction(db, session=session, message=message, actor=actor, conversation_history=conversation_history)
    return _run_non_qa_chat(db, intent=intent, session=session, message=message, actor=actor, conversation_history=conversation_history)


def stream_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
):
    intent = detect_conversation_intent(session=session, message=message)
    if intent == ConversationIntent.STRUCTURED_QA:
        for event_type, event_payload in stream_family_qa(
            db,
            FamilyQaQueryRequest(
                household_id=session.household_id,
                requester_member_id=session.requester_member_id,
                agent_id=session.active_agent_id,
                question=message,
                channel="conversation_turn",
                context={"conversation_history": conversation_history},
            ),
            actor,
        ):
            if event_type == "done":
                yield event_type, _from_family_qa_result(intent, event_payload)
            else:
                yield event_type, event_payload
        return

    if intent == ConversationIntent.CONFIG_EXTRACTION:
        result = _run_config_extraction(db, session=session, message=message, actor=actor, conversation_history=conversation_history)
        if result.text:
            yield "chunk", result.text
        yield "done", result
        return

    if intent == ConversationIntent.MEMORY_EXTRACTION:
        result = _run_memory_extraction(db, session=session, message=message, actor=actor, conversation_history=conversation_history)
        if result.text:
            yield "chunk", result.text
        yield "done", result
        return

    full_text = ""
    for event in stream_llm(
        db,
        task_type="free_chat",
        variables=_build_free_chat_variables(db, session=session, actor=actor, user_message=message),
        household_id=session.household_id,
        conversation_history=conversation_history,
    ):
        if event.event_type == "chunk":
            full_text += event.content
            yield "chunk", event.content
            continue
        if event.event_type == "done" and event.result is not None:
            text = event.result.text or full_text
            yield "done", ConversationOrchestratorResult(
                intent=intent,
                text=text,
                degraded=False,
                facts=[],
                suggestions=[],
                memory_candidate_payloads=[],
                config_suggestion=None,
                ai_trace_id=None,
                ai_provider_code=event.result.provider or None,
                effective_agent_id=session.active_agent_id,
                effective_agent_name=None,
            )


def _run_structured_qa(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
) -> FamilyQaQueryResponse:
    return query_family_qa(
        db,
        FamilyQaQueryRequest(
            household_id=session.household_id,
            requester_member_id=session.requester_member_id,
            agent_id=session.active_agent_id,
            question=message,
            channel="conversation_turn",
            context={"conversation_history": conversation_history},
        ),
        actor,
    )


def _run_non_qa_chat(
    db: Session,
    *,
    intent: ConversationIntent,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
) -> ConversationOrchestratorResult:
    result = invoke_llm(
        db,
        task_type="free_chat",
        variables=_build_free_chat_variables(db, session=session, actor=actor, user_message=message),
        household_id=session.household_id,
        conversation_history=conversation_history,
    )
    return ConversationOrchestratorResult(
        intent=intent,
        text=result.text,
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[],
        config_suggestion=None,
        ai_trace_id=None,
        ai_provider_code=result.provider or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
    )


def _run_config_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
) -> ConversationOrchestratorResult:
    _ = conversation_history
    variables = _build_free_chat_variables(db, session=session, actor=actor, user_message=message)
    result = invoke_llm(
        db,
        task_type="config_extraction",
        variables={
            "agent_context": variables["agent_context"],
            "user_message": message,
        },
        household_id=session.household_id,
    )
    parsed = result.data
    if parsed is None:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.CONFIG_EXTRACTION,
            text="我还没有从这轮表达里整理出明确的 Agent 配置建议。你可以更具体地告诉我想改名字、说话风格或性格标签。",
            degraded=False,
            facts=[],
            suggestions=["修改名字", "调整说话风格", "补充性格标签"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            ai_trace_id=None,
            ai_provider_code=result.provider or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
        )

    suggestion = {
        "display_name": getattr(parsed, "display_name", None),
        "speaking_style": getattr(parsed, "speaking_style", None),
        "personality_traits": getattr(parsed, "personality_traits", []),
    }
    lines = ["我已经把这轮表达整理成 Agent 配置建议："]
    if suggestion["display_name"]:
        lines.append(f"- 名称建议：{suggestion['display_name']}")
    if suggestion["speaking_style"]:
        lines.append(f"- 说话风格：{suggestion['speaking_style']}")
    if suggestion["personality_traits"]:
        lines.append(f"- 性格标签：{'、'.join(suggestion['personality_traits'])}")
    if len(lines) == 1:
        lines.append("- 当前没有足够明确的配置项")
    lines.append("如果你认可，我后续可以继续把它整理成正式配置建议。")
    return ConversationOrchestratorResult(
        intent=ConversationIntent.CONFIG_EXTRACTION,
        text="\n".join(lines),
        degraded=False,
        facts=[{"type": "config_suggestion", "label": "Agent 配置建议", "source": "conversation_orchestrator", "extra": suggestion}],
        suggestions=["去 AI 配置", "继续补充配置要求"],
        memory_candidate_payloads=[],
        config_suggestion=suggestion,
        ai_trace_id=None,
        ai_provider_code=result.provider or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
    )


def _run_memory_extraction(
    db: Session,
    *,
    session: ConversationSession,
    message: str,
    actor: ActorContext,
    conversation_history: list[dict[str, str]],
) -> ConversationOrchestratorResult:
    conversation = "\n".join([*(f"{item['role']}：{item['content']}" for item in conversation_history[-4:]), f"用户：{message}"])
    result = invoke_llm(
        db,
        task_type="memory_extraction",
        variables={
            "conversation": conversation,
            "member_context": _build_member_context(db, household_id=session.household_id),
        },
        household_id=session.household_id,
        conversation_history=conversation_history,
    )
    parsed = result.data
    if parsed is None or not parsed.memories:
        return ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="我暂时没有从这轮内容里提取到值得长期保存的记忆。",
            degraded=False,
            facts=[],
            suggestions=["换一种说法", "明确告诉我要记住什么"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            ai_trace_id=None,
            ai_provider_code=result.provider or None,
            effective_agent_id=session.active_agent_id,
            effective_agent_name=None,
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
        text="我已经从这轮内容里整理出记忆候选，右侧可以直接确认写入。",
        degraded=False,
        facts=[],
        suggestions=["确认写入记忆", "忽略这次提取"],
        memory_candidate_payloads=candidates,
        config_suggestion=None,
        ai_trace_id=None,
        ai_provider_code=result.provider or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
    )


def _from_family_qa_result(intent: ConversationIntent, result: FamilyQaQueryResponse) -> ConversationOrchestratorResult:
    return ConversationOrchestratorResult(
        intent=intent,
        text=result.answer,
        degraded=result.degraded or result.ai_degraded,
        facts=[item.model_dump(mode="json") for item in result.facts],
        suggestions=result.suggestions,
        memory_candidate_payloads=[],
        config_suggestion=None,
        ai_trace_id=result.ai_trace_id,
        ai_provider_code=result.ai_provider_code,
        effective_agent_id=result.effective_agent_id,
        effective_agent_name=result.effective_agent_name,
    )


def _build_free_chat_variables(
    db: Session,
    *,
    session: ConversationSession,
    actor: ActorContext,
    user_message: str,
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
    return {
        "user_message": user_message,
        "agent_context": (
            f"当前角色：{agent.get('name') or 'AI 管家'}。\n"
            f"角色定位：{identity.get('role_summary') or '家庭 AI 管家'}。\n"
            f"说话风格：{identity.get('speaking_style') or '自然亲切'}。"
        ),
        "memory_context": f"当前长期记忆摘要：{'；'.join(memory_highlights) if memory_highlights else '暂无明显长期记忆摘要。'}",
        "household_context": (
            f"当前家庭概况：活跃成员 {overview.active_member.name if overview.active_member else '暂无'}；"
            f"家庭模式 {overview.home_mode}；"
            f"Home Assistant 状态 {overview.home_assistant_status}。"
        ),
    }


def _looks_like_memory_intent(message: str) -> bool:
    keywords = ["记住", "记下来", "记一下", "写入记忆", "帮我记住"]
    return any(keyword in message for keyword in keywords)


def _looks_like_config_intent(message: str) -> bool:
    keywords = ["改名字", "换名字", "你叫", "你应该叫", "说话风格", "性格", "人格", "人设", "以后你就叫"]
    return any(keyword in message for keyword in keywords)


def _looks_like_structured_qa(message: str) -> bool:
    keywords = [
        "谁在家", "现在家里", "家庭状态", "设备", "空调", "灯", "窗帘", "门锁",
        "提醒", "场景", "最近提醒", "最近场景", "在哪个房间", "状态", "在家吗",
    ]
    if any(keyword in message for keyword in keywords):
        return True
    if message.endswith("吗") and ("家" in message or "提醒" in message or "设备" in message):
        return True
    return False
