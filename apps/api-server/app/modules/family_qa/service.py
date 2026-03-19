from dataclasses import dataclass
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.modules.ai_gateway import repository as ai_gateway_repository
from app.modules.ai_gateway.gateway_service import ainvoke_capability, build_invocation_plan, invoke_capability, prepare_payload_for_invocation
from app.modules.ai_gateway.provider_runtime import stream_provider_invoke
from app.modules.ai_gateway.provider_runtime import ProviderRuntimeError
from app.modules.agent.service import build_agent_runtime_context, resolve_effective_agent
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.conversation.device_context_summary import ConversationDeviceContextSummary
from app.modules.conversation.prompt_realtime_context_service import build_realtime_prompt_context
from app.modules.family_qa import repository
from app.modules.family_qa.fact_view_service import build_qa_fact_view
from app.modules.family_qa.models import QaQueryLog
from app.modules.family_qa.schemas import (
    FamilyQaQueryRequest,
    FamilyQaQueryResponse,
    FamilyQaSuggestionItem,
    FamilyQaSuggestionsResponse,
    QaFactMemberProfile,
    QaFactReference,
    QaFactViewRead,
    QaQueryLogCreate,
    QaQueryLogRead,
)
from app.modules.household.models import Household
from app.modules.member.models import Member
from app.modules.ai_gateway.schemas import AiGatewayInvokeRequest
from app.modules.memory.schemas import EventRecordCreate
from app.modules.memory.service import ingest_event_record_best_effort

logger = logging.getLogger(__name__)


@dataclass
class PreparedFamilyQaTurn:
    payload: FamilyQaQueryRequest
    effective_agent: object
    fact_view: QaFactViewRead
    answer_type: str
    answer_text: str
    confidence: float
    facts: list[QaFactReference]
    suggestions: list[str]
    agent_runtime_context: dict[str, object]
    conversation_history: list[dict[str, str]]
    device_context_summary: ConversationDeviceContextSummary
    realtime_context_text: str = ""


def create_query_log(db: Session, payload: QaQueryLogCreate) -> QaQueryLogRead:
    _ensure_household_exists(db, payload.household_id)
    _validate_requester_member(db, payload.household_id, payload.requester_member_id)

    row = QaQueryLog(
        id=new_uuid(),
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        question=payload.question,
        answer_type=payload.answer_type,
        answer_summary=payload.answer_summary,
        confidence=payload.confidence,
        degraded=payload.degraded,
        facts_json=dump_json([fact.model_dump(mode="json") for fact in payload.facts]) or "[]",
        created_at=utc_now_iso(),
    )
    repository.add_query_log(db, row)
    db.flush()
    return _to_query_log_read(row)


def list_query_logs(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    limit: int = 50,
) -> list[QaQueryLogRead]:
    _ensure_household_exists(db, household_id)
    _validate_requester_member(db, household_id, requester_member_id)
    rows = repository.list_query_logs(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        limit=limit,
    )
    return [_to_query_log_read(row) for row in rows]


def query_family_qa(db: Session, payload: FamilyQaQueryRequest, actor: ActorContext) -> FamilyQaQueryResponse:
    prepared = _prepare_family_qa_turn(db, payload, actor)
    ai_trace_id: str | None = None
    ai_provider_code: str | None = None
    ai_degraded = False
    degraded = False
    answer_text = prepared.answer_text

    try:
        ai_response = invoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="text",
                household_id=payload.household_id,
                requester_member_id=payload.requester_member_id,
                agent_id=prepared.effective_agent.id,
                payload=_build_qa_generation_payload(prepared),
            ),
        )
        answer_text = str(ai_response.normalized_output.get("text") or answer_text)
        ai_trace_id = ai_response.trace_id
        ai_provider_code = ai_response.provider_code
        ai_degraded = ai_response.degraded
        degraded = ai_response.degraded
    except HTTPException:
        degraded = True

    result = _build_family_qa_response(
        prepared,
        answer_text=answer_text,
        ai_trace_id=ai_trace_id,
        ai_provider_code=ai_provider_code,
        ai_degraded=ai_degraded,
        degraded=degraded,
    )
    _persist_family_qa_result(db, prepared=prepared, result=result)
    return result


