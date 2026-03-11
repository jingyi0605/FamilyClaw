"""create account foundation

Revision ID: 20260311_0010
Revises: 20260311_0009
Create Date: 2026-03-11 18:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0010"
down_revision: str = "20260311_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("username", name="uq_accounts_username"),
    )
    op.create_index("idx_accounts_account_type", "accounts", ["account_type"])
    op.create_index("idx_accounts_household_id", "accounts", ["household_id"])
    op.create_index("idx_accounts_status", "accounts", ["status"])

    op.create_table(
        "account_member_bindings",
        sa.Column("account_id", sa.Text(), primary_key=True),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("binding_status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("member_id", name="uq_account_member_bindings_member_id"),
    )
    op.create_index(
        "idx_account_member_bindings_household_id",
        "account_member_bindings",
        ["household_id"],
    )
    op.create_index(
        "idx_account_member_bindings_status",
        "account_member_bindings",
        ["binding_status"],
    )

    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("session_token_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_token_hash", name="uq_account_sessions_session_token_hash"),
    )
    op.create_index("idx_account_sessions_account_id", "account_sessions", ["account_id"])
    op.create_index("idx_account_sessions_expires_at", "account_sessions", ["expires_at"])
    op.create_index("idx_account_sessions_status", "account_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("idx_account_sessions_status", table_name="account_sessions")
    op.drop_index("idx_account_sessions_expires_at", table_name="account_sessions")
    op.drop_index("idx_account_sessions_account_id", table_name="account_sessions")
    op.drop_table("account_sessions")

    op.drop_index("idx_account_member_bindings_status", table_name="account_member_bindings")
    op.drop_index("idx_account_member_bindings_household_id", table_name="account_member_bindings")
    op.drop_table("account_member_bindings")

    op.drop_index("idx_accounts_status", table_name="accounts")
    op.drop_index("idx_accounts_household_id", table_name="accounts")
    op.drop_index("idx_accounts_account_type", table_name="accounts")
    op.drop_table("accounts")
