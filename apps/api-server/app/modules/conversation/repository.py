from collections.abc import Sequence

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.conversation.models import (
    ConversationActionRecord,
    ConversationDeviceControlShortcut,
    ConversationDebugLog,
    ConversationMemoryRead,
    ConversationMemoryCandidate,
    ConversationMessage,
    ConversationProposalBatch,
    ConversationProposalItem,
    ConversationSession,
    ConversationSessionSummary,
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


def add_session_summary(db: Session, row: ConversationSessionSummary) -> ConversationSessionSummary:
    db.add(row)
    return row


def get_session_summary(db: Session, *, session_id: str) -> ConversationSessionSummary | None:
    stmt: Select[tuple[ConversationSessionSummary]] = select(ConversationSessionSummary).where(
        ConversationSessionSummary.session_id == session_id
    )
    return db.scalar(stmt)


def list_session_summaries(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    status: str | None = None,
) -> Sequence[ConversationSessionSummary]:
    stmt: Select[tuple[ConversationSessionSummary]] = (
        select(ConversationSessionSummary)
        .where(ConversationSessionSummary.household_id == household_id)
        .order_by(ConversationSessionSummary.updated_at.desc(), ConversationSessionSummary.id.desc())
    )
    if requester_member_id is not None:
        stmt = stmt.where(ConversationSessionSummary.requester_member_id == requester_member_id)
    if status is not None:
        stmt = stmt.where(ConversationSessionSummary.status == status)
    return list(db.scalars(stmt).all())


def add_turn_source(db: Session, row: ConversationTurnSource) -> ConversationTurnSource:
    db.add(row)
    return row


def get_turn_source_by_turn_id(db: Session, *, conversation_turn_id: str) -> ConversationTurnSource | None:
    stmt: Select[tuple[ConversationTurnSource]] = select(ConversationTurnSource).where(
        ConversationTurnSource.conversation_turn_id == conversation_turn_id
    )
    return db.scalar(stmt)


def get_latest_turn_source_by_external_conversation_key(
    db: Session,
    *,
    household_id: str,
    source_kind: str,
    platform_code: str,
    external_conversation_key: str,
) -> ConversationTurnSource | None:
    stmt: Select[tuple[ConversationTurnSource]] = (
        select(ConversationTurnSource)
        .join(
            ConversationSession,
            ConversationSession.id == ConversationTurnSource.conversation_session_id,
        )
        .where(
            ConversationSession.household_id == household_id,
            ConversationTurnSource.source_kind == source_kind,
            ConversationTurnSource.platform_code == platform_code,
            ConversationTurnSource.external_conversation_key == external_conversation_key,
        )
        .order_by(ConversationTurnSource.created_at.desc(), ConversationTurnSource.id.desc())
    )
    return db.scalars(stmt).first()


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


def has_message_for_request(db: Session, *, session_id: str, request_id: str) -> bool:
    stmt = (
        select(ConversationMessage.id)
        .where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.request_id == request_id,
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


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


def add_memory_read(db: Session, row: ConversationMemoryRead) -> ConversationMemoryRead:
    db.add(row)
    return row


def list_memory_reads(
    db: Session,
    *,
    session_id: str,
    request_id: str | None = None,
) -> Sequence[ConversationMemoryRead]:
    stmt: Select[tuple[ConversationMemoryRead]] = (
        select(ConversationMemoryRead)
        .where(ConversationMemoryRead.session_id == session_id)
        .order_by(
            ConversationMemoryRead.created_at.asc(),
            ConversationMemoryRead.group_name.asc(),
            ConversationMemoryRead.rank.asc(),
            ConversationMemoryRead.id.asc(),
        )
    )
    if request_id is not None:
        stmt = stmt.where(ConversationMemoryRead.request_id == request_id)
    return list(db.scalars(stmt).all())


def add_device_control_shortcut(
    db: Session,
    row: ConversationDeviceControlShortcut,
) -> ConversationDeviceControlShortcut:
    db.add(row)
    return row


def list_device_control_shortcuts(
    db: Session,
    *,
    household_id: str,
    member_id: str | None = None,
    statuses: Sequence[str] | None = None,
) -> Sequence[ConversationDeviceControlShortcut]:
    stmt: Select[tuple[ConversationDeviceControlShortcut]] = (
        select(ConversationDeviceControlShortcut)
        .where(ConversationDeviceControlShortcut.household_id == household_id)
        .order_by(
            case((ConversationDeviceControlShortcut.member_id == member_id, 0), else_=1),
            ConversationDeviceControlShortcut.hit_count.desc(),
            ConversationDeviceControlShortcut.last_used_at.desc().nullslast(),
            ConversationDeviceControlShortcut.created_at.desc(),
        )
    )
    if member_id is not None:
        stmt = stmt.where(
            or_(
                ConversationDeviceControlShortcut.member_id == member_id,
                ConversationDeviceControlShortcut.member_id.is_(None),
            )
        )
    else:
        stmt = stmt.where(ConversationDeviceControlShortcut.member_id.is_(None))
    if statuses:
        stmt = stmt.where(ConversationDeviceControlShortcut.status.in_(list(statuses)))
    return list(db.scalars(stmt).all())


def list_device_control_shortcuts_by_phrase(
    db: Session,
    *,
    household_id: str,
    normalized_text: str,
    member_id: str | None = None,
    statuses: Sequence[str] | None = None,
) -> Sequence[ConversationDeviceControlShortcut]:
    stmt: Select[tuple[ConversationDeviceControlShortcut]] = (
        select(ConversationDeviceControlShortcut)
        .where(
            ConversationDeviceControlShortcut.household_id == household_id,
            ConversationDeviceControlShortcut.normalized_text == normalized_text,
        )
        .order_by(
            case((ConversationDeviceControlShortcut.member_id == member_id, 0), else_=1),
            ConversationDeviceControlShortcut.hit_count.desc(),
            ConversationDeviceControlShortcut.last_used_at.desc().nullslast(),
            ConversationDeviceControlShortcut.created_at.desc(),
        )
    )
    if member_id is not None:
        stmt = stmt.where(
            or_(
                ConversationDeviceControlShortcut.member_id == member_id,
                ConversationDeviceControlShortcut.member_id.is_(None),
            )
        )
    else:
        stmt = stmt.where(ConversationDeviceControlShortcut.member_id.is_(None))
    if statuses:
        stmt = stmt.where(ConversationDeviceControlShortcut.status.in_(list(statuses)))
    return list(db.scalars(stmt).all())


def find_device_control_shortcut_for_upsert(
    db: Session,
    *,
    household_id: str,
    member_id: str | None,
    normalized_text: str,
    device_id: str,
    entity_id: str,
    action: str,
) -> ConversationDeviceControlShortcut | None:
    stmt: Select[tuple[ConversationDeviceControlShortcut]] = (
        select(ConversationDeviceControlShortcut)
        .where(
            ConversationDeviceControlShortcut.household_id == household_id,
            ConversationDeviceControlShortcut.normalized_text == normalized_text,
            ConversationDeviceControlShortcut.device_id == device_id,
            ConversationDeviceControlShortcut.entity_id == entity_id,
            ConversationDeviceControlShortcut.action == action,
        )
        .order_by(ConversationDeviceControlShortcut.updated_at.desc())
    )
    if member_id is None:
        stmt = stmt.where(ConversationDeviceControlShortcut.member_id.is_(None))
    else:
        stmt = stmt.where(ConversationDeviceControlShortcut.member_id == member_id)
    return db.scalars(stmt).first()


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
