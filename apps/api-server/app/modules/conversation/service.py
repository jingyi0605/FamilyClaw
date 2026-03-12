from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository as agent_repository
from app.modules.agent.service import AgentNotFoundError, resolve_effective_agent
from app.modules.audit.service import write_audit_log
from app.modules.conversation import repository
from app.modules.conversation.models import (
    ConversationMemoryCandidate,
    ConversationMessage,
    ConversationSession,
)
from app.modules.conversation.schemas import (
    ConversationMemoryCandidateActionRead,
    ConversationMemoryCandidateRead,
    ConversationMessageRead,
    ConversationSessionCreate,
    ConversationSessionDetailRead,
    ConversationSessionListResponse,
    ConversationSessionRead,
    ConversationTurnCreate,
    ConversationTurnRead,
)
from app.modules.family_qa.schemas import FamilyQaQueryRequest, FamilyQaQueryResponse
from app.modules.family_qa.service import query_family_qa
from app.modules.household.models import Household
from app.modules.llm_task import invoke_llm
from app.modules.llm_task.output_models import MemoryExtractionOutput
from app.modules.memory.schemas import MemoryCardManualCreate
from app.modules.memory.service import create_manual_memory_card
from app.modules.member import service as member_service
from app.modules.realtime.connection_manager import RealtimeConnectionManager
from app.modules.realtime.schemas import build_bootstrap_realtime_event


class ConversationNotFoundError(LookupError):
    pass


def create_conversation_session(
    db: Session,
    *,
    payload: ConversationSessionCreate,
    actor: ActorContext,
) -> ConversationSessionDetailRead:
    requester_member_id = _normalize_requester_member_id(payload.requester_member_id, actor)
    _ensure_household_exists(db, payload.household_id)
    try:
        effective_agent = resolve_effective_agent(
            db,
            household_id=payload.household_id,
            agent_id=payload.active_agent_id,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no available agent for current household conversation",
        ) from exc
    now = utc_now_iso()
    row = ConversationSession(
        id=new_uuid(),
        household_id=payload.household_id,
        requester_member_id=requester_member_id,
        session_mode=payload.session_mode,
        active_agent_id=effective_agent.id if effective_agent is not None else None,
        title=(payload.title or "新对话").strip(),
        status="active",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    repository.add_session(db, row)
    db.flush()
    return _to_session_detail_read(db, row)


def list_conversation_sessions(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None,
    actor: ActorContext,
    limit: int = 50,
) -> ConversationSessionListResponse:
    normalized_requester_member_id = _normalize_requester_member_id(requester_member_id, actor)
    _ensure_household_exists(db, household_id)
    rows = repository.list_sessions(
        db,
        household_id=household_id,
        requester_member_id=normalized_requester_member_id,
        limit=limit,
    )
    return ConversationSessionListResponse(
        household_id=household_id,
        requester_member_id=normalized_requester_member_id,
        items=[_to_session_read(db, row) for row in rows],
    )


def get_conversation_session_detail(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
) -> ConversationSessionDetailRead:
    row = repository.get_session(db, session_id)
    if row is None:
        raise ConversationNotFoundError(session_id)
    _ensure_actor_can_read_session(row, actor)
    return _to_session_detail_read(db, row)


def get_conversation_session_snapshot(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
) -> ConversationSessionDetailRead:
    return get_conversation_session_detail(db, session_id=session_id, actor=actor)


def create_conversation_turn(
    db: Session,
    *,
    session_id: str,
    payload: ConversationTurnCreate,
    actor: ActorContext,
) -> ConversationTurnRead:
    session = _get_visible_session(db, session_id=session_id, actor=actor)
    request_id, user_message, assistant_message = _create_pending_turn(
        db,
        session=session,
        payload=payload,
    )

    outcome = "completed"
    error_message: str | None = None

    try:
        result = _run_family_qa_turn(
            db,
            session=session,
            question=payload.message.strip(),
            request_id=request_id,
            actor=actor,
        )
        _complete_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message,
            result=result,
        )
        _generate_memory_candidates_for_turn(
            db,
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
        )
    except Exception as exc:
        outcome = "failed"
        error_message = _render_turn_error(exc)
        _fail_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message,
            error_message=error_message,
            error_code=_resolve_turn_error_code(exc),
        )

    db.flush()
    return ConversationTurnRead(
        request_id=request_id,
        session_id=session.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        outcome=outcome,
        error_message=error_message,
        session=_to_session_detail_read(db, session),
    )