async def aquery_family_qa(db: Session, payload: FamilyQaQueryRequest, actor: ActorContext) -> FamilyQaQueryResponse:
    prepared = _prepare_family_qa_turn(db, payload, actor)
    ai_trace_id: str | None = None
    ai_provider_code: str | None = None
    ai_degraded = False
    degraded = False
    answer_text = prepared.answer_text

    try:
        ai_response = await ainvoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="text",
                household_id=payload.household_id,
                requester_member_id=payload.requester_member_id,
                agent_id=prepared.effective_agent.id,
                payload=_build_qa_generation_payload(prepared),
            ),
        )
        answer_text = str(ai_response.normalized_output.get("text") or answer_text)
        ai_trace_id = ai_response.trace_id
        ai_provider_code = ai_response.provider_code
        ai_degraded = ai_response.degraded
        degraded = ai_response.degraded
    except HTTPException:
        degraded = True

    result = _build_family_qa_response(
        prepared,
        answer_text=answer_text,
        ai_trace_id=ai_trace_id,
        ai_provider_code=ai_provider_code,
        ai_degraded=ai_degraded,
        degraded=degraded,
    )
    _persist_family_qa_result(db, prepared=prepared, result=result)
    return result


async def stream_family_qa(
    db: Session,
    payload: FamilyQaQueryRequest,
    actor: ActorContext,
):
    prepared = _prepare_family_qa_turn(db, payload, actor)
    provider_code: str | None = None
    trace_id: str | None = None
    degraded = False
    chunks: list[str] = []

    plan = build_invocation_plan(
        db,
        capability="text",
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        agent_id=prepared.effective_agent.id,
        request_payload=_build_qa_generation_payload(prepared),
    )
    prepared_payload = prepare_payload_for_invocation(plan, _build_qa_generation_payload(prepared))

    provider_profile = None
    if plan.primary_provider is not None:
        provider_profile = ai_gateway_repository.get_provider_profile(db, plan.primary_provider.provider_profile_id)

    if provider_profile is None or not provider_profile.enabled or prepared_payload.blocked_reason:
        degraded = True
        response = await ainvoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="text",
                household_id=payload.household_id,
                requester_member_id=payload.requester_member_id,
                agent_id=prepared.effective_agent.id,
                payload=_build_qa_generation_payload(prepared),
            ),
        )
        text = str(response.normalized_output.get("text") or prepared.answer_text)
        if text:
            yield ("chunk", text)
        result = _build_family_qa_response(
            prepared,
            answer_text=text,
            ai_trace_id=response.trace_id,
            ai_provider_code=response.provider_code,
            ai_degraded=response.degraded,
            degraded=response.degraded or degraded,
        )
        _persist_family_qa_result(db, prepared=prepared, result=result)
        yield ("done", result)
        return

    provider_code = provider_profile.provider_code
    trace_id = plan.trace_id
    try:
        async for chunk in stream_provider_invoke(
            provider_profile=provider_profile,
            payload=prepared_payload.payload,
            timeout_ms=plan.timeout_ms,
        ):
            text = str(chunk or "")
            if not text:
                continue
            chunks.append(text)
            yield ("chunk", text)

        answer_text = "".join(chunks).strip() or prepared.answer_text
        result = _build_family_qa_response(
            prepared,
            answer_text=answer_text,
            ai_trace_id=trace_id,
            ai_provider_code=provider_code,
            ai_degraded=False,
            degraded=degraded,
        )
        _persist_family_qa_result(db, prepared=prepared, result=result)
        yield ("done", result)
        return
    except ProviderRuntimeError as exc:
        logger.warning(
            "Family QA 流式调用失败，切换到同步降级 capability=text trace_id=%s household_id=%s requester_member_id=%s session_id=%s provider=%s error_code=%s",
            trace_id,
            payload.household_id,
            payload.requester_member_id or "-",
            str((payload.context.get("request_context") or {}).get("session_id") or "-"),
            provider_code,
            exc.error_code,
        )
        response = await ainvoke_capability(
            db,
            AiGatewayInvokeRequest(
                capability="text",
                household_id=payload.household_id,
                requester_member_id=payload.requester_member_id,
                agent_id=prepared.effective_agent.id,
                payload=_build_qa_generation_payload(prepared),
            ),
        )
        logger.info(
            "Family QA 同步降级完成 capability=text trace_id=%s fallback_trace_id=%s household_id=%s requester_member_id=%s provider=%s degraded=%s attempts=%s",
            trace_id,
            response.trace_id,
            payload.household_id,
            payload.requester_member_id or "-",
            response.provider_code,
            response.degraded,
            _summarize_ai_gateway_attempts(response.attempts),
        )
        text = str(response.normalized_output.get("text") or prepared.answer_text)
        if text:
            yield ("chunk", text)
        result = _build_family_qa_response(
            prepared,
            answer_text=text,
            ai_trace_id=response.trace_id,
            ai_provider_code=response.provider_code,
            ai_degraded=response.degraded,
            degraded=response.degraded or degraded,
        )
        _persist_family_qa_result(db, prepared=prepared, result=result)
        yield ("done", result)


