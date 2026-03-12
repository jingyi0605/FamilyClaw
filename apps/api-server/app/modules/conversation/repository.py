from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.conversation.models import (
    ConversationMemoryCandidate,
    ConversationMessage,
    ConversationSession,
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


def claim_next_event_seq(db: Session, *, session: ConversationSession) -> int:
    session.last_event_seq += 1
    db.flush()
    return session.last_event_seq