def confirm_memory_candidate(
    db: Session,
    *,
    candidate_id: str,
    actor: ActorContext,
) -> ConversationMemoryCandidateActionRead:
    candidate = repository.get_memory_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation memory candidate not found")
    session = _get_visible_session(db, session_id=candidate.session_id, actor=actor)
    if candidate.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation memory candidate already resolved")

    memory_card = create_manual_memory_card(
        db,
        payload=MemoryCardManualCreate(
            household_id=session.household_id,
            memory_type=_normalize_memory_type(candidate.memory_type),
            title=candidate.title,
            summary=candidate.summary,
            content=load_json(candidate.content_json) or {},
            status="active",
            visibility="family",
            importance=3,
            confidence=candidate.confidence,
            subject_member_id=candidate.requester_member_id,
            source_event_id=None,
            dedupe_key=f"conversation_candidate:{candidate.id}",
            effective_at=None,
            last_observed_at=None,
            related_members=[],
            reason="confirmed from conversation candidate",
        ),
        actor=actor,
    )
    candidate.status = "confirmed"
    candidate.updated_at = utc_now_iso()
    db.flush()
    return ConversationMemoryCandidateActionRead(
        candidate=_to_candidate_read(candidate),
        memory_card_id=memory_card.id,
    )


def dismiss_memory_candidate(
    db: Session,
    *,
    candidate_id: str,
    actor: ActorContext,
) -> ConversationMemoryCandidateActionRead:
    candidate = repository.get_memory_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation memory candidate not found")
    _get_visible_session(db, session_id=candidate.session_id, actor=actor)
    if candidate.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation memory candidate already resolved")
    candidate.status = "dismissed"
    candidate.updated_at = utc_now_iso()
    db.flush()
    return ConversationMemoryCandidateActionRead(
        candidate=_to_candidate_read(candidate),
        memory_card_id=None,
    )


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="household not found")


def _normalize_requester_member_id(requester_member_id: str | None, actor: ActorContext) -> str | None:
    if actor.account_type == "system":
        return requester_member_id
    if actor.member_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor required")
    if requester_member_id is not None and requester_member_id != actor.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member actor cannot create or query conversation for another member",
        )
    return actor.member_id


def _ensure_actor_can_read_session(row: ConversationSession, actor: ActorContext) -> None:
    if actor.account_type == "system":
        return
    if actor.household_id != row.household_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot access another household conversation")
    if actor.member_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor required")
    if row.requester_member_id is not None and row.requester_member_id != actor.member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="conversation is not visible to current member")


def _get_visible_session(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
) -> ConversationSession:
    row = repository.get_session(db, session_id)
    if row is None:
        raise ConversationNotFoundError(session_id)
    _ensure_actor_can_read_session(row, actor)
    return row


def _create_pending_turn(
    db: Session,
    *,
    session: ConversationSession,
    payload: ConversationTurnCreate,
    request_id: str | None = None,
) -> tuple[str, ConversationMessage, ConversationMessage]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message 不能为空")

    effective_agent = _resolve_turn_agent(db, session=session, requested_agent_id=payload.agent_id)
    request_id = request_id or new_uuid()
    now = utc_now_iso()

    existing_messages = list(repository.list_messages(db, session_id=session.id))
    if not existing_messages and session.title == "新对话":
        session.title = _build_session_title(message)

    session.active_agent_id = effective_agent.id
    session.last_message_at = now
    session.updated_at = now

    user_message = ConversationMessage(
        id=new_uuid(),
        session_id=session.id,
        request_id=request_id,
        seq=repository.get_next_message_seq(db, session_id=session.id),
        role="user",
        message_type="text",
        content=message,
        status="completed",
        effective_agent_id=effective_agent.id,
        ai_provider_code=None,
        ai_trace_id=None,
        degraded=False,
        error_code=None,
        facts_json=dump_json([]),
        suggestions_json=dump_json([]),
        created_at=now,
        updated_at=now,
    )
    repository.add_message(db, user_message)

    assistant_message = ConversationMessage(
        id=new_uuid(),
        session_id=session.id,
        request_id=request_id,
        seq=repository.get_next_message_seq(db, session_id=session.id),
        role="assistant",
        message_type="text",
        content="",
        status="pending",
        effective_agent_id=effective_agent.id,
        ai_provider_code=None,
        ai_trace_id=None,
        degraded=False,
        error_code=None,
        facts_json=dump_json([]),
        suggestions_json=dump_json([]),
        created_at=now,
        updated_at=now,
    )
    repository.add_message(db, assistant_message)
    db.flush()
    return request_id, user_message, assistant_message


