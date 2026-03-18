from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class FamilyAgent(Base):
    __tablename__ = "family_agents"
    __table_args__ = (
        Index("idx_family_agents_household_id", "household_id"),
        Index("idx_family_agents_agent_type", "agent_type"),
        Index("idx_family_agents_status", "status"),
        Index("uq_family_agents_household_code", "household_id", "code", unique=True),
        Index(
            "uq_family_agents_household_primary",
            "household_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class FamilyAgentSoulProfile(Base):
    __tablename__ = "family_agent_soul_profiles"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_family_agent_soul_profiles_agent_version"),
        Index("idx_family_agent_soul_profiles_agent_id", "agent_id"),
        Index("idx_family_agent_soul_profiles_is_active", "is_active"),
        Index(
            "uq_family_agent_soul_profiles_agent_active",
            "agent_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    self_identity: Mapped[str] = mapped_column(Text, nullable=False)
    role_summary: Mapped[str] = mapped_column(Text, nullable=False)
    intro_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaking_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality_traits_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    service_focus_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    service_boundaries_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class FamilyAgentMemberCognition(Base):
    __tablename__ = "family_agent_member_cognitions"
    __table_args__ = (
        UniqueConstraint("agent_id", "member_id", name="uq_family_agent_member_cognitions_agent_member"),
        Index("idx_family_agent_member_cognitions_agent_id", "agent_id"),
        Index("idx_family_agent_member_cognitions_member_id", "member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    closeness_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    service_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    communication_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    care_notes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class FamilyAgentRuntimePolicy(Base):
    __tablename__ = "family_agent_runtime_policies"

    agent_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    conversation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_entry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    routing_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    memory_scope_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    autonomous_action_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default='{"memory":"ask","config":"ask","action":"ask"}')
    model_bindings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    agent_skill_model_bindings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class FamilyAgentBootstrapSession(Base):
    __tablename__ = "family_agent_bootstrap_sessions"
    __table_args__ = (
        Index("idx_family_agent_bootstrap_sessions_household_id", "household_id"),
        Index("idx_family_agent_bootstrap_sessions_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collecting")
    pending_field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    draft_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    transcript_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    current_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class FamilyAgentBootstrapMessage(Base):
    __tablename__ = "family_agent_bootstrap_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_family_agent_bootstrap_messages_session_seq"),
        Index("idx_family_agent_bootstrap_messages_session_id", "session_id"),
        Index("idx_family_agent_bootstrap_messages_request_id", "request_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("family_agent_bootstrap_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)


class FamilyAgentBootstrapRequest(Base):
    __tablename__ = "family_agent_bootstrap_requests"
    __table_args__ = (
        Index("idx_family_agent_bootstrap_requests_session_id", "session_id"),
        Index("idx_family_agent_bootstrap_requests_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("family_agent_bootstrap_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    user_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)