def _prepare_family_qa_turn(db: Session, payload: FamilyQaQueryRequest, actor: ActorContext) -> PreparedFamilyQaTurn:
    _ensure_household_exists(db, payload.household_id)
    _validate_requester_member(db, payload.household_id, payload.requester_member_id)
    effective_agent = resolve_effective_agent(
        db,
        household_id=payload.household_id,
        agent_id=payload.agent_id,
    )
    agent_runtime_context = build_agent_runtime_context(
        db,
        household_id=payload.household_id,
        agent_id=effective_agent.id,
        requester_member_id=payload.requester_member_id,
    )

    fact_view = build_qa_fact_view(
        db,
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        agent_id=effective_agent.id,
        actor=actor,
        question=payload.question,
    )
    device_context_summary = ConversationDeviceContextSummary.from_payload(
        payload.context.get("device_context_summary") if isinstance(payload.context, dict) else None
    )
    answer_type, answer_text, confidence, facts, suggestions = _answer_from_fact_view(
        fact_view,
        payload.question,
        device_context_summary=device_context_summary,
    )

    ai_trace_id: str | None = None
    ai_provider_code: str | None = None
    ai_degraded = False
    degraded = False
    conversation_history = _normalize_conversation_history(payload.context.get("conversation_history"))
    realtime_context_text = build_realtime_prompt_context(
        db,
        household_id=payload.household_id,
        generated_at=fact_view.generated_at,
    )
    _ = ai_trace_id, ai_provider_code, ai_degraded, degraded
    return PreparedFamilyQaTurn(
        payload=payload,
        effective_agent=effective_agent,
        fact_view=fact_view,
        answer_type=answer_type,
        answer_text=answer_text,
        confidence=confidence,
        facts=facts,
        suggestions=suggestions,
        agent_runtime_context=agent_runtime_context,
        conversation_history=conversation_history,
        device_context_summary=device_context_summary,
        realtime_context_text=realtime_context_text,
    )


def _summarize_ai_gateway_attempts(attempts: list[object]) -> str:
    if not attempts:
        return "-"
    fragments: list[str] = []
    for attempt in attempts:
        provider_code = str(getattr(attempt, "provider_code", "-"))
        status = str(getattr(attempt, "status", "-"))
        error_code = str(getattr(attempt, "error_code", "") or "ok")
        fragments.append(f"{provider_code}:{status}:{error_code}")
    return ",".join(fragments)


def list_family_qa_suggestions(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    agent_id: str | None = None,
    actor: ActorContext,
) -> FamilyQaSuggestionsResponse:
    _ensure_household_exists(db, household_id)
    _validate_requester_member(db, household_id, requester_member_id)
    effective_agent = resolve_effective_agent(
        db,
        household_id=household_id,
        agent_id=agent_id,
    )
    fact_view = build_qa_fact_view(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        agent_id=effective_agent.id,
        actor=actor,
        question=None,
    )
    items: list[FamilyQaSuggestionItem] = []
    if fact_view.active_member is not None:
        items.append(
            FamilyQaSuggestionItem(
                question=f"{fact_view.active_member.name} 现在在哪个房间？",
                answer_type="member_status",
                reason="当前有活跃成员，可直接问位置",
            )
        )
    if fact_view.reminder_summary.recent_items:
        first_item = fact_view.reminder_summary.recent_items[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_item.title} 处理完了吗？",
                answer_type="reminder_status",
                reason="最近有提醒记录",
            )
        )
    if fact_view.scene_summary.recent_items:
        first_scene = fact_view.scene_summary.recent_items[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_scene.name} 最近执行了吗？",
                answer_type="scene_status",
                reason="最近有场景模板记录",
            )
        )
    if fact_view.device_states:
        first_device = fact_view.device_states[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"{first_device.name} 现在是什么状态？",
                answer_type="device_status",
                reason="当前有可查询设备",
            )
        )
    if fact_view.memory_summary.items:
        first_memory = fact_view.memory_summary.items[0]
        items.append(
            FamilyQaSuggestionItem(
                question=f"记得 {first_memory.label} 吗？",
                answer_type="memory_recall",
                reason="长期记忆已经命中，可以直接问记忆类问题",
            )
        )
    elif fact_view.memory_summary.status == "hot_summary_only":
        items.append(
            FamilyQaSuggestionItem(
                question="最近家里记住了什么？",
                answer_type="memory_recall",
                reason="当前已有热记忆摘要",
            )
        )
    if not items:
        items.append(
            FamilyQaSuggestionItem(
                question="现在家里是什么状态？",
                answer_type="general",
                reason="默认建议问题",
            )
        )
    return FamilyQaSuggestionsResponse(
        household_id=household_id,
        effective_agent_id=effective_agent.id,
        effective_agent_type=effective_agent.agent_type,
        effective_agent_name=effective_agent.display_name,
        items=items[:6],
    )


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )


