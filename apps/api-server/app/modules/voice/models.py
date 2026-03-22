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
