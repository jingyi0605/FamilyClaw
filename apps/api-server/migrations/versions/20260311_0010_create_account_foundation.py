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

EXPECTED_TABLES: dict[str, set[str]] = {
    "accounts": {
        "id",
        "username",
        "password_hash",
        "account_type",
        "status",
        "household_id",
        "must_change_password",
        "created_at",
        "updated_at",
    },
    "account_member_bindings": {
        "account_id",
        "member_id",
        "household_id",
        "binding_status",
        "created_at",
        "updated_at",
    },
    "account_sessions": {
        "id",
        "account_id",
        "session_token_hash",
        "status",
        "expires_at",
        "last_seen_at",
        "created_at",
    },
}

EXPECTED_INDEXES: dict[str, set[str]] = {
    "accounts": {
        "idx_accounts_account_type",
        "idx_accounts_household_id",
        "idx_accounts_status",
    },
    "account_member_bindings": {
        "idx_account_member_bindings_household_id",
        "idx_account_member_bindings_status",
    },
    "account_sessions": {
        "idx_account_sessions_account_id",
        "idx_account_sessions_expires_at",
        "idx_account_sessions_status",
    },
}


def _validate_existing_account_schema(inspector: sa.Inspector) -> None:
    for table_name, expected_columns in EXPECTED_TABLES.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(expected_columns - actual_columns)
        if missing_columns:
            raise RuntimeError(
                f"Migration {revision} found existing table '{table_name}' but it is missing columns: "
                f"{', '.join(missing_columns)}. Check the schema manually and use 'alembic stamp {revision}' "
                "only after the table matches the migration."
            )

        actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        missing_indexes = sorted(EXPECTED_INDEXES[table_name] - actual_indexes)
        if missing_indexes:
            raise RuntimeError(
                f"Migration {revision} found existing table '{table_name}' but it is missing indexes: "
                f"{', '.join(missing_indexes)}. Check the schema manually and use 'alembic stamp {revision}' "
                "only after the table matches the migration."
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    present_tables = sorted(table_name for table_name in EXPECTED_TABLES if table_name in existing_tables)

    if present_tables:
        if len(present_tables) != len(EXPECTED_TABLES):
            missing_tables = sorted(set(EXPECTED_TABLES) - set(present_tables))
            raise RuntimeError(
                f"Migration {revision} found a partial account schema. Existing tables: {', '.join(present_tables)}; "
                f"missing tables: {', '.join(missing_tables)}. This database is in an inconsistent state. "
                "Check the schema manually, repair it, then use Alembic stamp/upgrade to continue."
            )

        _validate_existing_account_schema(inspector)
        return

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
