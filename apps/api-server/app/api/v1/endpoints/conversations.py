from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext, ensure_actor_can_access_household, require_bound_member_actor
from app.api.errors import translate_integrity_error
from app.db.session import get_db
from app.modules.audit.service import write_audit_log
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.schemas import (
    ConversationDebugLogListRead,
    ConversationProposalExecutionRead,
    ConversationSessionCreate,
    ConversationSessionDetailRead,
    ConversationSessionListResponse,
    ConversationTurnCreate,
    ConversationTurnRead,
)
from app.modules.conversation.service import (
    ConversationNotFoundError,
    acreate_conversation_turn,
    create_conversation_session,
    create_conversation_turn,
    delete_conversation_session,
    confirm_conversation_proposal,
    dismiss_conversation_proposal,
    get_conversation_session_detail,
    list_conversation_debug_logs,
    list_conversation_sessions,
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


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_session_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> Response:
    try:
        session = delete_conversation_session(db, session_id=session_id, actor=actor)
        write_audit_log(
            db,
            household_id=session.household_id,
            actor=actor,
            action="conversation.session.delete",
            target_type="conversation_session",
            target_id=session.id,
            result="success",
            details={
                "session_mode": session.session_mode,
                "title": session.title,
                "active_agent_id": session.active_agent_id,
            },
        )
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation session not found") from exc
    except HTTPException:
        db.rollback()
        raise


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
async def create_conversation_turn_endpoint(
    session_id: str,
    payload: ConversationTurnCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationTurnRead:
    try:
        result = await acreate_conversation_turn(db, session_id=session_id, payload=payload, actor=actor)
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


@router.post("/proposal-items/{proposal_item_id}/confirm", response_model=ConversationProposalExecutionRead)
def confirm_conversation_proposal_endpoint(
    proposal_item_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationProposalExecutionRead:
    result = confirm_conversation_proposal(db, proposal_item_id=proposal_item_id, actor=actor)
    batch = conversation_repository.get_proposal_batch(db, result.item.batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal batch not found")
    session_detail = get_conversation_session_detail(db, session_id=batch.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.proposal_item.confirm",
        target_type="conversation_proposal_item",
        target_id=result.item.id,
        result="success",
        details={"proposal_kind": result.item.proposal_kind, "affected_target_id": result.affected_target_id},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc


@router.post("/proposal-items/{proposal_item_id}/dismiss", response_model=ConversationProposalExecutionRead)
def dismiss_conversation_proposal_endpoint(
    proposal_item_id: str,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_bound_member_actor),
) -> ConversationProposalExecutionRead:
    result = dismiss_conversation_proposal(db, proposal_item_id=proposal_item_id, actor=actor)
    batch = conversation_repository.get_proposal_batch(db, result.item.batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation proposal batch not found")
    session_detail = get_conversation_session_detail(db, session_id=batch.session_id, actor=actor)
    write_audit_log(
        db,
        household_id=session_detail.household_id,
        actor=actor,
        action="conversation.proposal_item.dismiss",
        target_type="conversation_proposal_item",
        target_id=result.item.id,
        result="success",
        details={"proposal_kind": result.item.proposal_kind},
    )
    try:
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise translate_integrity_error(exc) from exc
