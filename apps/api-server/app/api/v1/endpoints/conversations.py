from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.conversation.schemas import (
    ConversationActionExecutionRead,
    ConversationDebugLogListRead,
    ConversationMemoryCandidateActionRead,
    ConversationSessionCreate,
    ConversationSessionDetailRead,
    ConversationSessionListResponse,
    ConversationTurnCreate,
    ConversationTurnRead,
)
from app.modules.conversation.service import (
    ConversationNotFoundError,
    confirm_conversation_action,
    confirm_memory_candidate,
    create_conversation_session,
    create_conversation_turn,
    dismiss_conversation_action,
    dismiss_memory_candidate,
    get_conversation_session_detail,
    list_conversation_debug_logs,
    list_conversation_sessions,
    undo_conversation_action,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/sessions", response_model=ConversationSessionDetailRead, status_code=status.HTTP_201_CREATED)
def create_conversation_session_endpoint(
    payload: ConversationSessionCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationSessionDetailRead:
    ensure_actor_can_access_household(actor, payload.household_id)
    try:
        result = create_conversation_session(db, payload=payload, actor=actor)
        write_audit_log(
            db,
            household_id=payload.household_id,
            actor=actor,
            action="conversation.session.create",
            target_type="conversation_session",
            target_id=result.id,
            result="success",
            details={
                "session_mode": result.session_mode,
                "active_agent_id": result.active_agent_id,
            },
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.get("/sessions", response_model=ConversationSessionListResponse)
def list_conversation_sessions_endpoint(
    household_id: str,
    requester_member_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationSessionListResponse:
    ensure_actor_can_access_household(actor, household_id)
    return list_conversation_sessions(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        actor=actor,
        limit=limit,
    )


@router.get("/sessions/{session_id}", response_model=ConversationSessionDetailRead)
def get_conversation_session_detail_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationSessionDetailRead:
    try:
        result = get_conversation_session_detail(db, session_id=session_id, actor=actor)
        ensure_actor_can_access_household(actor, result.household_id)
        return result
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found") from exc


@router.get("/sessions/{session_id}/debug-logs", response_model=ConversationDebugLogListRead)
def list_conversation_debug_logs_endpoint(
    session_id: str,
    request_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationDebugLogListRead:
    try:
        return list_conversation_debug_logs(
            db,
            session_id=session_id,
            actor=actor,
            request_id=request_id,
            limit=limit,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found") from exc


@router.post("/sessions/{session_id}/turns", response_model=ConversationTurnRead)
def create_conversation_turn_endpoint(
    session_id: str,
    payload: ConversationTurnCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationTurnRead:
    try:
        result = create_conversation_turn(db, session_id=session_id, payload=payload, actor=actor)
        write_audit_log(
            db,
            household_id=result.session.household_id,
            actor=actor,
            action="conversation.turn.create",
            target_type="conversation_session",
            target_id=result.session_id,
            result=result.outcome,
            details={
                "request_id": result.request_id,
                "assistant_message_id": result.assistant_message_id,
                "agent_id": result.session.active_agent_id,
                "error_message": result.error_message,
            },
        )
        db.commit()
        return result
    except ConversationNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found") from exc
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/memory-candidates/{candidate_id}/confirm", response_model=ConversationMemoryCandidateActionRead)
def confirm_memory_candidate_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationMemoryCandidateActionRead:
    result = confirm_memory_candidate(db, candidate_id=candidate_id, actor=actor)
    session_detail = get_conversation_session_detail(db, session_id=result.candidate.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.memory_candidate.confirm",
        target_type="conversation_memory_candidate",
        target_id=result.candidate.id,
        result="success",
        details={"memory_card_id": result.memory_card_id},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/memory-candidates/{candidate_id}/dismiss", response_model=ConversationMemoryCandidateActionRead)
def dismiss_memory_candidate_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationMemoryCandidateActionRead:
    result = dismiss_memory_candidate(db, candidate_id=candidate_id, actor=actor)
    session_detail = get_conversation_session_detail(db, session_id=result.candidate.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.memory_candidate.dismiss",
        target_type="conversation_memory_candidate",
        target_id=result.candidate.id,
        result="success",
        details=None,
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/actions/{action_id}/confirm", response_model=ConversationActionExecutionRead)
def confirm_conversation_action_endpoint(
    action_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationActionExecutionRead:
    result = confirm_conversation_action(db, action_id=action_id, actor=actor)
    session_detail = get_conversation_session_detail(db, session_id=result.action.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.action.confirm",
        target_type="conversation_action",
        target_id=result.action.id,
        result=result.action.status,
        details={"action_name": result.action.action_name},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/actions/{action_id}/dismiss", response_model=ConversationActionExecutionRead)
def dismiss_conversation_action_endpoint(
    action_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationActionExecutionRead:
    result = dismiss_conversation_action(db, action_id=action_id, actor=actor)
    session_detail = get_conversation_session_detail(db, session_id=result.action.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.action.dismiss",
        target_type="conversation_action",
        target_id=result.action.id,
        result=result.action.status,
        details={"action_name": result.action.action_name},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/actions/{action_id}/undo", response_model=ConversationActionExecutionRead)
def undo_conversation_action_endpoint(
    action_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationActionExecutionRead:
    result = undo_conversation_action(db, action_id=action_id, actor=actor)
    session_detail = get_conversation_session_detail(db, session_id=result.action.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.action.undo",
        target_type="conversation_action",
        target_id=result.action.id,
        result=result.action.status,
        details={"action_name": result.action.action_name},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
