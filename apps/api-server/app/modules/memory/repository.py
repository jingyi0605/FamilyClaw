from collections.abc import Sequence

from sqlalchemy import Select, bindparam, delete, func, select, text
from sqlalchemy.orm import Session

from app.modules.memory.models import (
    EpisodicMemoryEntryRevision,
    EpisodicMemoryEntry,
    EventRecord,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    MemoryCard,
    MemoryCardMember,
    MemoryCardRevision,
    MemoryRecallDocument,
)


def add_event_record(db: Session, row: EventRecord) -> EventRecord:
    db.add(row)
    return row


def get_event_record(db: Session, event_id: str) -> EventRecord | None:
    return db.get(EventRecord, event_id)


def get_event_record_by_dedupe_key(
    db: Session,
    *,
    household_id: str,
    dedupe_key: str,
) -> EventRecord | None:
    stmt = select(EventRecord).where(
        EventRecord.household_id == household_id,
        EventRecord.dedupe_key == dedupe_key,
    )
    return db.scalar(stmt)


def list_event_records(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    processing_status: str | None = None,
) -> tuple[list[EventRecord], int]:
    filters = [EventRecord.household_id == household_id]
    if processing_status is not None:
        filters.append(EventRecord.processing_status == processing_status)

    total = db.scalar(select(func.count()).select_from(EventRecord).where(*filters)) or 0
    stmt: Select[tuple[EventRecord]] = (
        select(EventRecord)
        .where(*filters)
        .order_by(EventRecord.occurred_at.desc(), EventRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).all()), total


def count_event_records_by_status(db: Session, *, household_id: str) -> dict[str, int]:
    stmt = (
        select(EventRecord.processing_status, func.count())
        .where(EventRecord.household_id == household_id)
        .group_by(EventRecord.processing_status)
    )
    return {status: count for status, count in db.execute(stmt).all()}


def get_latest_event_occurred_at(db: Session, *, household_id: str) -> str | None:
    stmt = select(EventRecord.occurred_at).where(EventRecord.household_id == household_id).order_by(
        EventRecord.occurred_at.desc(),
        EventRecord.id.desc(),
    )
    return db.scalar(stmt)


def add_memory_card(db: Session, row: MemoryCard) -> MemoryCard:
    db.add(row)
    return row


def get_memory_card(db: Session, memory_id: str) -> MemoryCard | None:
    return db.get(MemoryCard, memory_id)


def get_memory_card_by_dedupe_key(
    db: Session,
    *,
    household_id: str,
    dedupe_key: str,
) -> MemoryCard | None:
    stmt = select(MemoryCard).where(
        MemoryCard.household_id == household_id,
        MemoryCard.dedupe_key == dedupe_key,
    )
    return db.scalar(stmt)


def list_memory_cards(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    memory_type: str | None = None,
) -> tuple[list[MemoryCard], int]:
    filters = [MemoryCard.household_id == household_id]
    if memory_type is not None:
        filters.append(MemoryCard.memory_type == memory_type)

    total = db.scalar(select(func.count()).select_from(MemoryCard).where(*filters)) or 0
    stmt: Select[tuple[MemoryCard]] = (
        select(MemoryCard)
        .where(*filters)
        .order_by(MemoryCard.updated_at.desc(), MemoryCard.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).all()), total


def list_memory_cards_by_ids(db: Session, *, memory_ids: list[str]) -> Sequence[MemoryCard]:
    if not memory_ids:
        return []
    stmt: Select[tuple[MemoryCard]] = (
        select(MemoryCard)
        .where(MemoryCard.id.in_(memory_ids))
        .order_by(MemoryCard.updated_at.desc(), MemoryCard.id.desc())
    )
    return list(db.scalars(stmt).all())


