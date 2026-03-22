from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class VoiceTerminalConversationBinding(Base):
    __tablename__ = "voice_terminal_conversation_bindings"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "terminal_type",
            "terminal_code",
            name="uq_voice_terminal_conversation_bindings_household_terminal",
        ),
        Index("idx_voice_terminal_conversation_bindings_household_id", "household_id"),
        Index("idx_voice_terminal_conversation_bindings_terminal_type", "terminal_type"),
        Index(
            "idx_voice_terminal_conv_bindings_session_id",
            "conversation_session_id",
        ),
        Index("idx_voice_terminal_conversation_bindings_binding_status", "binding_status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    terminal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    terminal_code: Mapped[str] = mapped_column(String(255), nullable=False)
    member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    binding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_command_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class SpeakerRuntimeState(Base):
    __tablename__ = "speaker_runtime_states"
    __table_args__ = (
        UniqueConstraint(
            "integration_instance_id",
            name="uq_speaker_runtime_states_integration_instance",
        ),
        Index("idx_speaker_runtime_states_household_id", "household_id"),
        Index("idx_speaker_runtime_states_plugin_id", "plugin_id"),
        Index("idx_speaker_runtime_states_runtime_state", "runtime_state"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_instance_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("integration_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    adapter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_state: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    consecutive_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    last_succeeded_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_failed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
