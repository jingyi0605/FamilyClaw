"""create channel account and binding tables

Revision ID: 20260314_0029
Revises: 20260314_0028
Create Date: 2026-03-14 21:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0029"
down_revision = "20260314_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_plugin_accounts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("account_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("connection_mode", sa.String(length=32), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("last_probe_status", sa.String(length=20), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_inbound_at", sa.Text(), nullable=True),
        sa.Column("last_outbound_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("household_id", "account_code", name="uq_channel_plugin_accounts_household_account_code"),
    )
    op.create_index("idx_channel_plugin_accounts_household_id", "channel_plugin_accounts", ["household_id"], unique=False)
    op.create_index("idx_channel_plugin_accounts_plugin_id", "channel_plugin_accounts", ["plugin_id"], unique=False)
    op.create_index("idx_channel_plugin_accounts_platform_code", "channel_plugin_accounts", ["platform_code"], unique=False)
    op.create_index("idx_channel_plugin_accounts_status", "channel_plugin_accounts", ["status"], unique=False)

    op.create_table(
        "member_channel_bindings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("channel_account_id", sa.Text(), nullable=False),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("external_chat_id", sa.String(length=255), nullable=True),
        sa.Column("display_hint", sa.String(length=255), nullable=True),
        sa.Column("binding_status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_account_id"], ["channel_plugin_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "platform_code",
            "external_user_id",
            name="uq_member_channel_bindings_household_platform_external_user",
        ),
    )
    op.create_index("idx_member_channel_bindings_household_id", "member_channel_bindings", ["household_id"], unique=False)
    op.create_index("idx_member_channel_bindings_member_id", "member_channel_bindings", ["member_id"], unique=False)
    op.create_index("idx_member_channel_bindings_channel_account_id", "member_channel_bindings", ["channel_account_id"], unique=False)
    op.create_index("idx_member_channel_bindings_platform_code", "member_channel_bindings", ["platform_code"], unique=False)
    op.create_index("idx_member_channel_bindings_binding_status", "member_channel_bindings", ["binding_status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_member_channel_bindings_binding_status", table_name="member_channel_bindings")
    op.drop_index("idx_member_channel_bindings_platform_code", table_name="member_channel_bindings")
    op.drop_index("idx_member_channel_bindings_channel_account_id", table_name="member_channel_bindings")
    op.drop_index("idx_member_channel_bindings_member_id", table_name="member_channel_bindings")
    op.drop_index("idx_member_channel_bindings_household_id", table_name="member_channel_bindings")
    op.drop_table("member_channel_bindings")

    op.drop_index("idx_channel_plugin_accounts_status", table_name="channel_plugin_accounts")
    op.drop_index("idx_channel_plugin_accounts_platform_code", table_name="channel_plugin_accounts")
    op.drop_index("idx_channel_plugin_accounts_plugin_id", table_name="channel_plugin_accounts")
    op.drop_index("idx_channel_plugin_accounts_household_id", table_name="channel_plugin_accounts")
    op.drop_table("channel_plugin_accounts")
