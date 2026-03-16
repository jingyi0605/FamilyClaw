from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

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


def add_session(db: Session, row: ConversationSession) -> ConversationSession:
    db.add(row)
    return row


def get_session(db: Session, session_id: str) -> ConversationSession | None:
    return db.get(ConversationSession, session_id)


def list_sessions(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    limit: int = 50,
) -> Sequence[ConversationSession]:
    stmt: Select[tuple[ConversationSession]] = (
        select(ConversationSession)
        .where(ConversationSession.household_id == household_id)
        .order_by(ConversationSession.last_message_at.desc(), ConversationSession.created_at.desc())
        .limit(limit)
    )
    if requester_member_id is not None:
        stmt = stmt.where(ConversationSession.requester_member_id == requester_member_id)
    return list(db.scalars(stmt).all())


def add_message(db: Session, row: ConversationMessage) -> ConversationMessage:
    db.add(row)
    return row


def add_turn_source(db: Session, row: ConversationTurnSource) -> ConversationTurnSource:
    db.add(row)
    return row


def get_turn_source_by_turn_id(db: Session, *, conversation_turn_id: str) -> ConversationTurnSource | None:
    stmt: Select[tuple[ConversationTurnSource]] = select(ConversationTurnSource).where(
        ConversationTurnSource.conversation_turn_id == conversation_turn_id
    )
    return db.scalar(stmt)


def list_turn_sources(db: Session, *, session_id: str) -> Sequence[ConversationTurnSource]:
    stmt: Select[tuple[ConversationTurnSource]] = (
        select(ConversationTurnSource)
        .where(ConversationTurnSource.conversation_session_id == session_id)
        .order_by(ConversationTurnSource.created_at.asc(), ConversationTurnSource.id.asc())
    )
    return list(db.scalars(stmt).all())