def count_memory_cards_by_status(db: Session, *, household_id: str) -> dict[str, int]:
    stmt = (
        select(MemoryCard.status, func.count())
        .where(MemoryCard.household_id == household_id)
        .group_by(MemoryCard.status)
    )
    return {status: count for status, count in db.execute(stmt).all()}


def get_latest_memory_card_updated_at(db: Session, *, household_id: str) -> str | None:
    stmt = select(MemoryCard.updated_at).where(MemoryCard.household_id == household_id).order_by(
        MemoryCard.updated_at.desc(),
        MemoryCard.id.desc(),
    )
    return db.scalar(stmt)


def add_memory_card_member(db: Session, row: MemoryCardMember) -> MemoryCardMember:
    db.add(row)
    return row


def list_memory_card_members(db: Session, *, memory_ids: list[str]) -> Sequence[MemoryCardMember]:
    if not memory_ids:
        return []
    stmt: Select[tuple[MemoryCardMember]] = (
        select(MemoryCardMember)
        .where(MemoryCardMember.memory_id.in_(memory_ids))
        .order_by(
            MemoryCardMember.memory_id.asc(),
            MemoryCardMember.relation_role.asc(),
            MemoryCardMember.member_id.asc(),
        )
    )
    return list(db.scalars(stmt).all())


def replace_memory_card_members(
    db: Session,
    *,
    memory_id: str,
    links: list[MemoryCardMember],
) -> None:
    db.execute(delete(MemoryCardMember).where(MemoryCardMember.memory_id == memory_id))
    for link in links:
        db.add(link)


def add_memory_card_revision(db: Session, row: MemoryCardRevision) -> MemoryCardRevision:
    db.add(row)
    return row


def get_next_revision_no(db: Session, *, memory_id: str) -> int:
    stmt = select(func.max(MemoryCardRevision.revision_no)).where(MemoryCardRevision.memory_id == memory_id)
    current = db.scalar(stmt)
    return int(current or 0) + 1


