from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class ChannelPluginAccount(Base):
    __tablename__ = "channel_plugin_accounts"
    __table_args__ = (
        UniqueConstraint("household_id", "account_code", name="uq_channel_plugin_accounts_household_account_code"),
        Index("idx_channel_plugin_accounts_household_id", "household_id"),
        Index("idx_channel_plugin_accounts_plugin_id", "plugin_id"),
        Index("idx_channel_plugin_accounts_platform_code", "platform_code"),
        Index("idx_channel_plugin_accounts_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    last_probe_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_inbound_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_outbound_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class MemberChannelBinding(Base):
    __tablename__ = "member_channel_bindings"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "channel_account_id",
            "external_user_id",
            name="uq_member_channel_bindings_household_account_external_user",
        ),
        Index("idx_member_channel_bindings_household_id", "household_id"),
        Index("idx_member_channel_bindings_member_id", "member_id"),
        Index("idx_member_channel_bindings_channel_account_id", "channel_account_id"),
        Index("idx_member_channel_bindings_platform_code", "platform_code"),
        Index("idx_member_channel_bindings_binding_status", "binding_status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("channel_plugin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    binding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class ChannelConversationBinding(Base):
    __tablename__ = "channel_conversation_bindings"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "channel_account_id",
            "external_conversation_key",
            name="uq_channel_conversation_bindings_household_account_external_conversation",
        ),
        Index("idx_channel_conversation_bindings_household_id", "household_id"),
        Index("idx_channel_conversation_bindings_channel_account_id", "channel_account_id"),
        Index("idx_channel_conversation_bindings_platform_code", "platform_code"),
        Index("idx_channel_conversation_bindings_member_id", "member_id"),
        Index("idx_channel_conversation_bindings_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("channel_plugin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    external_conversation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    active_agent_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("family_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_at: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class ChannelInboundEvent(Base):
    __tablename__ = "channel_inbound_events"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "channel_account_id",
            "external_event_id",
            name="uq_channel_inbound_events_household_account_external_event",
        ),
        Index("idx_channel_inbound_events_household_id", "household_id"),
        Index("idx_channel_inbound_events_channel_account_id", "channel_account_id"),
        Index("idx_channel_inbound_events_platform_code", "platform_code"),
        Index("idx_channel_inbound_events_event_type", "event_type"),
        Index("idx_channel_inbound_events_status", "status"),
        Index(
            "idx_channel_inbound_events_account_status_error_received",
            "channel_account_id",
            "status",
            "error_code",
            "received_at",
        ),
        Index("idx_channel_inbound_events_conversation_session_id", "conversation_session_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("channel_plugin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_conversation_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")
    conversation_session_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChannelDelivery(Base):
    __tablename__ = "channel_deliveries"
    __table_args__ = (
        Index("idx_channel_deliveries_household_id", "household_id"),
        Index("idx_channel_deliveries_channel_account_id", "channel_account_id"),
        Index("idx_channel_deliveries_platform_code", "platform_code"),
        Index("idx_channel_deliveries_conversation_session_id", "conversation_session_id"),
        Index("idx_channel_deliveries_assistant_message_id", "assistant_message_id"),
        Index("idx_channel_deliveries_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_account_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("channel_plugin_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_session_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_conversation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(30), nullable=False)
    request_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provider_message_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
