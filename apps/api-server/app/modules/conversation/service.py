import logging
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.core.config import settings
from app.core.logging import dump_conversation_debug_event, get_conversation_debug_logger
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository as agent_repository
from app.modules.agent.schemas import AgentAutonomousActionPolicy, AgentSoulProfileUpsert, AgentUpdate
from app.modules.agent.service import AgentNotFoundError, resolve_effective_agent, update_agent, upsert_agent_soul
from app.modules.account.service import AuthenticatedActor
from app.modules.audit.service import write_audit_log
from app.modules.conversation import repository
from app.modules.conversation.models import (
    ConversationActionRecord,
    ConversationDebugLog,
    ConversationMemoryCandidate,
    ConversationMessage,
    ConversationProposalBatch,
    ConversationProposalItem,
    ConversationSession,
    ConversationTurnSource,
)
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationOrchestratorResult,
    adetect_conversation_intent,
    run_orchestrated_turn,
    stream_orchestrated_turn,
)
from app.modules.conversation.proposal_pipeline import (
    ProposalPipeline,
    ProposalPipelineResult,
    build_turn_proposal_context,
    persist_proposal_batch,
)
from app.modules.conversation.proposal_analyzers import ProposalDraft
from app.modules.conversation.schemas import (
    ConversationActionExecutionRead,
    ConversationDebugLogListRead,
    ConversationDebugLogRead,
    ConversationActionRecordRead,
    ConversationMemoryCandidateActionRead,
    ConversationMemoryCandidateRead,
    ConversationMessageRead,
    ConversationProposalBatchRead,
    ConversationProposalExecutionRead,
    ConversationProposalItemRead,
    ConversationSessionCreate,
    ConversationSessionDetailRead,
    ConversationSessionListResponse,
    ConversationSessionRead,
    ConversationTurnCreate,
    ConversationTurnRead,
)
from app.modules.household.models import Household
from app.modules.llm_task import ainvoke_llm, invoke_llm
from app.modules.llm_task.output_models import MemoryExtractionOutput
from app.modules.memory.schemas import MemoryCardCorrectionPayload, MemoryCardManualCreate
from app.modules.memory.service import correct_memory_card, create_manual_memory_card
from app.modules.member import service as member_service
from app.modules.reminder.schemas import ReminderTaskCreate
from app.modules.reminder.service import create_task as create_reminder_task
from app.modules.reminder.service import delete_task as delete_reminder_task
from app.modules.realtime.connection_manager import RealtimeConnectionManager
from app.modules.realtime.schemas import build_bootstrap_realtime_event
from app.modules.scheduler.draft_service import confirm_draft_from_conversation
from app.modules.scheduler.schemas import ScheduledTaskDraftConfirmRequest
from app.modules.scheduler.service import delete_task_definition, set_task_enabled, update_task_definition
from app.modules.scheduler.schemas import ScheduledTaskDefinitionUpdate

logger = logging.getLogger(__name__)


class ConversationNotFoundError(LookupError):
    pass


def record_conversation_turn_source(
    db: Session,
    *,
    conversation_session_id: str,
    conversation_turn_id: str,
    source_kind: str,
    platform_code: str | None = None,
    channel_account_id: str | None = None,
    voice_terminal_code: str | None = None,
    external_conversation_key: str | None = None,
    thread_key: str | None = None,
    channel_inbound_event_id: str | None = None,
) -> ConversationTurnSource:
    existing = repository.get_turn_source_by_turn_id(
        db,
        conversation_turn_id=conversation_turn_id,
    )
    if existing is not None:
        return existing

    row = ConversationTurnSource(
        id=new_uuid(),
        conversation_session_id=conversation_session_id,
        conversation_turn_id=conversation_turn_id,
        source_kind=source_kind,
        platform_code=_normalize_optional_text(platform_code),
        channel_account_id=_normalize_optional_text(channel_account_id),
        voice_terminal_code=_normalize_optional_text(voice_terminal_code),
        external_conversation_key=_normalize_optional_text(external_conversation_key),
        thread_key=_normalize_optional_text(thread_key),
        channel_inbound_event_id=_normalize_optional_text(channel_inbound_event_id),
        created_at=utc_now_iso(),
    )
    repository.add_turn_source(db, row)
    db.flush()
    return row


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