def _validate_requester_member(db: Session, household_id: str, requester_member_id: str | None) -> None:
    if requester_member_id is None:
        return

    member = db.get(Member, requester_member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member not found",
        )
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member must belong to the same household",
        )


def _to_query_log_read(row: QaQueryLog) -> QaQueryLogRead:
    return QaQueryLogRead(
        id=row.id,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        question=row.question,
        answer_type=row.answer_type,
        answer_summary=row.answer_summary,
        confidence=row.confidence,
        degraded=row.degraded,
        facts=load_json(row.facts_json) or [],
        created_at=row.created_at,
    )


def _answer_from_fact_view(
    fact_view: QaFactViewRead,
    question: str,
    *,
    device_context_summary: ConversationDeviceContextSummary | None = None,
) -> tuple[str, str, float, list[QaFactReference], list[str]]:
    normalized_question = question.strip().lower()

    member_profile_answer = _answer_from_member_profiles(
        fact_view,
        question=question,
        normalized_question=normalized_question,
    )
    if member_profile_answer is not None:
        return member_profile_answer

    if fact_view.memory_summary.items and _should_answer_from_memory(normalized_question):
        top_item = fact_view.memory_summary.items[0]
        memory_summary = str(top_item.extra.get("summary") or top_item.label)
        answer = f"根据当前家庭长期记忆，{memory_summary}。"
        facts = fact_view.memory_summary.items[:3]
        return "memory_recall", answer, 0.89, facts, ["查看记忆详情", "纠正这条记忆"]

    for member_state in fact_view.member_states:
        if (
            member_state.name
            and member_state.name.lower() in normalized_question
            and not _contains_any_keyword(normalized_question, ["喜欢", "偏好", "习惯", "记得", "以前", "关系", "记住", "回忆"])
        ):
            room_name = member_state.current_room_name or "未知房间"
            answer = f"{member_state.name} 当前状态是 {member_state.presence}，位置是 {room_name}。"
            facts = [
                QaFactReference(
                    type="member_state",
                    label=f"{member_state.name} 状态",
                    source="context_overview",
                    occurred_at=member_state.updated_at,
                    inferred=False,
                    extra={
                        "member_id": member_state.member_id,
                        "presence": member_state.presence,
                        "room_name": member_state.current_room_name,
                    },
                )
            ]
            return "member_status", answer, 0.93, facts, ["查看家庭上下文", "查看房间状态"]

    if _contains_any_keyword(normalized_question, ["提醒", "吃药", "服药", "课程", "安排"]):
        if fact_view.reminder_summary.recent_items:
            reminder = fact_view.reminder_summary.recent_items[0]
            answer = (
                f"{reminder.title} 最近一次状态是 {reminder.last_run_status or '未触发'}，"
                f"确认结果是 {reminder.last_ack_action or '还没人确认'}。"
            )
            facts = [
                QaFactReference(
                    type="reminder_run",
                    label=reminder.title,
                    source="reminder_runs",
                    occurred_at=reminder.last_run_planned_at,
                    inferred=False,
                    extra={
                        "task_id": reminder.task_id,
                        "last_run_status": reminder.last_run_status,
                        "last_ack_action": reminder.last_ack_action,
                    },
                )
            ]
            return "reminder_status", answer, 0.9, facts, ["查看提醒详情", "手动再次提醒"]
        return "reminder_status", "当前没有可用的提醒记录。", 0.45, [], ["创建提醒", "查看提醒总览"]

    if _contains_any_keyword(normalized_question, ["场景", "回家", "睡前", "模式"]):
        if fact_view.scene_summary.recent_items:
            scene = fact_view.scene_summary.recent_items[0]
            answer = f"{scene.name} 最近一次执行状态是 {scene.last_execution_status or '未执行'}。"
            facts = [
                QaFactReference(
                    type="scene_execution",
                    label=scene.name,
                    source="scene_executions",
                    occurred_at=scene.last_execution_started_at,
                    inferred=False,
                    extra={
                        "template_id": scene.template_id,
                        "template_code": scene.template_code,
                        "last_execution_status": scene.last_execution_status,
                    },
                )
            ]
            return "scene_status", answer, 0.88, facts, ["查看场景详情", "手动触发场景"]
        return "scene_status", "当前没有场景执行记录。", 0.4, [], ["查看场景模板"]

    contextual_device = _resolve_contextual_device_state(
        fact_view=fact_view,
        normalized_question=normalized_question,
        device_context_summary=device_context_summary,
    )
    if contextual_device is not None:
        answer = f"{contextual_device.name} 当前状态是 {contextual_device.status}。"
        facts = [
            QaFactReference(
                type="device_state",
                label=contextual_device.name,
                source="devices",
                inferred=False,
                extra={
                    "device_id": contextual_device.device_id,
                    "device_type": contextual_device.device_type,
                    "status": contextual_device.status,
                    "room_id": contextual_device.room_id,
                    "room_name": contextual_device.room_name,
                    "from_device_context_summary": True,
                },
            )
        ]
        return "device_status", answer, 0.9, facts, ["查看设备列表", "继续控制这个设备"]

    if _contains_any_keyword(normalized_question, ["灯", "空调", "窗帘", "门锁", "设备"]):
        if fact_view.device_states:
            device = fact_view.device_states[0]
            answer = f"{device.name} 当前状态是 {device.status}。"
            facts = [
                QaFactReference(
                    type="device_state",
                    label=device.name,
                    source="devices",
                    inferred=False,
                    extra={
                        "device_id": device.device_id,
                        "device_type": device.device_type,
                        "status": device.status,
                    },
                )
            ]
            return "device_status", answer, 0.86, facts, ["查看设备列表", "查看上下文总览"]
        return "device_status", "当前没有可查询的设备状态。", 0.35, [], ["同步设备数据"]

    summary_parts = []
    if fact_view.active_member is not None:
        summary_parts.append(f"当前活跃成员是 {fact_view.active_member.name}")
    if fact_view.memory_summary.status in {"available", "hot_summary_only"}:
        summary_parts.append(fact_view.memory_summary.summary)
    summary_parts.append(f"当前有 {fact_view.reminder_summary.pending_runs} 个待处理提醒")
    summary_parts.append(f"当前有 {fact_view.scene_summary.running_executions} 个场景正在运行")
    answer = "；".join(summary_parts) + "。"
    facts: list[QaFactReference] = []
    if fact_view.active_member is not None:
        facts.append(
            QaFactReference(
                type="active_member",
                label=fact_view.active_member.name,
                source="context_overview",
                inferred=False,
                extra={"member_id": fact_view.active_member.member_id},
            )
        )
    return "general", answer, 0.72, facts, ["谁在家", "最近提醒", "最近场景"]