def _resolve_turn_agent(
    db: Session,
    *,
    session: ConversationSession,
    requested_agent_id: str | None,
):
    existing_messages = list(repository.list_messages(db, session_id=session.id))
    target_agent_id = requested_agent_id or session.active_agent_id
    if requested_agent_id and session.active_agent_id and requested_agent_id != session.active_agent_id and existing_messages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot switch agent inside a non-empty conversation session",
        )
    try:
        return resolve_effective_agent(
            db,
            household_id=session.household_id,
            agent_id=target_agent_id,
        )
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no available agent for current household conversation",
        ) from exc


def _run_family_qa_turn(
    db: Session,
    *,
    session: ConversationSession,
    question: str,
    request_id: str,
    actor: ActorContext,
) -> FamilyQaQueryResponse:
    _ = request_id
    return query_family_qa(
        db,
        FamilyQaQueryRequest(
            household_id=session.household_id,
            requester_member_id=session.requester_member_id,
            agent_id=session.active_agent_id,
            question=question,
            channel="conversation_turn",
            context={
                "conversation_history": _build_recent_conversation_history(
                    db,
                    session_id=session.id,
                    current_request_id=request_id,
                ),
            },
        ),
        actor,
    )


def _complete_assistant_message(
    db: Session,
    *,
    session: ConversationSession,
    assistant_message: ConversationMessage,
    result: FamilyQaQueryResponse,
) -> None:
    now = utc_now_iso()
    assistant_message.content = result.answer
    assistant_message.status = "completed"
    assistant_message.message_type = "text"
    assistant_message.effective_agent_id = result.effective_agent_id
    assistant_message.ai_provider_code = result.ai_provider_code
    assistant_message.ai_trace_id = result.ai_trace_id
    assistant_message.degraded = result.degraded or result.ai_degraded
    assistant_message.error_code = None
    assistant_message.facts_json = dump_json([item.model_dump(mode="json") for item in result.facts]) or "[]"
    assistant_message.suggestions_json = dump_json(result.suggestions) or "[]"
    assistant_message.updated_at = now
    session.active_agent_id = result.effective_agent_id or session.active_agent_id
    session.last_message_at = now
    session.updated_at = now
    db.flush()