def confirm_conversation_proposal(
    db: Session,
    *,
    proposal_item_id: str,
    actor: ActorContext,
) -> ConversationProposalExecutionRead:
    item = repository.get_proposal_item(db, proposal_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal item not found")
    batch = repository.get_proposal_batch(db, item.batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal batch not found")
    session = _get_visible_session(db, session_id=batch.session_id, actor=actor)
    if item.status != "pending_confirmation":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation proposal item is not waiting for confirmation")

    affected_target_id = _execute_proposal_item(
        db,
        item=item,
        session=session,
        actor=actor,
    )
    item.status = "completed"
    item.updated_at = utc_now_iso()
    _refresh_proposal_batch_status(db, batch_id=batch.id)
    _append_debug_log(
        db,
        session=session,
        request_id=batch.request_id,
        stage="proposal.item.confirmed",
        source="proposal",
        message="提案项已确认并执行。",
        payload={
            "proposal_item_id": item.id,
            "proposal_kind": item.proposal_kind,
            "affected_target_id": affected_target_id,
        },
    )
    db.flush()
    return ConversationProposalExecutionRead(
        item=_to_proposal_item_read(item),
        affected_target_id=affected_target_id,
    )


def dismiss_conversation_proposal(
    db: Session,
    *,
    proposal_item_id: str,
    actor: ActorContext,
) -> ConversationProposalExecutionRead:
    item = repository.get_proposal_item(db, proposal_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal item not found")
    batch = repository.get_proposal_batch(db, item.batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal batch not found")
    _get_visible_session(db, session_id=batch.session_id, actor=actor)
    if item.status != "pending_confirmation":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation proposal item is not waiting for confirmation")
    item.status = "dismissed"
    item.updated_at = utc_now_iso()
    _refresh_proposal_batch_status(db, batch_id=batch.id)
    session = _get_visible_session(db, session_id=batch.session_id, actor=actor)
    _append_debug_log(
        db,
        session=session,
        request_id=batch.request_id,
        stage="proposal.item.dismissed",
        source="proposal",
        message="提案项已忽略。",
        payload={
            "proposal_item_id": item.id,
            "proposal_kind": item.proposal_kind,
        },
    )
    db.flush()
    return ConversationProposalExecutionRead(
        item=_to_proposal_item_read(item),
        affected_target_id=None,
    )


def _execute_proposal_item(
    db: Session,
    *,
    item: ConversationProposalItem,
    session: ConversationSession,
    actor: ActorContext,
) -> str | None:
    payload = load_json(item.payload_json) or {}
    if item.proposal_kind == "memory_write":
        memory_card = create_manual_memory_card(
            db,
            payload=MemoryCardManualCreate(
                household_id=session.household_id,
                memory_type=str(payload.get("memory_type") or payload.get("type") or "fact"),
                title=item.title,
                summary=item.summary or item.title,
                content=payload if isinstance(payload, dict) else {},
                status="active",
                visibility="family",
                importance=3,
                confidence=item.confidence,
                subject_member_id=session.requester_member_id,
                source_event_id=None,
                dedupe_key=item.dedupe_key or f"proposal:{item.id}",
                effective_at=None,
                last_observed_at=None,
                related_members=[],
                reason="applied from conversation proposal",
            ),
            actor=actor,
        )
        return memory_card.id
    if item.proposal_kind == "config_apply":
        return _apply_config_proposal_item(db, session=session, payload=payload)
    if item.proposal_kind == "reminder_create":
        return _apply_reminder_proposal_item(db, session=session, payload=payload)
    if item.proposal_kind == "scheduled_task_create":
        return _apply_scheduled_task_proposal_item(db, payload=payload, actor=actor)
    if item.proposal_kind in {"scheduled_task_update", "scheduled_task_pause", "scheduled_task_resume", "scheduled_task_delete"}:
        return _apply_scheduled_task_operation_proposal_item(db, proposal_kind=item.proposal_kind, payload=payload, actor=actor)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported conversation proposal kind")


def get_conversation_session_snapshot(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
) -> ConversationSessionDetailRead:
    return get_conversation_session_detail(db, session_id=session_id, actor=actor)


def list_conversation_debug_logs(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
    request_id: str | None = None,
    limit: int = 200,
) -> ConversationDebugLogListRead:
    session = _get_visible_session(db, session_id=session_id, actor=actor)
    rows = repository.list_debug_logs(db, session_id=session.id, request_id=request_id, limit=limit)
    return ConversationDebugLogListRead(
        session_id=session.id,
        debug_enabled=settings.conversation_debug_log_enabled,
        request_id=request_id,
        items=[_to_debug_log_read(item) for item in rows],
    )


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
    _append_debug_log(
        db,
        session=session,
        request_id=request_id,
        stage="turn.received",
        source="service",
        message="收到新的聊天请求。",
        payload={
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "message": payload.message.strip(),
            "channel": payload.channel,
            "session_mode": session.session_mode,
        },
    )

    outcome = "completed"
    error_message: str | None = None

    try:
        result = _run_orchestrated_turn(
            db,
            session=session,
            question=payload.message.strip(),
            request_id=request_id,
            actor=actor,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="orchestrator.completed",
            source="orchestrator",
            message="编排层已完成意图识别和主路由。",
            payload=_build_orchestrator_debug_payload(result),
        )
        _complete_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message,
            result=result,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="assistant.completed",
            source="service",
            message="助手消息已落库。",
            payload={
                "assistant_message_id": assistant_message.id,
                "intent": result.intent.value,
                "content_preview": result.text[:120],
                "degraded": result.degraded,
            },
        )
        proposal_pipeline_result = _run_proposal_pipeline_for_turn(
            db,
            session=session,
            request_id=request_id,
            user_message=user_message,
            assistant_message=assistant_message,
            result=result,
            actor=actor,
        )
        if proposal_pipeline_result is None and _result_has_actionable_proposals(result):
            proposal_pipeline_result = _persist_legacy_result_as_proposal_batch(
                db,
                session=session,
                request_id=request_id,
                user_message=user_message,
                assistant_message=assistant_message,
                result=result,
                actor=actor,
            )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="proposal.model.applied",
            source="proposal",
            message="本轮已直接切到新提案模型，不再写旧候选和旧动作记录。",
            payload={
                "proposal_batch_id": None if proposal_pipeline_result is None else proposal_pipeline_result.batch_id,
                "proposal_count": 0 if proposal_pipeline_result is None else len(proposal_pipeline_result.drafts),
            },
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.completed",
            source="service",
            message="本轮聊天处理完成。",
            payload={"outcome": outcome},
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
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.failed",
            source="service",
            level="error",
            message="本轮聊天处理失败。",
            payload={
                "error_message": error_message,
                "error_code": _resolve_turn_error_code(exc),
            },
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


async def acreate_conversation_turn(
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
    _append_debug_log(
        db,
        session=session,
        request_id=request_id,
        stage="turn.received",
        source="service",
        message="收到新的聊天请求。",
        payload={
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "message": payload.message.strip(),
            "channel": payload.channel,
            "session_mode": session.session_mode,
        },
    )

    outcome = "completed"
    error_message: str | None = None

    try:
        result = await _arun_orchestrated_turn(
            db,
            session=session,
            question=payload.message.strip(),
            request_id=request_id,
            actor=actor,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="orchestrator.completed",
            source="orchestrator",
            message="编排层已完成意图识别和主路由。",
            payload=_build_orchestrator_debug_payload(result),
        )
        _complete_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message,
            result=result,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="assistant.completed",
            source="service",
            message="助手消息已落库。",
            payload={
                "assistant_message_id": assistant_message.id,
                "intent": result.intent.value,
                "content_preview": result.text[:120],
                "degraded": result.degraded,
            },
        )
        proposal_pipeline_result = _run_proposal_pipeline_for_turn(
            db,
            session=session,
            request_id=request_id,
            user_message=user_message,
            assistant_message=assistant_message,
            result=result,
            actor=actor,
        )
        if proposal_pipeline_result is None and _result_has_actionable_proposals(result):
            proposal_pipeline_result = _persist_legacy_result_as_proposal_batch(
                db,
                session=session,
                request_id=request_id,
                user_message=user_message,
                assistant_message=assistant_message,
                result=result,
                actor=actor,
            )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="proposal.model.applied",
            source="proposal",
            message="本轮已直接切到新提案模型，不再写旧候选和旧动作记录。",
            payload={
                "proposal_batch_id": None if proposal_pipeline_result is None else proposal_pipeline_result.batch_id,
                "proposal_count": 0 if proposal_pipeline_result is None else len(proposal_pipeline_result.drafts),
            },
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.completed",
            source="service",
            message="本轮聊天处理完成。",
            payload={"outcome": outcome},
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
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.failed",
            source="service",
            level="error",
            message="本轮聊天处理失败。",
            payload={
                "error_message": error_message,
                "error_code": _resolve_turn_error_code(exc),
            },
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
    _mark_linked_memory_action_completed(
        db,
        candidate_id=candidate.id,
        memory_card_id=memory_card.id,
    )
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
    _mark_linked_memory_action_dismissed(db, candidate_id=candidate.id)
    db.flush()
    return ConversationMemoryCandidateActionRead(
        candidate=_to_candidate_read(candidate),
        memory_card_id=None,
    )


def confirm_conversation_action(
    db: Session,
    *,
    action_id: str,
    actor: ActorContext,
) -> ConversationActionExecutionRead:
    row = repository.get_action_record(db, action_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation action not found")
    _get_visible_session(db, session_id=row.session_id, actor=actor)
    if row.status != "pending_confirmation":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation action is not waiting for confirmation")
    _execute_action_record(db, row=row, actor=actor)
    db.flush()
    return ConversationActionExecutionRead(action=_to_action_read(row))


def dismiss_conversation_action(
    db: Session,
    *,
    action_id: str,
    actor: ActorContext,
) -> ConversationActionExecutionRead:
    row = repository.get_action_record(db, action_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation action not found")
    _get_visible_session(db, session_id=row.session_id, actor=actor)
    if row.status != "pending_confirmation":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation action is not waiting for confirmation")
    if row.action_name == "memory.write" and row.target_ref:
        dismiss_memory_candidate(db, candidate_id=row.target_ref, actor=actor)
    row.status = "dismissed"
    row.updated_at = utc_now_iso()
    db.flush()
    return ConversationActionExecutionRead(action=_to_action_read(row))


def undo_conversation_action(
    db: Session,
    *,
    action_id: str,
    actor: ActorContext,
) -> ConversationActionExecutionRead:
    row = repository.get_action_record(db, action_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation action not found")
    _get_visible_session(db, session_id=row.session_id, actor=actor)
    if row.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation action cannot be undone")
    undo_payload = load_json(row.undo_payload_json) or {}
    if not isinstance(undo_payload, dict) or not undo_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation action does not support undo")
    try:
        _undo_action_record(db, row=row, undo_payload=undo_payload, actor=actor)
        row.status = "undone"
        row.undone_at = utc_now_iso()
        row.updated_at = row.undone_at
    except HTTPException:
        row.status = "undo_failed"
        row.updated_at = utc_now_iso()
        raise
    db.flush()
    return ConversationActionExecutionRead(action=_to_action_read(row))


def _apply_action_policy_for_turn(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    result: ConversationOrchestratorResult,
    actor: ActorContext,
) -> None:
    policy = _resolve_autonomous_action_policy(db, session=session)
    action_plans = _build_turn_action_plans(result)
    for plan in action_plans:
        policy_mode = _resolve_policy_mode(policy, action_category=str(plan["action_category"]))
        row = ConversationActionRecord(
            id=new_uuid(),
            session_id=session.id,
            request_id=request_id,
            trigger_message_id=user_message.id,
            source_message_id=assistant_message.id,
            intent=result.intent_detection.primary_intent.value if result.intent_detection is not None else result.intent.value,
            action_category=str(plan["action_category"]),
            action_name=str(plan["action_name"]),
            policy_mode=policy_mode,
            status="pending_confirmation" if policy_mode == "ask" else "completed",
            title=str(plan["title"])[:200],
            summary=str(plan["summary"]) if plan.get("summary") is not None else None,
            target_ref=None,
            plan_payload_json="{}",
            result_payload_json=None,
            undo_payload_json=None,
            created_at=utc_now_iso(),
            executed_at=None,
            undone_at=None,
            updated_at=utc_now_iso(),
        )
        repository.add_action_record(db, row)

        plan_payload = dict(plan)
        if result.intent_detection is not None:
            plan_payload["intent_detection"] = result.intent_detection.to_payload()
        if row.action_name == "memory.write":
            candidate = _create_memory_candidate_from_payload(
                db,
                session=session,
                source_message_id=assistant_message.id,
                item=plan_payload,
            )
            if candidate is None:
                row.status = "failed"
                row.result_payload_json = dump_json({"error": "memory_candidate_invalid"})
                row.updated_at = utc_now_iso()
                continue
            repository.add_memory_candidate(db, candidate)
            row.target_ref = candidate.id
            plan_payload["candidate_id"] = candidate.id

        row.plan_payload_json = dump_json(plan_payload) or "{}"
        row.updated_at = utc_now_iso()

        if policy_mode == "ask":
            continue

        try:
            _execute_action_record(db, row=row, actor=actor)
        except HTTPException as exc:
            row.status = "failed"
            row.result_payload_json = dump_json({"error": exc.detail if isinstance(exc.detail, str) else "action_execution_failed"})
            row.updated_at = utc_now_iso()


def _build_turn_action_plans(result: ConversationOrchestratorResult) -> list[dict]:
    plans: list[dict] = []
    for item in result.memory_candidate_payloads:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("content") or "").strip()
        title = str(item.get("title") or "").strip() or summary[:18]
        if not summary or not title:
            continue
        plans.append(
            {
                "action_category": "memory",
                "action_name": "memory.write",
                "title": f"写入记忆：{title}",
                "summary": summary,
                "memory_type": str(item.get("memory_type") or item.get("type") or "fact"),
                "candidate_title": title,
                "candidate_summary": summary,
                "content": item.get("content") if isinstance(item.get("content"), dict) else item,
                "confidence": float(item.get("confidence") or 0.75),
            }
        )
    if isinstance(result.config_suggestion, dict) and any(result.config_suggestion.values()):
        plans.append(
            {
                "action_category": "config",
                "action_name": "config.apply",
                "title": "应用 Agent 配置建议",
                "summary": _build_config_action_summary(result.config_suggestion),
                "suggestion": result.config_suggestion,
            }
        )
    for item in result.action_payloads:
        if not isinstance(item, dict):
            continue
        if str(item.get("action_type")) == "reminder_create":
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            plans.append(
                {
                    "action_category": "action",
                    "action_name": "reminder.create",
                    "title": f"创建提醒：{title}",
                    "summary": _build_reminder_action_summary(item),
                    "reminder": item,
                }
            )
    return plans


def _execute_action_record(
    db: Session,
    *,
    row: ConversationActionRecord,
    actor: ActorContext,
) -> None:
    if row.action_name == "memory.write":
        _execute_memory_action_record(db, row=row, actor=actor)
        return
    if row.action_name == "config.apply":
        _execute_config_action_record(db, row=row)
        return
    if row.action_name == "reminder.create":
        _execute_reminder_action_record(db, row=row)
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported conversation action")


def _undo_action_record(
    db: Session,
    *,
    row: ConversationActionRecord,
    undo_payload: dict,
    actor: ActorContext,
) -> None:
    if row.action_name == "memory.write":
        memory_card_id = str(undo_payload.get("memory_card_id") or "")
        if not memory_card_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="memory undo target missing")
        correct_memory_card(
            db,
            memory_id=memory_card_id,
            payload=MemoryCardCorrectionPayload(action="invalidate", reason="undo conversation action"),
            actor=actor,
        )
        return
    if row.action_name == "config.apply":
        _restore_agent_config_snapshot(db, session_id=row.session_id, undo_payload=undo_payload)
        return
    if row.action_name == "reminder.create":
        reminder_id = str(undo_payload.get("reminder_id") or "")
        if not reminder_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="reminder undo target missing")
        delete_reminder_task(db, task_id=reminder_id, updated_by="conversation-ai-undo")
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported conversation action undo")


def _execute_memory_action_record(
    db: Session,
    *,
    row: ConversationActionRecord,
    actor: ActorContext,
) -> None:
    candidate_id = row.target_ref or str((load_json(row.plan_payload_json) or {}).get("candidate_id") or "")
    if not candidate_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="memory candidate missing")
    result = confirm_memory_candidate(db, candidate_id=candidate_id, actor=actor)
    row.status = "completed"
    row.executed_at = utc_now_iso()
    row.updated_at = row.executed_at
    row.result_payload_json = dump_json(
        {
            "candidate_id": candidate_id,
            "memory_card_id": result.memory_card_id,
        }
    )
    row.undo_payload_json = dump_json({"memory_card_id": result.memory_card_id})


def _execute_config_action_record(db: Session, *, row: ConversationActionRecord) -> None:
    plan_payload = load_json(row.plan_payload_json) or {}
    suggestion = plan_payload.get("suggestion")
    if not isinstance(suggestion, dict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="config suggestion missing")
    session = repository.get_session(db, row.session_id)
    if session is None or not session.active_agent_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active agent missing")
    agent = agent_repository.get_agent_by_household_and_id(db, household_id=session.household_id, agent_id=session.active_agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
    current_soul = agent_repository.get_active_soul_profile(db, agent_id=agent.id)
    before_snapshot = {
        "display_name": agent.display_name,
        "soul": None if current_soul is None else {
            "self_identity": current_soul.self_identity,
            "role_summary": current_soul.role_summary,
            "intro_message": current_soul.intro_message,
            "speaking_style": current_soul.speaking_style,
            "personality_traits": load_json(current_soul.personality_traits_json) or [],
            "service_focus": load_json(current_soul.service_focus_json) or [],
            "service_boundaries": load_json(current_soul.service_boundaries_json),
        },
    }
    next_display_name = str(suggestion.get("display_name") or "").strip()
    if next_display_name and next_display_name != agent.display_name:
        update_agent(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentUpdate(display_name=next_display_name),
        )
    has_soul_change = bool(suggestion.get("speaking_style")) or bool(suggestion.get("personality_traits"))
    if has_soul_change:
        speaking_style = str(suggestion.get("speaking_style") or "").strip() or (current_soul.speaking_style if current_soul is not None else None)
        personality_traits_raw = suggestion.get("personality_traits")
        personality_traits = [str(item).strip() for item in personality_traits_raw] if isinstance(personality_traits_raw, list) else []
        if not personality_traits and current_soul is not None:
            personality_traits = [str(item) for item in (load_json(current_soul.personality_traits_json) or [])]
        service_focus = [str(item) for item in (load_json(current_soul.service_focus_json) or [])] if current_soul is not None else []
        upsert_agent_soul(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentSoulProfileUpsert(
                self_identity=current_soul.self_identity if current_soul is not None else f"我是{next_display_name or agent.display_name}",
                role_summary=current_soul.role_summary if current_soul is not None else "负责家庭事务",
                intro_message=current_soul.intro_message if current_soul is not None else None,
                speaking_style=speaking_style,
                personality_traits=personality_traits,
                service_focus=service_focus,
                service_boundaries=load_json(current_soul.service_boundaries_json) if current_soul is not None else None,
                created_by="conversation-ai",
            ),
        )
    row.status = "completed"
    row.target_ref = agent.id
    row.executed_at = utc_now_iso()
    row.updated_at = row.executed_at
    row.result_payload_json = dump_json({"applied": suggestion})
    row.undo_payload_json = dump_json(before_snapshot)


def _execute_reminder_action_record(db: Session, *, row: ConversationActionRecord) -> None:
    plan_payload = load_json(row.plan_payload_json) or {}
    reminder = plan_payload.get("reminder")
    if not isinstance(reminder, dict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="reminder payload missing")
    session = repository.get_session(db, row.session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found")
    trigger_at = str(reminder.get("trigger_at") or "").strip()
    title = str(reminder.get("title") or "").strip()
    if not trigger_at or not title:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="reminder payload incomplete")
    task = create_reminder_task(
        db,
        ReminderTaskCreate(
            household_id=session.household_id,
            owner_member_id=session.requester_member_id,
            title=title,
            description=str(reminder.get("description") or "").strip() or None,
            reminder_type="family",
            target_member_ids=[session.requester_member_id] if session.requester_member_id else [],
            preferred_room_ids=[],
            schedule_kind="once",
            schedule_rule={"trigger_at": trigger_at},
            priority="normal",
            delivery_channels=["in_app"],
            ack_required=False,
            escalation_policy={},
            enabled=True,
            updated_by="conversation-ai",
        ),
    )
    row.status = "completed"
    row.target_ref = task.id
    row.executed_at = utc_now_iso()
    row.updated_at = row.executed_at
    row.result_payload_json = dump_json({"reminder_id": task.id, "trigger_at": trigger_at})
    row.undo_payload_json = dump_json({"reminder_id": task.id})


def _restore_agent_config_snapshot(db: Session, *, session_id: str, undo_payload: dict) -> None:
    session = repository.get_session(db, session_id)
    if session is None or not session.active_agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found")
    agent = agent_repository.get_agent_by_household_and_id(db, household_id=session.household_id, agent_id=session.active_agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
    display_name = str(undo_payload.get("display_name") or "").strip()
    if display_name:
        update_agent(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentUpdate(display_name=display_name),
        )
    soul = undo_payload.get("soul")
    if isinstance(soul, dict):
        upsert_agent_soul(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentSoulProfileUpsert(
                self_identity=str(soul.get("self_identity") or "我是家庭助手"),
                role_summary=str(soul.get("role_summary") or "负责家庭事务"),
                intro_message=str(soul.get("intro_message") or "").strip() or None,
                speaking_style=str(soul.get("speaking_style") or "").strip() or None,
                personality_traits=[str(item) for item in soul.get("personality_traits", [])] if isinstance(soul.get("personality_traits"), list) else [],
                service_focus=[str(item) for item in soul.get("service_focus", [])] if isinstance(soul.get("service_focus"), list) else [],
                service_boundaries=soul.get("service_boundaries") if isinstance(soul.get("service_boundaries"), dict) else None,
                created_by="conversation-ai-undo",
            ),
        )


def _resolve_autonomous_action_policy(
    db: Session,
    *,
    session: ConversationSession,
) -> AgentAutonomousActionPolicy:
    if not session.active_agent_id:
        return AgentAutonomousActionPolicy()
    runtime_policy = agent_repository.get_runtime_policy(db, agent_id=session.active_agent_id)
    if runtime_policy is None:
        return AgentAutonomousActionPolicy()
    data = load_json(runtime_policy.autonomous_action_policy_json)
    if not isinstance(data, dict):
        return AgentAutonomousActionPolicy()
    return AgentAutonomousActionPolicy(
        memory=str(data.get("memory") or "ask"),
        config=str(data.get("config") or "ask"),
        action=str(data.get("action") or "ask"),
    )


def _resolve_policy_mode(policy: AgentAutonomousActionPolicy, *, action_category: str) -> str:
    if action_category == "memory":
        return policy.memory
    if action_category == "config":
        return policy.config
    return policy.action


def _build_config_action_summary(suggestion: dict) -> str:
    parts: list[str] = []
    display_name = str(suggestion.get("display_name") or "").strip()
    speaking_style = str(suggestion.get("speaking_style") or "").strip()
    personality_traits = suggestion.get("personality_traits")
    if display_name:
        parts.append(f"名称改成“{display_name}”")
    if speaking_style:
        parts.append(f"说话风格改成“{speaking_style}”")
    if isinstance(personality_traits, list) and personality_traits:
        parts.append(f"性格标签：{'、'.join(str(item) for item in personality_traits)}")
    return "；".join(parts) or "应用本轮配置建议"


def _build_reminder_action_summary(reminder: dict) -> str:
    trigger_at = str(reminder.get("trigger_at") or "").strip()
    description = str(reminder.get("description") or "").strip()
    parts = [part for part in [trigger_at, description] if part]
    return "；".join(parts) or "创建一次提醒"


def _mark_linked_memory_action_completed(
    db: Session,
    *,
    candidate_id: str,
    memory_card_id: str,
) -> None:
    action = repository.get_action_record_by_target_ref(db, target_ref=candidate_id, action_name="memory.write")
    if action is None:
        return
    action.status = "completed"
    action.executed_at = utc_now_iso()
    action.updated_at = action.executed_at
    action.result_payload_json = dump_json({"candidate_id": candidate_id, "memory_card_id": memory_card_id})
    action.undo_payload_json = dump_json({"memory_card_id": memory_card_id})


def _mark_linked_memory_action_dismissed(db: Session, *, candidate_id: str) -> None:
    action = repository.get_action_record_by_target_ref(db, target_ref=candidate_id, action_name="memory.write")
    if action is None:
        return
    action.status = "dismissed"
    action.updated_at = utc_now_iso()


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
    next_seq = repository.get_next_message_seq(db, session_id=session.id)

    user_message = ConversationMessage(
        id=new_uuid(),
        session_id=session.id,
        request_id=request_id,
        seq=next_seq,
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
        seq=next_seq + 1,
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


def _run_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    question: str,
    request_id: str,
    actor: ActorContext,
) -> ConversationOrchestratorResult:
    return run_orchestrated_turn(
        db,
        session=session,
        message=question,
        actor=actor,
        conversation_history=_build_recent_conversation_history(
            db,
            session_id=session.id,
            current_request_id=request_id,
        ),
        request_context={
            "request_id": request_id,
            "trace_id": request_id,
            "session_id": session.id,
            "channel": "conversation_turn",
        },
    )


async def _arun_orchestrated_turn(
    db: Session,
    *,
    session: ConversationSession,
    question: str,
    request_id: str,
    actor: ActorContext,
) -> ConversationOrchestratorResult:
    conversation_history = _build_recent_conversation_history(
        db,
        session_id=session.id,
        current_request_id=request_id,
    )
    request_context = {
        "request_id": request_id,
        "trace_id": request_id,
        "session_id": session.id,
        "channel": "conversation_turn",
    }
    final_text = ""
    final_result: ConversationOrchestratorResult | None = None
    async for event in stream_orchestrated_turn(
        db,
        session=session,
        message=question,
        actor=actor,
        conversation_history=conversation_history,
        request_context=request_context,
    ):
        event_type, event_payload = event
        if event_type == "chunk":
            final_text += str(event_payload)
            continue
        final_result = cast(ConversationOrchestratorResult, event_payload)

    if final_result is not None:
        return final_result

    return ConversationOrchestratorResult(
        intent=intent,
        text=final_text,
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
        intent_detection=detection,
    )


def _complete_assistant_message(
    db: Session,
    *,
    session: ConversationSession,
    assistant_message: ConversationMessage,
    result: ConversationOrchestratorResult,
) -> None:
    now = utc_now_iso()
    assistant_message.content = result.text
    assistant_message.status = "completed"
    assistant_message.message_type = "text"
    assistant_message.effective_agent_id = result.effective_agent_id
    assistant_message.ai_provider_code = result.ai_provider_code
    assistant_message.ai_trace_id = result.ai_trace_id
    assistant_message.degraded = result.degraded
    assistant_message.error_code = None
    assistant_message.facts_json = dump_json(result.facts) or "[]"
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
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    actor: ActorContext,
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
            request_context={
                "request_id": request_id,
                "trace_id": request_id,
                "session_id": session.id,
                "channel": "conversation_memory_autogen",
            },
        )
    except Exception:
        return

    if not isinstance(result.data, MemoryExtractionOutput):
        return

    generated_result = ConversationOrchestratorResult(
        intent=ConversationIntent.MEMORY_EXTRACTION,
        text="",
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[item for item in result.data.memories[:5] if isinstance(item, dict)],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
    )
    _apply_action_policy_for_turn(
        db,
        session=session,
        request_id=request_id,
        user_message=user_message,
        assistant_message=assistant_message,
        result=generated_result,
        actor=actor,
    )


async def _agenerate_memory_candidates_for_turn(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    actor: ActorContext,
) -> None:
    try:
        result = await ainvoke_llm(
            db,
            task_type="memory_extraction",
            variables={
                "conversation": _build_memory_extraction_conversation(user_message, assistant_message),
                "member_context": _build_member_context(db, household_id=session.household_id),
            },
            household_id=session.household_id,
            request_context={
                "request_id": request_id,
                "trace_id": request_id,
                "session_id": session.id,
                "channel": "conversation_memory_autogen",
            },
        )
    except Exception:
        return

    if not isinstance(result.data, MemoryExtractionOutput):
        return

    generated_result = ConversationOrchestratorResult(
        intent=ConversationIntent.MEMORY_EXTRACTION,
        text="",
        degraded=False,
        facts=[],
        suggestions=[],
        memory_candidate_payloads=[item for item in result.data.memories[:5] if isinstance(item, dict)],
        config_suggestion=None,
        action_payloads=[],
        ai_trace_id=None,
        ai_provider_code=getattr(result, "provider", None) or None,
        effective_agent_id=session.active_agent_id,
        effective_agent_name=None,
    )
    _apply_action_policy_for_turn(
        db,
        session=session,
        request_id=request_id,
        user_message=user_message,
        assistant_message=assistant_message,
        result=generated_result,
        actor=actor,
    )


def _persist_memory_candidate_payloads(
    db: Session,
    *,
    session: ConversationSession,
    assistant_message: ConversationMessage,
    candidate_payloads: list[dict],
) -> None:
    for item in candidate_payloads:
        candidate = _create_memory_candidate_from_payload(
            db,
            session=session,
            source_message_id=assistant_message.id,
            item=item,
        )
        if candidate is not None:
            repository.add_memory_candidate(db, candidate)
    db.flush()


def _create_memory_candidate_from_payload(
    db: Session,
    *,
    session: ConversationSession,
    source_message_id: str | None,
    item: dict,
) -> ConversationMemoryCandidate | None:
    _ = db
    if not isinstance(item, dict):
        return None
    summary = str(item.get("candidate_summary") or item.get("summary") or item.get("content") or "").strip()
    if not summary:
        return None
    title = str(item.get("candidate_title") or item.get("title") or "").strip() or _build_memory_candidate_title(summary)
    memory_type = str(item.get("memory_type") or item.get("type") or "fact").strip() or "fact"
    confidence_raw = item.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.6
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    return ConversationMemoryCandidate(
        id=new_uuid(),
        session_id=session.id,
        source_message_id=source_message_id,
        requester_member_id=session.requester_member_id,
        status="pending_review",
        memory_type=memory_type[:30],
        title=title[:200],
        summary=summary,
        content_json=dump_json(content) or "{}",
        confidence=max(0.0, min(confidence, 1.0)),
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )


def _append_debug_log(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str | None,
    stage: str,
    source: str,
    message: str,
    payload: dict | None = None,
    level: str = "info",
) -> None:
    if not settings.conversation_debug_log_enabled:
        return
    event_payload = {
        "session_id": session.id,
        "request_id": request_id,
        "stage": stage,
        "source": source,
        "level": level,
        "message": message,
        "payload": payload or {},
    }
    get_conversation_debug_logger().info(dump_conversation_debug_event(event_payload))
    repository.add_debug_log(
        db,
        ConversationDebugLog(
            id=new_uuid(),
            session_id=session.id,
            request_id=request_id,
            stage=stage[:80],
            source=source[:40],
            level=level[:20],
            message=message,
            payload_json=dump_json(payload or {}) or "{}",
            created_at=utc_now_iso(),
        ),
    )


def _build_orchestrator_debug_payload(result: ConversationOrchestratorResult) -> dict:
    detection_payload = result.intent_detection.to_payload() if result.intent_detection is not None else {}
    return {
        "final_result_intent": result.intent.value,
        "detected_route_intent": result.intent_detection.route_intent.value if result.intent_detection is not None else None,
        "lane_selection": result.lane_selection.to_payload() if result.lane_selection is not None else None,
        "intent_detection": detection_payload,
        "facts_count": len(result.facts),
        "suggestions_count": len(result.suggestions),
        "memory_candidate_count": len(result.memory_candidate_payloads),
        "action_payload_count": len(result.action_payloads),
        "has_config_suggestion": bool(result.config_suggestion),
        "degraded": result.degraded,
    }


def _serialize_action_records_for_debug(
    db: Session,
    *,
    session_id: str,
    request_id: str,
) -> list[dict]:
    return [
        {
            "id": row.id,
            "intent": row.intent,
            "action_name": row.action_name,
            "policy_mode": row.policy_mode,
            "status": row.status,
            "title": row.title,
        }
        for row in repository.list_action_records_by_request(db, session_id=session_id, request_id=request_id)
    ]


def _run_proposal_pipeline_for_turn(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    result: ConversationOrchestratorResult,
    actor: ActorContext,
) -> ProposalPipelineResult | None:
    if result.intent not in {ConversationIntent.FREE_CHAT, ConversationIntent.STRUCTURED_QA}:
        return None
    if not (settings.conversation_proposal_shadow_enabled or settings.conversation_proposal_write_enabled):
        return None

    turn_context = build_turn_proposal_context(
        db=db,
        session=session,
        request_id=request_id,
        authenticated_actor=_to_authenticated_actor(actor),
        user_message=user_message,
        assistant_message=assistant_message,
        conversation_history_excerpt=_build_recent_conversation_history(
            db,
            session_id=session.id,
            current_request_id=request_id,
        ),
        lane_result=result.lane_selection.to_payload() if result.lane_selection is not None else {},
        main_reply_summary=result.text[:300],
    )
    try:
        pipeline_result = ProposalPipeline().run(
            db,
            session=session,
            request_id=request_id,
            turn_context=turn_context,
            persist=settings.conversation_proposal_write_enabled,
        )
    except Exception as exc:
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="proposal.pipeline.failed",
            source="proposal",
            level="error",
            message="统一提案分析失败，但主回复保持不受影响。",
            payload={"error_message": str(exc)},
        )
        return None

    _append_debug_log(
        db,
        session=session,
        request_id=request_id,
        stage="proposal.pipeline.completed",
        source="proposal",
        message="统一提案分析完成。",
        payload={
            "batch_id": pipeline_result.batch_id,
            "draft_count": len(pipeline_result.drafts),
            "failure_count": len(pipeline_result.failures),
            "proposal_kinds": [item.proposal_kind for item in pipeline_result.drafts],
            "write_enabled": settings.conversation_proposal_write_enabled,
            "analyzer_failures": [
                {
                    "analyzer_name": failure.analyzer_name,
                    "error_message": failure.error_message,
                }
                for failure in pipeline_result.failures
            ],
            "extraction_output": (
                pipeline_result.extraction_output.model_dump(mode="json")
                if pipeline_result.extraction_output is not None
                else None
            ),
        },
    )
    if pipeline_result.batch_id is not None:
        _apply_policy_to_proposal_batch(
            db,
            session=session,
            batch_id=pipeline_result.batch_id,
            request_id=request_id,
            actor=actor,
        )
    return pipeline_result


def _build_legacy_policy_result_from_proposals(
    *,
    base_result: ConversationOrchestratorResult,
    proposal_result: ProposalPipelineResult,
) -> ConversationOrchestratorResult:
    return ConversationOrchestratorResult(
        intent=base_result.intent,
        text=base_result.text,
        degraded=base_result.degraded,
        facts=base_result.facts,
        suggestions=base_result.suggestions,
        memory_candidate_payloads=proposal_result.memory_candidate_payloads,
        config_suggestion=proposal_result.config_suggestion,
        action_payloads=proposal_result.action_payloads,
        ai_trace_id=base_result.ai_trace_id,
        ai_provider_code=base_result.ai_provider_code,
        effective_agent_id=base_result.effective_agent_id,
        effective_agent_name=base_result.effective_agent_name,
        intent_detection=base_result.intent_detection,
        lane_selection=base_result.lane_selection,
    )


def _result_has_actionable_proposals(result: ConversationOrchestratorResult) -> bool:
    return bool(result.memory_candidate_payloads or result.config_suggestion or result.action_payloads)


def _persist_legacy_result_as_proposal_batch(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    result: ConversationOrchestratorResult,
    actor: ActorContext,
) -> ProposalPipelineResult | None:
    drafts: list[ProposalDraft] = []
    for item in result.memory_candidate_payloads:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or item.get("content") or "").strip()
        title = str(item.get("title") or "").strip() or summary[:18]
        if not summary or not title:
            continue
        payload = dict(item)
        payload.setdefault("memory_type", payload.get("type") or "fact")
        drafts.append(
            ProposalDraft(
                proposal_kind="memory_write",
                policy_category="ask",
                title=title[:200],
                summary=summary,
                evidence_message_ids=[user_message.id],
                evidence_roles=["user"],
                dedupe_key=f"memory:{request_id}:{title[:30]}",
                confidence=float(item.get("confidence") or 0.75),
                payload=payload,
            )
        )
    if isinstance(result.config_suggestion, dict) and any(result.config_suggestion.values()):
        drafts.append(
            ProposalDraft(
                proposal_kind="config_apply",
                policy_category="ask",
                title="应用 Agent 配置建议",
                summary=_build_config_action_summary(result.config_suggestion),
                evidence_message_ids=[user_message.id],
                evidence_roles=["user"],
                dedupe_key=f"config:{request_id}",
                confidence=0.9,
                payload=dict(result.config_suggestion),
            )
        )
    for item in result.action_payloads:
        if not isinstance(item, dict):
            continue
        if str(item.get("action_type")) != "reminder_create":
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        payload = dict(item)
        drafts.append(
            ProposalDraft(
                proposal_kind="reminder_create",
                policy_category="ask",
                title=title[:200],
                summary=_build_reminder_action_summary(payload),
                evidence_message_ids=[user_message.id],
                evidence_roles=["user"],
                dedupe_key=f"reminder:{request_id}:{title[:30]}",
                confidence=float(item.get("confidence") or 0.9),
                payload=payload,
            )
        )
    if not drafts:
        return None
    turn_context = build_turn_proposal_context(
        db=db,
        session=session,
        request_id=request_id,
        authenticated_actor=_to_authenticated_actor(actor),
        user_message=user_message,
        assistant_message=assistant_message,
        conversation_history_excerpt=[],
        lane_result=result.lane_selection.to_payload() if result.lane_selection is not None else {},
        main_reply_summary=result.text[:300],
    )
    batch_id, item_ids = persist_proposal_batch(
        db,
        session=session,
        request_id=request_id,
        turn_context=turn_context,
        drafts=drafts,
    )
    _apply_policy_to_proposal_batch(
        db,
        session=session,
        batch_id=batch_id,
        request_id=request_id,
        actor=actor,
    )
    return ProposalPipelineResult(
        batch_id=batch_id,
        item_ids=item_ids,
        drafts=drafts,
        failures=[],
        extraction_output=None,
    )


def _apply_policy_to_proposal_batch(
    db: Session,
    *,
    session: ConversationSession,
    batch_id: str,
    request_id: str,
    actor: ActorContext,
) -> None:
    batch = repository.get_proposal_batch(db, batch_id)
    if batch is None:
        return
    policy = _resolve_autonomous_action_policy(db, session=session)
    items = list(repository.list_proposal_items(db, batch_id=batch_id))
    for item in items:
        policy_category = _resolve_proposal_policy_category(policy, proposal_kind=item.proposal_kind)
        item.policy_category = policy_category
        if policy_category == "ignore":
            item.status = "ignored"
            item.updated_at = utc_now_iso()
            continue
        if policy_category == "ask":
            item.status = "pending_confirmation"
            item.updated_at = utc_now_iso()
            continue
        try:
            affected_target_id = _execute_proposal_item(
                db,
                item=item,
                session=session,
                actor=actor,
            )
            item.status = "completed"
            item.updated_at = utc_now_iso()
            _append_debug_log(
                db,
                session=session,
                request_id=request_id,
                stage="proposal.item.executed",
                source="proposal",
                message="提案项已按策略自动执行。",
                payload={
                    "proposal_item_id": item.id,
                    "proposal_kind": item.proposal_kind,
                    "policy_category": policy_category,
                    "affected_target_id": affected_target_id,
                },
            )
        except HTTPException as exc:
            item.status = "failed"
            item.updated_at = utc_now_iso()
            _append_debug_log(
                db,
                session=session,
                request_id=request_id,
                stage="proposal.item.execution_failed",
                source="proposal",
                level="error",
                message="提案项自动执行失败。",
                payload={
                    "proposal_item_id": item.id,
                    "proposal_kind": item.proposal_kind,
                    "policy_category": policy_category,
                    "error_detail": exc.detail,
                },
            )
    _refresh_proposal_batch_status(db, batch_id=batch_id)
    db.flush()


def _resolve_proposal_policy_category(
    policy: AgentAutonomousActionPolicy,
    *,
    proposal_kind: str,
) -> str:
    action_category = _resolve_action_category_for_proposal_kind(proposal_kind)
    return _resolve_policy_mode(policy, action_category=action_category)


def _resolve_action_category_for_proposal_kind(proposal_kind: str) -> str:
    if proposal_kind == "memory_write":
        return "memory"
    if proposal_kind == "config_apply":
        return "config"
    return "action"


def _apply_config_proposal_item(
    db: Session,
    *,
    session: ConversationSession,
    payload: dict,
) -> str:
    if not session.active_agent_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active agent missing")
    agent = agent_repository.get_agent_by_household_and_id(db, household_id=session.household_id, agent_id=session.active_agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
    next_display_name = str(payload.get("display_name") or "").strip()
    if next_display_name and next_display_name != agent.display_name:
        update_agent(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentUpdate(display_name=next_display_name),
        )
    current_soul = agent_repository.get_active_soul_profile(db, agent_id=agent.id)
    has_soul_change = bool(payload.get("speaking_style")) or bool(payload.get("personality_traits"))
    if has_soul_change:
        speaking_style = str(payload.get("speaking_style") or "").strip() or (current_soul.speaking_style if current_soul is not None else None)
        personality_traits_raw = payload.get("personality_traits")
        personality_traits = [str(item).strip() for item in personality_traits_raw] if isinstance(personality_traits_raw, list) else []
        if not personality_traits and current_soul is not None:
            personality_traits = [str(item) for item in (load_json(current_soul.personality_traits_json) or [])]
        service_focus = [str(item) for item in (load_json(current_soul.service_focus_json) or [])] if current_soul is not None else []
        upsert_agent_soul(
            db,
            household_id=session.household_id,
            agent_id=agent.id,
            payload=AgentSoulProfileUpsert(
                self_identity=current_soul.self_identity if current_soul is not None else f"我是{next_display_name or agent.display_name}",
                role_summary=current_soul.role_summary if current_soul is not None else "负责家庭事务",
                intro_message=current_soul.intro_message if current_soul is not None else None,
                speaking_style=speaking_style,
                personality_traits=personality_traits,
                service_focus=service_focus,
                service_boundaries=load_json(current_soul.service_boundaries_json) if current_soul is not None else None,
                created_by="conversation-proposal",
            ),
        )
    return agent.id


def _apply_reminder_proposal_item(
    db: Session,
    *,
    session: ConversationSession,
    payload: dict,
) -> str:
    trigger_at = str(payload.get("trigger_at") or "").strip()
    title = str(payload.get("title") or "").strip()
    if not trigger_at or not title:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="reminder payload incomplete")
    task = create_reminder_task(
        db,
        ReminderTaskCreate(
            household_id=session.household_id,
            owner_member_id=session.requester_member_id,
            title=title,
            description=str(payload.get("description") or "").strip() or None,
            reminder_type="family",
            target_member_ids=[session.requester_member_id] if session.requester_member_id else [],
            preferred_room_ids=[],
            schedule_kind="once",
            schedule_rule={"trigger_at": trigger_at},
            priority="normal",
            delivery_channels=["in_app"],
            ack_required=False,
            escalation_policy={},
            enabled=True,
            updated_by="conversation-proposal",
        ),
    )
    return task.id


def _apply_scheduled_task_proposal_item(
    db: Session,
    *,
    payload: dict,
    actor: ActorContext,
) -> str:
    draft_id = str(payload.get("draft_id") or "").strip()
    if not draft_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="计划任务提案缺少草稿标识，暂时不能确认。")
    _, task_id = confirm_draft_from_conversation(
        db,
        actor=_to_authenticated_actor(actor),
        draft_id=draft_id,
        payload=ScheduledTaskDraftConfirmRequest(),
    )
    return task_id


