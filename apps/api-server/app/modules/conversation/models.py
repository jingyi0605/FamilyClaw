from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        Index("idx_conversation_sessions_household_last_message_at", "household_id", "last_message_at"),
        Index("idx_conversation_sessions_requester_status", "requester_member_id", "status"),
        Index("idx_conversation_sessions_active_agent_id", "active_agent_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    requester_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="family_chat")
    active_agent_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_message_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("idx_conversation_messages_session_seq", "session_id", "seq"),
        Index("idx_conversation_messages_request_id", "request_id"),
        Index("idx_conversation_messages_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(40), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    effective_agent_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_provider_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    degraded: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationMemoryCandidate(Base):
    __tablename__ = "conversation_memory_candidates"
    __table_args__ = (
        Index("idx_conversation_memory_candidates_session_status", "session_id", "status"),
        Index("idx_conversation_memory_candidates_source_message_id", "source_message_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    requester_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False, default="fact")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationActionRecord(Base):
    __tablename__ = "conversation_action_records"
    __table_args__ = (
        Index("idx_conversation_action_records_session_created_at", "session_id", "created_at"),
        Index("idx_conversation_action_records_source_message_id", "source_message_id"),
        Index("idx_conversation_action_records_target_ref", "target_ref"),
        Index("idx_conversation_action_records_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_message_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    action_category: Mapped[str] = mapped_column(String(20), nullable=False)
    action_name: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_confirmation")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    undo_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    executed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    undone_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationDebugLog(Base):
    __tablename__ = "conversation_debug_logs"
    __table_args__ = (
        Index("idx_conversation_debug_logs_session_created_at", "session_id", "created_at"),
        Index("idx_conversation_debug_logs_request_id", "request_id"),
        Index("idx_conversation_debug_logs_stage", "stage"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="service")
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationProposalBatch(Base):
    __tablename__ = "conversation_proposal_batches"
    __table_args__ = (
        Index("idx_conversation_proposal_batches_session_created_at", "session_id", "created_at"),
        Index("idx_conversation_proposal_batches_request_id", "request_id"),
        Index("idx_conversation_proposal_batches_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_roles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    lane_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_policy")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class ConversationProposalItem(Base):
    __tablename__ = "conversation_proposal_items"
    __table_args__ = (
        Index("idx_conversation_proposal_items_batch_created_at", "batch_id", "created_at"),
        Index("idx_conversation_proposal_items_kind_status", "proposal_kind", "status"),
        Index("idx_conversation_proposal_items_dedupe_key", "dedupe_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_proposal_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposal_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_category: Mapped[str] = mapped_column(String(20), nullable=False, default="ask")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_policy")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_message_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_roles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