def _answer_from_member_profiles(
    fact_view: QaFactViewRead,
    *,
    question: str,
    normalized_question: str,
) -> tuple[str, str, float, list[QaFactReference], list[str]] | None:
    if not fact_view.member_profiles:
        return None

    if _looks_like_member_age_question(normalized_question):
        age_answer = _answer_member_age_question(
            fact_view,
            question=question,
            normalized_question=normalized_question,
        )
        if age_answer is not None:
            return age_answer

    if _looks_like_member_relationship_question(normalized_question):
        relationship_answer = _answer_member_relationship_question(
            fact_view,
            question=question,
            normalized_question=normalized_question,
        )
        if relationship_answer is not None:
            return relationship_answer

    return None


def _answer_member_age_question(
    fact_view: QaFactViewRead,
    *,
    question: str,
    normalized_question: str,
) -> tuple[str, str, float, list[QaFactReference], list[str]] | None:
    profile = _select_primary_member_profile(
        fact_view,
        question=question,
        normalized_question=normalized_question,
    )
    if profile is None:
        return None
    if profile.age_years is None and not profile.age_group_label and not profile.birthday:
        return None

    detail_parts: list[str] = []
    if profile.age_years is not None:
        detail_parts.append(f"{profile.name}现在 {profile.age_years} 岁")
    elif profile.age_group_label:
        detail_parts.append(f"{profile.name}当前档案里的年龄段是{profile.age_group_label}")

    if profile.birthday:
        detail_parts.append(f"生日是 {profile.birthday}")
    elif profile.age_years is None and profile.age_group_label:
        detail_parts.append("档案里还没有精确生日")

    answer = "，".join(detail_parts) + "。"
    facts = [
        QaFactReference(
            type="member_profile",
            label=f"{profile.name} 的年龄资料",
            source="members",
            inferred=False,
            extra={
                "member_id": profile.member_id,
                "age_years": profile.age_years,
                "age_group": profile.age_group,
                "birthday": profile.birthday,
            },
        )
    ]
    return "member_profile", answer, 0.96, facts, ["查看家庭成员", "查看家庭关系"]