def _generate_memory_candidates_for_turn(
    db: Session,
    *,
    session: ConversationSession,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
) -> None:
    try:
        result = invoke_llm(
            db,
            task_type="memory_extraction",
            variables={
                "conversation": _build_memory_extraction_conversation(user_message, assistant_message),
                "member_context": _build_member_context(db, household_id=session.household_id),
            },
            household_id=session.household_id,
        )
    except Exception:
        return

    if not isinstance(result.data, MemoryExtractionOutput):
        return

    for item in result.data.memories[:5]:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("content") or "").strip()
        if not summary:
            continue
        title = str(item.get("title") or "").strip() or _build_memory_candidate_title(summary)
        memory_type = str(item.get("type") or item.get("memory_type") or "fact").strip() or "fact"
        confidence_raw = item.get("confidence")
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.6
        candidate = ConversationMemoryCandidate(
            id=new_uuid(),
            session_id=session.id,
            source_message_id=assistant_message.id,
            requester_member_id=session.requester_member_id,
            status="pending_review",
            memory_type=memory_type[:30],
            title=title[:200],
            summary=summary,
            content_json=dump_json(item) or "{}",
            confidence=max(0.0, min(confidence, 1.0)),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        repository.add_memory_candidate(db, candidate)
    db.flush()


def _fail_assistant_message(
    db: Session,
    *,
    session: ConversationSession,
    assistant_message: ConversationMessage,
    error_message: str,
    error_code: str,
) -> None:
    now = utc_now_iso()
    assistant_message.content = error_message
    assistant_message.status = "failed"
    assistant_message.message_type = "error"
    assistant_message.error_code = error_code
    assistant_message.updated_at = now
    session.last_message_at = now
    session.updated_at = now
    db.flush()


def _build_session_title(message: str) -> str:
    return f"{message[:18]}..." if len(message) > 18 else message


def _build_memory_extraction_conversation(
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
) -> str:
    return f"用户：{user_message.content}\n助手：{assistant_message.content}"


def _build_member_context(db: Session, *, household_id: str) -> str:
    members, _ = member_service.list_members(db, household_id=household_id, page=1, page_size=100, status_value="active")
    if not members:
        return "当前家庭还没有有效成员。"
    lines: list[str] = []
    for member in members:
        display_name = member.nickname or member.name
        lines.append(f"- {display_name}（{member.role}）")
    return "\n".join(lines)


def _build_memory_candidate_title(summary: str) -> str:
    normalized = summary.strip()
    return normalized[:18] + "..." if len(normalized) > 18 else normalized


def _normalize_memory_type(memory_type: str) -> str:
    if memory_type in {"fact", "event", "preference", "relation", "growth"}:
        return memory_type
    return "fact"


async def _broadcast_conversation_event(
    db: Session,
    *,
    connection_manager: RealtimeConnectionManager,
    household_id: str,
    session: ConversationSession,
    event_type: str,
    payload: dict[str, object],
    request_id: str | None = None,
) -> None:
    seq = repository.claim_next_event_seq(db, session=session)
    db.commit()
    event = build_bootstrap_realtime_event(
        event_type=event_type,  # type: ignore[arg-type]
        session_id=session.id,
        request_id=request_id,
        seq=seq,
        payload=payload,
    )
    await connection_manager.broadcast(household_id=household_id, session_id=session.id, event=event)


def _build_recent_conversation_history(
    db: Session,
    *,
    session_id: str,
    current_request_id: str,
    limit: int = 8,
) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for item in repository.list_messages(db, session_id=session_id):
        if item.request_id == current_request_id:
            continue
        if item.role not in {"user", "assistant", "system"}:
            continue
        if item.status != "completed":
            continue
        content = item.content.strip()
        if not content:
            continue
        history.append({"role": item.role, "content": content})
    return history[-limit:]


def _split_text_chunks(text: str, chunk_size: int = 24) -> list[str]:
    if not text:
        return [""]
    return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]


def _render_turn_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        return str(detail) if detail else "当前消息处理失败，请稍后重试。"
    return "当前消息处理失败，请稍后重试。"


def _resolve_turn_error_code(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        if exc.status_code == status.HTTP_409_CONFLICT:
            return "request_conflict"
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return "permission_denied"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return "session_not_found"
        return "turn_http_error"
    return "turn_failed"


async def run_conversation_realtime_turn(
    db: Session,
    *,
    session_id: str,
    request_id: str,
    user_message: str,
    actor: ActorContext,
    connection_manager: RealtimeConnectionManager,
) -> None:
    session = _get_visible_session(db, session_id=session_id, actor=actor)
    if session.current_request_id and session.current_request_id != request_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="上一轮还没结束，请稍后再试")

    payload = ConversationTurnCreate(message=user_message, agent_id=session.active_agent_id, channel="user_web")
    request_id, user_message_row, assistant_message_row = _create_pending_turn(
        db,
        session=session,
        payload=payload,
        request_id=request_id,
    )
    session.current_request_id = request_id
    db.flush()

    await _broadcast_conversation_event(
        db,
        connection_manager=connection_manager,
        household_id=session.household_id,
        session=session,
        event_type="user.message.accepted",
        request_id=request_id,
        payload={},
    )

    try:
        result = _run_family_qa_turn(
            db,
            session=session,
            question=user_message.strip(),
            request_id=request_id,
            actor=actor,
        )
        full_text = result.answer
        for chunk in _split_text_chunks(full_text):
            await _broadcast_conversation_event(
                db,
                connection_manager=connection_manager,
                household_id=session.household_id,
                session=session,
                event_type="agent.chunk",
                request_id=request_id,
                payload={"text": chunk},
            )

        _complete_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message_row,
            result=result,
        )
        _generate_memory_candidates_for_turn(
            db,
            session=session,
            user_message=user_message_row,
            assistant_message=assistant_message_row,
        )
        session.current_request_id = None
        session.updated_at = utc_now_iso()
        db.flush()
        await _broadcast_conversation_event(
            db,
            connection_manager=connection_manager,
            household_id=session.household_id,
            session=session,
            event_type="agent.done",
            request_id=request_id,
            payload={},
        )
        snapshot = _to_session_detail_read(db, session)
        await _broadcast_conversation_event(
            db,
            connection_manager=connection_manager,
            household_id=session.household_id,
            session=session,
            event_type="session.snapshot",
            payload={"snapshot": snapshot.model_dump(mode="json")},
        )
    except Exception as exc:
        _fail_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message_row,
            error_message=_render_turn_error(exc),
            error_code=_resolve_turn_error_code(exc),
        )
        session.current_request_id = None
        session.updated_at = utc_now_iso()
        db.flush()
        await _broadcast_conversation_event(
            db,
            connection_manager=connection_manager,
            household_id=session.household_id,
            session=session,
            event_type="agent.error",
            request_id=request_id,
            payload={
                "detail": _render_turn_error(exc),
                "error_code": _resolve_turn_error_code(exc),
            },
        )
        snapshot = _to_session_detail_read(db, session)
        await _broadcast_conversation_event(
            db,
            connection_manager=connection_manager,
            household_id=session.household_id,
            session=session,
            event_type="session.snapshot",
            payload={"snapshot": snapshot.model_dump(mode="json")},
        )


