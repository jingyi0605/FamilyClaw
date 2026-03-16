"""create conversation turn sources and voice terminal bindings

Revision ID: 20260316_0041
Revises: 20260316_0040
Create Date: 2026-03-16 23:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0041"
down_revision = "20260316_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_turn_sources",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("conversation_session_id", sa.Text(), nullable=False),
        sa.Column("conversation_turn_id", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=True),
        sa.Column("channel_account_id", sa.Text(), nullable=True),
        sa.Column("voice_terminal_code", sa.String(length=255), nullable=True),
        sa.Column("external_conversation_key", sa.String(length=255), nullable=True),
        sa.Column("thread_key", sa.String(length=255), nullable=True),
        sa.Column("channel_inbound_event_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_account_id"], ["channel_plugin_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_inbound_event_id"], ["channel_inbound_events.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("conversation_turn_id", name="uq_conversation_turn_sources_turn_id"),
    )
    op.create_index(
        "idx_conversation_turn_sources_session_id",
        "conversation_turn_sources",
        ["conversation_session_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_turn_sources_source_kind",
        "conversation_turn_sources",
        ["source_kind"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_turn_sources_platform_code",
        "conversation_turn_sources",
        ["platform_code"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_turn_sources_channel_account_id",
        "conversation_turn_sources",
        ["channel_account_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_turn_sources_voice_terminal_code",
        "conversation_turn_sources",
        ["voice_terminal_code"],
        unique=False,
    )

    op.create_table(
        "voice_terminal_conversation_bindings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("terminal_type", sa.String(length=50), nullable=False),
        sa.Column("terminal_code", sa.String(length=255), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("conversation_session_id", sa.Text(), nullable=False),
        sa.Column("binding_status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_command_at", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "terminal_type",
            "terminal_code",
            name="uq_voice_terminal_conversation_bindings_household_terminal",
        ),
    )
    op.create_index(
        "idx_voice_terminal_conversation_bindings_household_id",
        "voice_terminal_conversation_bindings",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_voice_terminal_conversation_bindings_terminal_type",
        "voice_terminal_conversation_bindings",
        ["terminal_type"],
        unique=False,
    )
    op.create_index(
        "idx_voice_terminal_conversation_bindings_conversation_session_id",
        "voice_terminal_conversation_bindings",
        ["conversation_session_id"],
        unique=False,
    )
    op.create_index(
        "idx_voice_terminal_conversation_bindings_binding_status",
        "voice_terminal_conversation_bindings",
        ["binding_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_voice_terminal_conversation_bindings_binding_status",
        table_name="voice_terminal_conversation_bindings",
    )
    op.drop_index(
        "idx_voice_terminal_conversation_bindings_conversation_session_id",
        table_name="voice_terminal_conversation_bindings",
    )
    op.drop_index(
        "idx_voice_terminal_conversation_bindings_terminal_type",
        table_name="voice_terminal_conversation_bindings",
    )
    op.drop_index(
        "idx_voice_terminal_conversation_bindings_household_id",
        table_name="voice_terminal_conversation_bindings",
    )
    op.drop_table("voice_terminal_conversation_bindings")

    op.drop_index(
        "idx_conversation_turn_sources_voice_terminal_code",
        table_name="conversation_turn_sources",
    )
    op.drop_index(
        "idx_conversation_turn_sources_channel_account_id",
        table_name="conversation_turn_sources",
    )
    op.drop_index(
        "idx_conversation_turn_sources_platform_code",
        table_name="conversation_turn_sources",
    )
    op.drop_index(
        "idx_conversation_turn_sources_source_kind",
        table_name="conversation_turn_sources",
    )
    op.drop_index(
        "idx_conversation_turn_sources_session_id",
        table_name="conversation_turn_sources",
    )
    op.drop_table("conversation_turn_sources")