def _answer_member_relationship_question(
    fact_view: QaFactViewRead,
    *,
    question: str,
    normalized_question: str,
) -> tuple[str, str, float, list[QaFactReference], list[str]] | None:
    requester_profile = _find_member_profile_by_id(
        fact_view.member_profiles,
        fact_view.requester_member_id,
    )
    mentioned_profiles = _find_mentioned_member_profiles(
        fact_view.member_profiles,
        question=question,
        normalized_question=normalized_question,
    )

    if requester_profile is not None and ("和我" in normalized_question or "我和" in normalized_question):
        target_profiles = [
            profile for profile in mentioned_profiles if profile.member_id != requester_profile.member_id
        ]
        if len(target_profiles) == 1:
            target_profile = target_profiles[0]
            relation = _find_relationship(target_profile, requester_profile.member_id)
            if relation is not None:
                answer = f"按当前家庭关系，{target_profile.name}是你的{relation.relation_label}。"
                return _build_member_relationship_answer(
                    source_profile=target_profile,
                    target_profile=requester_profile,
                    answer=answer,
                    relation_type=relation.relation_type,
                    relation_label=relation.relation_label,
                )
            reverse_relation = _find_relationship(requester_profile, target_profile.member_id)
            if reverse_relation is not None:
                answer = f"按当前家庭关系，你是{target_profile.name}的{reverse_relation.relation_label}。"
                return _build_member_relationship_answer(
                    source_profile=requester_profile,
                    target_profile=target_profile,
                    answer=answer,
                    relation_type=reverse_relation.relation_type,
                    relation_label=reverse_relation.relation_label,
                )

    if len(mentioned_profiles) < 2:
        return None

    source_profile = mentioned_profiles[0]
    target_profile = mentioned_profiles[1]
    relation = _find_relationship(source_profile, target_profile.member_id)
    if relation is not None:
        answer = f"按当前家庭关系，{source_profile.name}是{target_profile.name}的{relation.relation_label}。"
        return _build_member_relationship_answer(
            source_profile=source_profile,
            target_profile=target_profile,
            answer=answer,
            relation_type=relation.relation_type,
            relation_label=relation.relation_label,
        )

    reverse_relation = _find_relationship(target_profile, source_profile.member_id)
    if reverse_relation is None:
        return None

    answer = f"按当前家庭关系，{target_profile.name}是{source_profile.name}的{reverse_relation.relation_label}。"
    return _build_member_relationship_answer(
        source_profile=target_profile,
        target_profile=source_profile,
        answer=answer,
        relation_type=reverse_relation.relation_type,
        relation_label=reverse_relation.relation_label,
    )