def list_messages(db: Session, *, session_id: str) -> Sequence[ConversationMessage]:
    stmt: Select[tuple[ConversationMessage]] = (
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.seq.asc(), ConversationMessage.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def get_next_message_seq(db: Session, *, session_id: str) -> int:
    current = db.scalar(
        select(func.max(ConversationMessage.seq)).where(ConversationMessage.session_id == session_id)
    )
    return int(current or 0) + 1


def add_memory_candidate(db: Session, row: ConversationMemoryCandidate) -> ConversationMemoryCandidate:
    db.add(row)
    return row


def list_memory_candidates(
    db: Session,
    *,
    session_id: str,
    status: str | None = None,
) -> Sequence[ConversationMemoryCandidate]:
    stmt: Select[tuple[ConversationMemoryCandidate]] = (
        select(ConversationMemoryCandidate)
        .where(ConversationMemoryCandidate.session_id == session_id)
        .order_by(ConversationMemoryCandidate.created_at.asc(), ConversationMemoryCandidate.id.asc())
    )
    if status is not None:
        stmt = stmt.where(ConversationMemoryCandidate.status == status)
    return list(db.scalars(stmt).all())


def get_memory_candidate(db: Session, candidate_id: str) -> ConversationMemoryCandidate | None:
    return db.get(ConversationMemoryCandidate, candidate_id)


def add_action_record(db: Session, row: ConversationActionRecord) -> ConversationActionRecord:
    db.add(row)
    return row


def list_action_records(db: Session, *, session_id: str) -> Sequence[ConversationActionRecord]:
    stmt: Select[tuple[ConversationActionRecord]] = (
        select(ConversationActionRecord)
        .where(ConversationActionRecord.session_id == session_id)
        .order_by(ConversationActionRecord.created_at.asc(), ConversationActionRecord.id.asc())
    )
    return list(db.scalars(stmt).all())


def list_action_records_by_request(
    db: Session,
    *,
    session_id: str,
    request_id: str,
) -> Sequence[ConversationActionRecord]:
    stmt: Select[tuple[ConversationActionRecord]] = (
        select(ConversationActionRecord)
        .where(
            ConversationActionRecord.session_id == session_id,
            ConversationActionRecord.request_id == request_id,
        )
        .order_by(ConversationActionRecord.created_at.asc(), ConversationActionRecord.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_action_record(db: Session, action_id: str) -> ConversationActionRecord | None:
    return db.get(ConversationActionRecord, action_id)


def get_action_record_by_target_ref(
    db: Session,
    *,
    target_ref: str,
    action_name: str | None = None,
) -> ConversationActionRecord | None:
    stmt: Select[tuple[ConversationActionRecord]] = select(ConversationActionRecord).where(
        ConversationActionRecord.target_ref == target_ref
    )
    if action_name is not None:
        stmt = stmt.where(ConversationActionRecord.action_name == action_name)
    stmt = stmt.order_by(ConversationActionRecord.created_at.desc())
    return db.scalars(stmt).first()


def claim_next_event_seq(db: Session, *, session: ConversationSession) -> int:
    session.last_event_seq += 1
    db.flush()
    return session.last_event_seq


def add_debug_log(db: Session, row: ConversationDebugLog) -> ConversationDebugLog:
    db.add(row)
    return row


def list_debug_logs(
    db: Session,
    *,
    session_id: str,
    request_id: str | None = None,
    limit: int = 200,
) -> Sequence[ConversationDebugLog]:
    stmt: Select[tuple[ConversationDebugLog]] = (
        select(ConversationDebugLog)
        .where(ConversationDebugLog.session_id == session_id)
        .order_by(ConversationDebugLog.created_at.asc(), ConversationDebugLog.id.asc())
        .limit(limit)
    )
    if request_id is not None:
        stmt = stmt.where(ConversationDebugLog.request_id == request_id)
    return list(db.scalars(stmt).all())


def add_proposal_batch(db: Session, row: ConversationProposalBatch) -> ConversationProposalBatch:
    db.add(row)
    return row


def get_proposal_batch(db: Session, batch_id: str) -> ConversationProposalBatch | None:
    return db.get(ConversationProposalBatch, batch_id)


def get_proposal_batch_by_request(
    db: Session,
    *,
    session_id: str,
    request_id: str,
) -> ConversationProposalBatch | None:
    stmt: Select[tuple[ConversationProposalBatch]] = (
        select(ConversationProposalBatch)
        .where(
            ConversationProposalBatch.session_id == session_id,
            ConversationProposalBatch.request_id == request_id,
        )
        .order_by(ConversationProposalBatch.created_at.desc(), ConversationProposalBatch.id.desc())
    )
    return db.scalars(stmt).first()


def list_proposal_batches(
    db: Session,
    *,
    session_id: str,
    status: str | None = None,
) -> Sequence[ConversationProposalBatch]:
    stmt: Select[tuple[ConversationProposalBatch]] = (
        select(ConversationProposalBatch)
        .where(ConversationProposalBatch.session_id == session_id)
        .order_by(ConversationProposalBatch.created_at.asc(), ConversationProposalBatch.id.asc())
    )
    if status is not None:
        stmt = stmt.where(ConversationProposalBatch.status == status)
    return list(db.scalars(stmt).all())


def add_proposal_item(db: Session, row: ConversationProposalItem) -> ConversationProposalItem:
    db.add(row)
    return row


def get_proposal_item(db: Session, proposal_item_id: str) -> ConversationProposalItem | None:
    return db.get(ConversationProposalItem, proposal_item_id)


def list_proposal_items(
    db: Session,
    *,
    batch_id: str,
    status: str | None = None,
) -> Sequence[ConversationProposalItem]:
    stmt: Select[tuple[ConversationProposalItem]] = (
        select(ConversationProposalItem)
        .where(ConversationProposalItem.batch_id == batch_id)
        .order_by(ConversationProposalItem.created_at.asc(), ConversationProposalItem.id.asc())
    )
    if status is not None:
        stmt = stmt.where(ConversationProposalItem.status == status)
    return list(db.scalars(stmt).all())
