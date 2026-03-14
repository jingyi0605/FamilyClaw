"""create channel delivery tables

Revision ID: 20260314_0031
Revises: 20260314_0030
Create Date: 2026-03-14 21:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0031"
down_revision = "20260314_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_deliveries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("channel_account_id", sa.Text(), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("conversation_session_id", sa.Text(), nullable=True),
        sa.Column("assistant_message_id", sa.Text(), nullable=True),
        sa.Column("external_conversation_key", sa.String(length=255), nullable=False),
        sa.Column("delivery_type", sa.String(length=30), nullable=False),
        sa.Column("request_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("provider_message_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_account_id"], ["channel_plugin_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["conversation_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["conversation_messages.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_channel_deliveries_household_id", "channel_deliveries", ["household_id"], unique=False)
    op.create_index("idx_channel_deliveries_channel_account_id", "channel_deliveries", ["channel_account_id"], unique=False)
    op.create_index("idx_channel_deliveries_platform_code", "channel_deliveries", ["platform_code"], unique=False)
    op.create_index(
        "idx_channel_deliveries_conversation_session_id",
        "channel_deliveries",
        ["conversation_session_id"],
        unique=False,
    )
    op.create_index(
        "idx_channel_deliveries_assistant_message_id",
        "channel_deliveries",
        ["assistant_message_id"],
        unique=False,
    )
    op.create_index("idx_channel_deliveries_status", "channel_deliveries", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_channel_deliveries_status", table_name="channel_deliveries")
    op.drop_index("idx_channel_deliveries_assistant_message_id", table_name="channel_deliveries")
    op.drop_index("idx_channel_deliveries_conversation_session_id", table_name="channel_deliveries")
    op.drop_index("idx_channel_deliveries_platform_code", table_name="channel_deliveries")
    op.drop_index("idx_channel_deliveries_channel_account_id", table_name="channel_deliveries")
    op.drop_index("idx_channel_deliveries_household_id", table_name="channel_deliveries")
    op.drop_table("channel_deliveries")