def _build_member_relationship_answer(
    *,
    source_profile: QaFactMemberProfile,
    target_profile: QaFactMemberProfile,
    answer: str,
    relation_type: str,
    relation_label: str,
) -> tuple[str, str, float, list[QaFactReference], list[str]]:
    facts = [
        QaFactReference(
            type="member_relationship",
            label=f"{source_profile.name} 与 {target_profile.name} 的关系",
            source="member_relationships",
            inferred=False,
            extra={
                "source_member_id": source_profile.member_id,
                "target_member_id": target_profile.member_id,
                "relation_type": relation_type,
                "relation_label": relation_label,
            },
        )
    ]
    return "member_relationship", answer, 0.97, facts, ["查看家庭关系", "查看成员资料"]


def _find_mentioned_member_profiles(
    profiles: list[QaFactMemberProfile],
    *,
    question: str,
    normalized_question: str,
) -> list[QaFactMemberProfile]:
    matches: list[tuple[int, int, QaFactMemberProfile]] = []
    seen_member_ids: set[str] = set()
    for profile in profiles:
        match_index: int | None = None
        alias_length = 0
        for alias in profile.aliases:
            normalized_alias = str(alias or "").strip().lower()
            if not normalized_alias:
                continue
            current_index = normalized_question.find(normalized_alias)
            if current_index < 0:
                continue
            if match_index is None or current_index < match_index or (
                current_index == match_index and len(normalized_alias) > alias_length
            ):
                match_index = current_index
                alias_length = len(normalized_alias)
        if match_index is None or profile.member_id in seen_member_ids:
            continue
        matches.append((match_index, -alias_length, profile))
        seen_member_ids.add(profile.member_id)

    matches.sort(key=lambda item: (item[0], item[1], item[2].name))
    return [item[2] for item in matches]


def _select_primary_member_profile(
    fact_view: QaFactViewRead,
    *,
    question: str,
    normalized_question: str,
) -> QaFactMemberProfile | None:
    mentioned_profiles = _find_mentioned_member_profiles(
        fact_view.member_profiles,
        question=question,
        normalized_question=normalized_question,
    )
    if mentioned_profiles:
        return mentioned_profiles[0]
    return _find_member_profile_by_id(
        fact_view.member_profiles,
        fact_view.requester_member_id if "我" in question else None,
    )


def _find_member_profile_by_id(
    profiles: list[QaFactMemberProfile],
    member_id: str | None,
) -> QaFactMemberProfile | None:
    if not member_id:
        return None
    for profile in profiles:
        if profile.member_id == member_id:
            return profile
    return None


def _find_relationship(profile: QaFactMemberProfile, target_member_id: str) -> object | None:
    for relationship in profile.relationships:
        if relationship.target_member_id == target_member_id:
            return relationship
    if profile.guardian_member_id == target_member_id:
        return type(
            "GuardianRelationship",
            (),
            {"relation_type": "guardian", "relation_label": "被监护人"},
        )()
    return None