def _to_session_read(db: Session, row: ConversationSession) -> ConversationSessionRead:
    message_rows = list(repository.list_messages(db, session_id=row.id))
    latest_message = message_rows[-1] if message_rows else None
    effective_agent = (
        agent_repository.get_agent_by_household_and_id(
            db,
            household_id=row.household_id,
            agent_id=row.active_agent_id,
        )
        if row.active_agent_id
        else None
    )

    return ConversationSessionRead(
        id=row.id,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        session_mode=row.session_mode,
        active_agent_id=row.active_agent_id,
        active_agent_name=effective_agent.display_name if effective_agent is not None else None,
        active_agent_type=effective_agent.agent_type if effective_agent is not None else None,
        title=row.title,
        status=row.status,
        last_message_at=row.last_message_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=len(message_rows),
        latest_message_preview=(latest_message.content[:80] if latest_message and latest_message.content else None),
    )


def _to_session_detail_read(db: Session, row: ConversationSession) -> ConversationSessionDetailRead:
    session_read = _to_session_read(db, row)
    messages = [_to_message_read(item) for item in repository.list_messages(db, session_id=row.id)]
    candidates = [_to_candidate_read(item) for item in repository.list_memory_candidates(db, session_id=row.id)]
    return ConversationSessionDetailRead(
        **session_read.model_dump(mode="json"),
        messages=messages,
        memory_candidates=candidates,
    )


def _to_message_read(row: ConversationMessage) -> ConversationMessageRead:
    facts = load_json(row.facts_json) or []
    suggestions = load_json(row.suggestions_json) or []
    return ConversationMessageRead(
        id=row.id,
        session_id=row.session_id,
        request_id=row.request_id,
        seq=row.seq,
        role=row.role,
        message_type=row.message_type,
        content=row.content,
        status=row.status,
        effective_agent_id=row.effective_agent_id,
        ai_provider_code=row.ai_provider_code,
        ai_trace_id=row.ai_trace_id,
        degraded=row.degraded,
        error_code=row.error_code,
        facts=facts if isinstance(facts, list) else [],
        suggestions=[str(item) for item in suggestions] if isinstance(suggestions, list) else [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_candidate_read(row: ConversationMemoryCandidate) -> ConversationMemoryCandidateRead:
    content = load_json(row.content_json) or {}
    return ConversationMemoryCandidateRead(
        id=row.id,
        session_id=row.session_id,
        source_message_id=row.source_message_id,
        requester_member_id=row.requester_member_id,
        status=row.status,
        memory_type=row.memory_type,
        title=row.title,
        summary=row.summary,
        content=content if isinstance(content, dict) else {},
        confidence=row.confidence,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