def _apply_scheduled_task_operation_proposal_item(
    db: Session,
    *,
    proposal_kind: str,
    payload: dict,
    actor: ActorContext,
) -> str:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="计划任务操作提案缺少任务标识。")
    authenticated_actor = _to_authenticated_actor(actor)
    if proposal_kind == "scheduled_task_pause":
        set_task_enabled(db, actor=authenticated_actor, task_id=task_id, enabled=False)
        return task_id
    if proposal_kind == "scheduled_task_resume":
        set_task_enabled(db, actor=authenticated_actor, task_id=task_id, enabled=True)
        return task_id
    if proposal_kind == "scheduled_task_delete":
        delete_task_definition(db, actor=authenticated_actor, task_id=task_id)
        return task_id
    if proposal_kind == "scheduled_task_update":
        update_payload = payload.get("update_payload")
        if not isinstance(update_payload, dict) or not update_payload:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="计划任务更新提案缺少有效变更内容。")
        update_task_definition(
            db,
            actor=authenticated_actor,
            task_id=task_id,
            payload=ScheduledTaskDefinitionUpdate.model_validate(update_payload),
        )
        return task_id
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported scheduled task proposal kind")


def _to_authenticated_actor(actor: ActorContext) -> AuthenticatedActor:
    return AuthenticatedActor(
        account_id=actor.account_id or "",
        username=actor.username or "",
        account_type=actor.account_type,
        account_status=actor.account_status,
        household_id=actor.household_id,
        member_id=actor.member_id,
        member_role=actor.member_role,
        must_change_password=actor.must_change_password,
    )