def _contains_any_keyword(question: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        if keyword in question:
            return True
    return False


def _looks_like_member_age_question(question: str) -> bool:
    return _contains_any_keyword(question, ["多大", "几岁", "年龄", "生日"])


def _looks_like_member_relationship_question(question: str) -> bool:
    return _contains_any_keyword(question, ["关系", "什么关系", "监护人", "家人"])


def _should_answer_from_memory(question: str) -> bool:
    return _contains_any_keyword(
        question,
        ["喜欢", "偏好", "习惯", "记得", "记住", "回忆", "上次", "以前", "关系", "不吃", "联系方式", "生日", "温度"],
    )


def _normalize_conversation_history(raw_value: object) -> list[dict[str, str]]:
    if not isinstance(raw_value, list):
        return []

    messages: list[dict[str, str]] = []
    for item in raw_value[:12]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant", "system"}:
            continue
        if not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _build_qa_generation_payload(prepared: PreparedFamilyQaTurn) -> dict[str, object]:
    return {
        "question": prepared.payload.question,
        "answer_draft": prepared.answer_text,
        "answer_type": prepared.answer_type,
        "fact_count": len(prepared.facts),
        "channel": prepared.payload.channel,
        "conversation_history": prepared.conversation_history,
        "device_context_summary": prepared.device_context_summary.to_payload(),
        "device_context_summary_text": prepared.device_context_summary.to_prompt_text(),
        "realtime_context_text": prepared.realtime_context_text,
        "request_context": prepared.payload.context.get("request_context") if isinstance(prepared.payload.context, dict) else {},
        "agent_runtime_context": prepared.agent_runtime_context,
        "agent_memory_context": {
            "status": prepared.fact_view.memory_summary.status,
            "summary": prepared.fact_view.memory_summary.summary,
            "items": [
                {
                    "label": item.label,
                    "summary": str(item.extra.get("summary") or ""),
                    "memory_type": str(item.extra.get("memory_type") or ""),
                }
                for item in prepared.fact_view.memory_summary.items[:5]
            ],
        },
    }


def _resolve_contextual_device_state(
    *,
    fact_view: QaFactViewRead,
    normalized_question: str,
    device_context_summary: ConversationDeviceContextSummary | None,
):
    if device_context_summary is None or not device_context_summary.can_resume_control:
        return None
    if _is_device_inventory_question(normalized_question):
        return None

    target = (
        device_context_summary.resume_target
        or device_context_summary.latest_query_target
        or device_context_summary.latest_execution_target
        or device_context_summary.latest_target
    )
    if target is None:
        return None
    if not _looks_like_contextual_device_question(normalized_question):
        return None
    if any(str(item.name or "").strip().lower() in normalized_question for item in fact_view.device_states if item.name):
        return None

    for device in fact_view.device_states:
        if device.device_id == target.device_id:
            return device
    return None


def _looks_like_contextual_device_question(question: str) -> bool:
    return _contains_any_keyword(
        question,
        [
            "它",
            "这个",
            "那个",
            "刚才",
            "刚刚",
            "上一个",
            "上次",
            "状态",
            "怎么样",
            "咋样",
            "还开着",
            "还亮着",
            "还关着",
            "开着吗",
            "亮着吗",
            "关了吗",
            "灭了吗",
            "还在吗",
        ],
    )


def _is_device_inventory_question(question: str) -> bool:
    return _contains_any_keyword(
        question,
        [
            "什么设备",
            "哪些设备",
            "都有设备",
            "设备列表",
            "家里设备",
            "设备总览",
            "设备清单",
        ],
    )


def _build_family_qa_response(
    prepared: PreparedFamilyQaTurn,
    *,
    answer_text: str,
    ai_trace_id: str | None,
    ai_provider_code: str | None,
    ai_degraded: bool,
    degraded: bool,
) -> FamilyQaQueryResponse:
    effective_agent = prepared.effective_agent
    return FamilyQaQueryResponse(
        answer_type=prepared.answer_type,
        answer=answer_text,
        confidence=prepared.confidence,
        facts=prepared.facts,
        degraded=degraded,
        suggestions=prepared.suggestions,
        effective_agent_id=effective_agent.id,
        effective_agent_type=effective_agent.agent_type,
        effective_agent_name=effective_agent.display_name,
        ai_trace_id=ai_trace_id,
        ai_provider_code=ai_provider_code,
        ai_degraded=ai_degraded,
    )


def _persist_family_qa_result(
    db: Session,
    *,
    prepared: PreparedFamilyQaTurn,
    result: FamilyQaQueryResponse,
) -> None:
    query_log = create_query_log(
        db,
        QaQueryLogCreate(
            household_id=prepared.payload.household_id,
            requester_member_id=prepared.payload.requester_member_id,
            question=prepared.payload.question,
            answer_type=result.answer_type,
            answer_summary=result.answer[:2000],
            confidence=result.confidence,
            degraded=result.degraded,
            facts=result.facts,
        ),
    )
    ingest_event_record_best_effort(
        db,
        EventRecordCreate(
            household_id=prepared.payload.household_id,
            event_type="family_event_occurred",
            source_type="family_qa",
            source_ref=query_log.id,
            subject_member_id=prepared.payload.requester_member_id,
            room_id=None,
            payload={
                "event_category": "agent_qa_interaction",
                "agent_id": prepared.effective_agent.id,
                "agent_type": prepared.effective_agent.agent_type,
                "agent_name": prepared.effective_agent.display_name,
                "question": prepared.payload.question,
                "answer_type": result.answer_type,
                "answer_summary": result.answer[:500],
                "ai_degraded": result.ai_degraded,
                "memory_summary": prepared.fact_view.memory_summary.summary,
                "memory_status": prepared.fact_view.memory_summary.status,
                "memory_item_count": len(prepared.fact_view.memory_summary.items),
            },
            dedupe_key=f"family_qa:{query_log.id}",
            generate_memory_card=False,
            occurred_at=query_log.created_at,
        ),
    )