def list_memory_card_revisions(db: Session, *, memory_id: str) -> Sequence[MemoryCardRevision]:
    stmt: Select[tuple[MemoryCardRevision]] = (
        select(MemoryCardRevision)
        .where(MemoryCardRevision.memory_id == memory_id)
        .order_by(MemoryCardRevision.revision_no.desc(), MemoryCardRevision.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_episodic_memory_entry(db: Session, row: EpisodicMemoryEntry) -> EpisodicMemoryEntry:
    db.add(row)
    return row


def get_episodic_memory_entry(db: Session, entry_id: str) -> EpisodicMemoryEntry | None:
    return db.get(EpisodicMemoryEntry, entry_id)


def get_episodic_memory_entry_by_source(
    db: Session,
    *,
    household_id: str,
    source_kind: str,
    source_id: str,
) -> EpisodicMemoryEntry | None:
    stmt = select(EpisodicMemoryEntry).where(
        EpisodicMemoryEntry.household_id == household_id,
        EpisodicMemoryEntry.source_kind == source_kind,
        EpisodicMemoryEntry.source_id == source_id,
    )
    return db.scalar(stmt)


def list_episodic_memory_entries_by_ids(
    db: Session,
    *,
    entry_ids: list[str],
) -> Sequence[EpisodicMemoryEntry]:
    if not entry_ids:
        return []
    stmt: Select[tuple[EpisodicMemoryEntry]] = (
        select(EpisodicMemoryEntry)
        .where(EpisodicMemoryEntry.id.in_(entry_ids))
        .order_by(EpisodicMemoryEntry.occurred_at.desc(), EpisodicMemoryEntry.id.desc())
    )
    return list(db.scalars(stmt).all())


def list_episodic_memory_entries_by_promotion_key(
    db: Session,
    *,
    household_id: str,
    promotion_key: str,
    statuses: list[str] | None = None,
    occurred_at_gte: str | None = None,
) -> Sequence[EpisodicMemoryEntry]:
    filters = [
        EpisodicMemoryEntry.household_id == household_id,
        EpisodicMemoryEntry.promotion_key == promotion_key,
    ]
    if statuses:
        filters.append(EpisodicMemoryEntry.status.in_(statuses))
    if occurred_at_gte is not None:
        filters.append(EpisodicMemoryEntry.occurred_at >= occurred_at_gte)
    stmt: Select[tuple[EpisodicMemoryEntry]] = (
        select(EpisodicMemoryEntry)
        .where(*filters)
        .order_by(EpisodicMemoryEntry.occurred_at.desc(), EpisodicMemoryEntry.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_episodic_memory_entry_revision(db: Session, row: EpisodicMemoryEntryRevision) -> EpisodicMemoryEntryRevision:
    db.add(row)
    return row


def get_next_episodic_memory_entry_revision_no(db: Session, *, entry_id: str) -> int:
    stmt = select(func.max(EpisodicMemoryEntryRevision.revision_no)).where(
        EpisodicMemoryEntryRevision.entry_id == entry_id
    )
    current = db.scalar(stmt)
    return int(current or 0) + 1


def list_episodic_memory_entry_revisions(
    db: Session,
    *,
    entry_id: str,
) -> Sequence[EpisodicMemoryEntryRevision]:
    stmt: Select[tuple[EpisodicMemoryEntryRevision]] = (
        select(EpisodicMemoryEntryRevision)
        .where(EpisodicMemoryEntryRevision.entry_id == entry_id)
        .order_by(EpisodicMemoryEntryRevision.revision_no.desc(), EpisodicMemoryEntryRevision.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_knowledge_document(db: Session, row: KnowledgeDocument) -> KnowledgeDocument:
    db.add(row)
    return row


def get_knowledge_document(db: Session, document_id: str) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)


def get_knowledge_document_by_source(
    db: Session,
    *,
    household_id: str,
    source_kind: str,
    source_ref: str,
) -> KnowledgeDocument | None:
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.household_id == household_id,
        KnowledgeDocument.source_kind == source_kind,
        KnowledgeDocument.source_ref == source_ref,
    )
    return db.scalar(stmt)


def list_knowledge_documents_by_ids(
    db: Session,
    *,
    document_ids: list[str],
) -> Sequence[KnowledgeDocument]:
    if not document_ids:
        return []
    stmt: Select[tuple[KnowledgeDocument]] = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.id.in_(document_ids))
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_knowledge_document_revision(db: Session, row: KnowledgeDocumentRevision) -> KnowledgeDocumentRevision:
    db.add(row)
    return row


def get_next_knowledge_document_revision_no(db: Session, *, document_id: str) -> int:
    stmt = select(func.max(KnowledgeDocumentRevision.revision_no)).where(
        KnowledgeDocumentRevision.document_id == document_id
    )
    current = db.scalar(stmt)
    return int(current or 0) + 1


def list_knowledge_document_revisions(
    db: Session,
    *,
    document_id: str,
) -> Sequence[KnowledgeDocumentRevision]:
    stmt: Select[tuple[KnowledgeDocumentRevision]] = (
        select(KnowledgeDocumentRevision)
        .where(KnowledgeDocumentRevision.document_id == document_id)
        .order_by(KnowledgeDocumentRevision.revision_no.desc(), KnowledgeDocumentRevision.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_memory_recall_document(db: Session, row: MemoryRecallDocument) -> MemoryRecallDocument:
    db.add(row)
    return row


def get_memory_recall_document(db: Session, recall_document_id: str) -> MemoryRecallDocument | None:
    return db.get(MemoryRecallDocument, recall_document_id)


def get_memory_recall_document_by_source(
    db: Session,
    *,
    household_id: str,
    layer: str,
    source_kind: str,
    source_id: str,
) -> MemoryRecallDocument | None:
    stmt = select(MemoryRecallDocument).where(
        MemoryRecallDocument.household_id == household_id,
        MemoryRecallDocument.layer == layer,
        MemoryRecallDocument.source_kind == source_kind,
        MemoryRecallDocument.source_id == source_id,
    )
    return db.scalar(stmt)


def list_memory_recall_documents_by_ids(
    db: Session,
    *,
    recall_document_ids: list[str],
) -> Sequence[MemoryRecallDocument]:
    if not recall_document_ids:
        return []
    stmt: Select[tuple[MemoryRecallDocument]] = (
        select(MemoryRecallDocument)
        .where(MemoryRecallDocument.id.in_(recall_document_ids))
        .order_by(MemoryRecallDocument.updated_at.desc(), MemoryRecallDocument.id.desc())
    )
    return list(db.scalars(stmt).all())


def is_pgvector_enabled(db: Session) -> bool:
    stmt = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'memory_cards'
              AND column_name = 'embedding'
              AND udt_name = 'vector'
        )
        """
    )
    return bool(db.execute(stmt).scalar())


def is_memory_recall_pgvector_enabled(db: Session) -> bool:
    stmt = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'memory_recall_documents'
              AND column_name = 'embedding'
              AND udt_name = 'vector'
        )
        """
    )
    return bool(db.execute(stmt).scalar())


def refresh_memory_card_projection(
    db: Session,
    *,
    memory_id: str,
    search_text: str | None,
    embedding_literal: str | None,
    projection_version: int,
    projection_updated_at: str,
) -> None:
    params = {
        "memory_id": memory_id,
        "search_text": search_text or "",
        "embedding_literal": embedding_literal,
        "projection_version": projection_version,
        "projection_updated_at": projection_updated_at,
    }
    if is_pgvector_enabled(db):
        stmt = text(
            """
            UPDATE memory_cards
            SET search_text = :search_text,
                search_tsv = CASE
                    WHEN :search_text = '' THEN NULL
                    ELSE to_tsvector('simple', :search_text)
                END,
                embedding = CASE
                    WHEN :embedding_literal IS NULL THEN NULL
                    ELSE CAST(:embedding_literal AS vector(16))
                END,
                projection_version = :projection_version,
                projection_updated_at = :projection_updated_at
            WHERE id = :memory_id
            """
        )
    else:
        stmt = text(
            """
            UPDATE memory_cards
            SET search_text = :search_text,
                search_tsv = CASE
                    WHEN :search_text = '' THEN NULL
                    ELSE to_tsvector('simple', :search_text)
                END,
                embedding = :embedding_literal,
                projection_version = :projection_version,
                projection_updated_at = :projection_updated_at
            WHERE id = :memory_id
            """
        ).bindparams(bindparam("embedding_literal"))
    db.execute(stmt, params)


def refresh_memory_recall_document_projection(
    db: Session,
    *,
    recall_document_id: str,
    search_text: str,
    embedding_literal: str | None,
) -> None:
    params = {
        "recall_document_id": recall_document_id,
        "search_text": search_text or "",
        "embedding_literal": embedding_literal,
    }
    if is_memory_recall_pgvector_enabled(db):
        stmt = text(
            """
            UPDATE memory_recall_documents
            SET search_text = :search_text,
                search_tsv = CASE
                    WHEN :search_text = '' THEN NULL
                    ELSE to_tsvector('simple', :search_text)
                END,
                embedding = CASE
                    WHEN :embedding_literal IS NULL THEN NULL
                    ELSE CAST(:embedding_literal AS vector(16))
                END
            WHERE id = :recall_document_id
            """
        )
    else:
        stmt = text(
            """
            UPDATE memory_recall_documents
            SET search_text = :search_text,
                search_tsv = CASE
                    WHEN :search_text = '' THEN NULL
                    ELSE to_tsvector('simple', :search_text)
                END,
                embedding = :embedding_literal
            WHERE id = :recall_document_id
            """
        ).bindparams(bindparam("embedding_literal"))
    db.execute(stmt, params)
