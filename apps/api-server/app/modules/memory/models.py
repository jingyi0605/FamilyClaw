from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class EventRecord(Base):
    __tablename__ = "event_records"
    __table_args__ = (
        UniqueConstraint("household_id", "dedupe_key", name="uq_event_records_household_dedupe_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    room_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    generate_memory_card: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    processed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class MemoryCard(Base):
    __tablename__ = "memory_cards"
    __table_args__ = (
        UniqueConstraint("household_id", "dedupe_key", name="uq_memory_cards_household_dedupe_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    projection_updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    subject_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_event_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("event_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_plugin_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_raw_record_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_observed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    invalidated_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class MemoryCardMember(Base):
    __tablename__ = "memory_card_members"

    memory_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("memory_cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    )
    relation_role: Mapped[str] = mapped_column(String(30), primary_key=True)


class MemoryCardRevision(Base):
    __tablename__ = "memory_card_revisions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    memory_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("memory_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class EpisodicMemoryEntry(Base):
    __tablename__ = "episodic_memory_entries"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "source_kind",
            "source_id",
            name="uq_episodic_memory_entries_household_source",
        ),
        Index("idx_episodic_memory_entries_household_status", "household_id", "status"),
        Index("idx_episodic_memory_entries_subject_status", "subject_member_id", "status"),
        Index("idx_episodic_memory_entries_promotion_key", "promotion_key"),
        Index("idx_episodic_memory_entries_occurred_at", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="family")
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    promotion_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class EpisodicMemoryEntryRevision(Base):
    __tablename__ = "episodic_memory_entry_revisions"
    __table_args__ = (
        UniqueConstraint("entry_id", "revision_no", name="uq_episodic_memory_entry_revisions_entry_revision"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    entry_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("episodic_memory_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "source_kind",
            "source_ref",
            name="uq_knowledge_documents_household_source",
        ),
        Index("idx_knowledge_documents_household_status", "household_id", "status"),
        Index("idx_knowledge_documents_source_kind", "source_kind"),
        Index("idx_knowledge_documents_visibility", "visibility"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, default="family")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class KnowledgeDocumentRevision(Base):
    __tablename__ = "knowledge_document_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "revision_no", name="uq_knowledge_document_revisions_document_revision"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class MemoryRecallDocument(Base):
    __tablename__ = "memory_recall_documents"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "layer",
            "source_kind",
            "source_id",
            name="uq_memory_recall_documents_household_source",
        ),
        Index("idx_memory_recall_documents_household_status", "household_id", "status"),
        Index("idx_memory_recall_documents_layer_group", "layer", "group_hint"),
        Index("idx_memory_recall_documents_subject_visibility", "subject_member_id", "visibility"),
        Index("idx_memory_recall_documents_occurred_at", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    layer: Mapped[str] = mapped_column(String(10), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    visibility: Mapped[str] = mapped_column(String(30), nullable=False)
    group_hint: Mapped[str] = mapped_column(String(30), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    occurred_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
