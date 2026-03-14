"""create channel conversation binding and event tables

Revision ID: 20260314_0030
Revises: 20260314_0029
Create Date: 2026-03-14 21:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0030"
down_revision = "20260314_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_conversation_bindings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("channel_account_id", sa.Text(), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("external_conversation_key", sa.String(length=255), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("conversation_session_id", sa.Text(), nullable=False),
        sa.Column("active_agent_id", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_account_id"], ["channel_plugin_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["active_agent_id"], ["family_agents.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "household_id",
            "channel_account_id",
            "external_conversation_key",
            name="uq_channel_conversation_bindings_household_account_external_conversation",
        ),
    )
    op.create_index(
        "idx_channel_conversation_bindings_household_id",
        "channel_conversation_bindings",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_channel_conversation_bindings_channel_account_id",
        "channel_conversation_bindings",
        ["channel_account_id"],
        unique=False,
    )
    op.create_index(
        "idx_channel_conversation_bindings_platform_code",
        "channel_conversation_bindings",
        ["platform_code"],
        unique=False,
    )
    op.create_index(
        "idx_channel_conversation_bindings_member_id",
        "channel_conversation_bindings",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        "idx_channel_conversation_bindings_status",
        "channel_conversation_bindings",
        ["status"],
        unique=False,
    )

    op.create_table(
        "channel_inbound_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("channel_account_id", sa.Text(), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("external_conversation_key", sa.String(length=255), nullable=True),
        sa.Column("normalized_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="received"),
        sa.Column("conversation_session_id", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("received_at", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_account_id"], ["channel_plugin_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["conversation_sessions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "household_id",
            "channel_account_id",
            "external_event_id",
            name="uq_channel_inbound_events_household_account_external_event",
        ),
    )
    op.create_index("idx_channel_inbound_events_household_id", "channel_inbound_events", ["household_id"], unique=False)
    op.create_index("idx_channel_inbound_events_channel_account_id", "channel_inbound_events", ["channel_account_id"], unique=False)
    op.create_index("idx_channel_inbound_events_platform_code", "channel_inbound_events", ["platform_code"], unique=False)
    op.create_index("idx_channel_inbound_events_event_type", "channel_inbound_events", ["event_type"], unique=False)
    op.create_index("idx_channel_inbound_events_status", "channel_inbound_events", ["status"], unique=False)
    op.create_index(
        "idx_channel_inbound_events_conversation_session_id",
        "channel_inbound_events",
        ["conversation_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_channel_inbound_events_conversation_session_id", table_name="channel_inbound_events")
    op.drop_index("idx_channel_inbound_events_status", table_name="channel_inbound_events")
    op.drop_index("idx_channel_inbound_events_event_type", table_name="channel_inbound_events")
    op.drop_index("idx_channel_inbound_events_platform_code", table_name="channel_inbound_events")
    op.drop_index("idx_channel_inbound_events_channel_account_id", table_name="channel_inbound_events")
    op.drop_index("idx_channel_inbound_events_household_id", table_name="channel_inbound_events")
    op.drop_table("channel_inbound_events")

    op.drop_index("idx_channel_conversation_bindings_status", table_name="channel_conversation_bindings")
    op.drop_index("idx_channel_conversation_bindings_member_id", table_name="channel_conversation_bindings")
    op.drop_index("idx_channel_conversation_bindings_platform_code", table_name="channel_conversation_bindings")
    op.drop_index("idx_channel_conversation_bindings_channel_account_id", table_name="channel_conversation_bindings")
    op.drop_index("idx_channel_conversation_bindings_household_id", table_name="channel_conversation_bindings")
    op.drop_table("channel_conversation_bindings")