def _count_request_memory_candidates(
    db: Session,
    *,
    session_id: str,
    request_id: str,
) -> int:
    source_message_ids = {
        row.id
        for row in repository.list_messages(db, session_id=session_id)
        if row.request_id == request_id and row.role == "assistant"
    }
    if not source_message_ids:
        return 0
    return sum(
        1
        for candidate in repository.list_memory_candidates(db, session_id=session_id)
        if candidate.source_message_id in source_message_ids
    )


def _refresh_proposal_batch_status(db: Session, *, batch_id: str) -> None:
    batch = repository.get_proposal_batch(db, batch_id)
    if batch is None:
        return
    items = list(repository.list_proposal_items(db, batch_id=batch_id))
    statuses = {item.status for item in items}
    if not items:
        batch.status = "ignored"
    elif statuses <= {"completed"}:
        batch.status = "completed"
    elif statuses <= {"dismissed", "ignored"}:
        batch.status = "ignored"
    elif "pending_confirmation" in statuses:
        batch.status = "pending_confirmation"
    elif "failed" in statuses and len(statuses) == 1:
        batch.status = "failed"
    else:
        batch.status = "partially_applied"
    batch.updated_at = utc_now_iso()


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
    if members:
        display_name_map = member_service.build_member_display_name_map(
            db,
            household_id=household_id,
            members=members,
            status_value="active",
        )
        lines: list[str] = []
        for member in members:
            display_name = display_name_map.get(member.id, member.name)
            lines.append(f"- {display_name} ({member.role})")
        return "\n".join(lines)
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
    _append_debug_log(
        db,
        session=session,
        request_id=request_id,
        stage="turn.received",
        source="service",
        message="收到新的实时聊天请求。",
        payload={
            "user_message_id": user_message_row.id,
            "assistant_message_id": assistant_message_row.id,
            "message": user_message.strip(),
            "channel": payload.channel,
            "session_mode": session.session_mode,
            "realtime": True,
        },
    )

    await _broadcast_conversation_event(
        db,
        connection_manager=connection_manager,
        household_id=session.household_id,
        session=session,
        event_type="user.message.accepted",
        request_id=request_id,
        payload={},
    )

    result: ConversationOrchestratorResult | None = None
    emitted_chunks: list[str] = []
    try:
        async for event_type, event_payload in stream_orchestrated_turn(
            db,
            session=session,
            message=user_message.strip(),
            actor=actor,
            conversation_history=_build_recent_conversation_history(
                db,
                session_id=session.id,
                current_request_id=request_id,
            ),
            request_context={
                "request_id": request_id,
                "trace_id": request_id,
                "session_id": session.id,
                "channel": "conversation_turn",
            },
        ):
            if event_type == "chunk":
                emitted_chunks.append(str(event_payload))
                await _broadcast_conversation_event(
                    db,
                    connection_manager=connection_manager,
                    household_id=session.household_id,
                    session=session,
                    event_type="agent.chunk",
                    request_id=request_id,
                    payload={"text": str(event_payload)},
                )
                continue
            result = cast(ConversationOrchestratorResult, event_payload)

        if result is None:
            raise RuntimeError("family_qa stream did not produce final result")

        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="orchestrator.completed",
            source="orchestrator",
            message="实时编排层已完成意图识别和主路由。",
            payload=_build_orchestrator_debug_payload(result),
        )
        _complete_assistant_message(
            db,
            session=session,
            assistant_message=assistant_message_row,
            result=result,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="assistant.completed",
            source="service",
            message="实时助手消息已落库。",
            payload={
                "assistant_message_id": assistant_message_row.id,
                "intent": result.intent.value,
                "content_preview": result.text[:120],
                "degraded": result.degraded,
            },
        )
        proposal_pipeline_result = _run_proposal_pipeline_for_turn(
            db,
            session=session,
            request_id=request_id,
            user_message=user_message_row,
            assistant_message=assistant_message_row,
            result=result,
            actor=actor,
        )
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="proposal.model.applied",
            source="proposal",
            message="本轮实时链路已直接切到新提案模型，不再写旧候选和旧动作记录。",
            payload={
                "proposal_batch_id": None if proposal_pipeline_result is None else proposal_pipeline_result.batch_id,
                "proposal_count": 0 if proposal_pipeline_result is None else len(proposal_pipeline_result.drafts),
            },
        )
        session.current_request_id = None
        session.updated_at = utc_now_iso()
        db.flush()
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.completed",
            source="service",
            message="本轮实时聊天处理完成。",
            payload={"outcome": "completed", "chunk_count": len(emitted_chunks)},
        )
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
        logger.exception(
            "实时会话处理失败 session_id=%s request_id=%s household_id=%s requester_member_id=%s error_code=%s partial_chunks=%s",
            session.id,
            request_id,
            session.household_id,
            session.requester_member_id or "-",
            _resolve_turn_error_code(exc),
            len(emitted_chunks),
        )
        partial_text = "".join(emitted_chunks).strip()
        if partial_text:
            assistant_message_row.content = partial_text
            assistant_message_row.status = "failed"
            assistant_message_row.message_type = "error"
            assistant_message_row.error_code = _resolve_turn_error_code(exc)
            assistant_message_row.updated_at = utc_now_iso()
            session.last_message_at = assistant_message_row.updated_at
            session.updated_at = assistant_message_row.updated_at
            db.flush()
        else:
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
        _append_debug_log(
            db,
            session=session,
            request_id=request_id,
            stage="turn.failed",
            source="service",
            level="error",
            message="本轮实时聊天处理失败。",
            payload={
                "error_message": _render_turn_error(exc),
                "error_code": _resolve_turn_error_code(exc),
                "partial_text": partial_text,
            },
        )
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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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
    proposal_batches = [_to_proposal_batch_read(db, item) for item in repository.list_proposal_batches(db, session_id=row.id)]
    return ConversationSessionDetailRead(
        **session_read.model_dump(mode="json"),
        messages=messages,
        proposal_batches=proposal_batches,
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


def _to_action_read(row: ConversationActionRecord) -> ConversationActionRecordRead:
    plan_payload = load_json(row.plan_payload_json) or {}
    result_payload = load_json(row.result_payload_json) or {}
    undo_payload = load_json(row.undo_payload_json) or {}
    return ConversationActionRecordRead(
        id=row.id,
        session_id=row.session_id,
        request_id=row.request_id,
        trigger_message_id=row.trigger_message_id,
        source_message_id=row.source_message_id,
        intent=row.intent,
        action_category=row.action_category,
        action_name=row.action_name,
        policy_mode=row.policy_mode,
        status=row.status,
        title=row.title,
        summary=row.summary,
        target_ref=row.target_ref,
        plan_payload=plan_payload if isinstance(plan_payload, dict) else {},
        result_payload=result_payload if isinstance(result_payload, dict) else {},
        undo_payload=undo_payload if isinstance(undo_payload, dict) else {},
        created_at=row.created_at,
        executed_at=row.executed_at,
        undone_at=row.undone_at,
        updated_at=row.updated_at,
    )


def _to_proposal_item_read(row: ConversationProposalItem) -> ConversationProposalItemRead:
    evidence_message_ids = load_json(row.evidence_message_ids_json) or []
    evidence_roles = load_json(row.evidence_roles_json) or []
    payload = load_json(row.payload_json) or {}
    return ConversationProposalItemRead(
        id=row.id,
        batch_id=row.batch_id,
        proposal_kind=row.proposal_kind,
        policy_category=cast(str, row.policy_category),
        status=cast(str, row.status),
        title=row.title,
        summary=row.summary,
        evidence_message_ids=[str(item) for item in evidence_message_ids] if isinstance(evidence_message_ids, list) else [],
        evidence_roles=[str(item) for item in evidence_roles] if isinstance(evidence_roles, list) else [],
        dedupe_key=row.dedupe_key,
        confidence=row.confidence,
        payload=payload if isinstance(payload, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_proposal_batch_read(db: Session, row: ConversationProposalBatch) -> ConversationProposalBatchRead:
    source_message_ids = load_json(row.source_message_ids_json) or []
    source_roles = load_json(row.source_roles_json) or []
    lane = load_json(row.lane_json) or {}
    items = [_to_proposal_item_read(item) for item in repository.list_proposal_items(db, batch_id=row.id)]
    return ConversationProposalBatchRead(
        id=row.id,
        session_id=row.session_id,
        request_id=row.request_id,
        source_message_ids=[str(item) for item in source_message_ids] if isinstance(source_message_ids, list) else [],
        source_roles=[str(item) for item in source_roles] if isinstance(source_roles, list) else [],
        lane=lane if isinstance(lane, dict) else {},
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        items=items,
    )


def _to_debug_log_read(row: ConversationDebugLog) -> ConversationDebugLogRead:
    payload = load_json(row.payload_json) or {}
    return ConversationDebugLogRead(
        id=row.id,
        session_id=row.session_id,
        request_id=row.request_id,
        stage=row.stage,
        source=row.source,
        level=row.level,
        message=row.message,
        payload=payload if isinstance(payload, dict) else {},
        created_at=row.created_at,
    )
