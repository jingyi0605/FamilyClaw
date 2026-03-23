"""add plugin config auth sessions

Revision ID: 20260323_0064
Revises: 20260321_0063
Create Date: 2026-03-23 22:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_0064"
down_revision = "20260321_0063"
branch_labels = None
depends_on = None

TABLE_NAME = "plugin_config_auth_sessions"
INDEX_NAMES = (
    "ix_plugin_config_auth_sessions_household_id",
    "ix_plugin_config_auth_sessions_plugin_id",
    "ix_plugin_config_auth_sessions_scope_type",
    "ix_plugin_config_auth_sessions_scope_key",
    "ix_plugin_config_auth_sessions_action_key",
    "ix_plugin_config_auth_sessions_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if TABLE_NAME not in table_names:
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("household_id", sa.Text(), nullable=False),
            sa.Column("plugin_id", sa.String(length=64), nullable=False),
            sa.Column("scope_type", sa.String(length=32), nullable=False),
            sa.Column("scope_key", sa.String(length=100), nullable=False),
            sa.Column("action_key", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("callback_token", sa.String(length=128), nullable=False),
            sa.Column("state_token", sa.String(length=128), nullable=False),
            sa.Column("session_payload_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("callback_payload_json", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(length=100), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.Text(), nullable=False),
            sa.Column("callback_received_at", sa.Text(), nullable=True),
            sa.Column("finished_at", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("callback_token", name="uq_plugin_config_auth_sessions_callback_token"),
            sa.UniqueConstraint("state_token", name="uq_plugin_config_auth_sessions_state_token"),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)} if TABLE_NAME in table_names or TABLE_NAME in set(inspector.get_table_names()) else set()
    if INDEX_NAMES[0] not in existing_indexes:
        op.create_index(INDEX_NAMES[0], TABLE_NAME, ["household_id"], unique=False)
    if INDEX_NAMES[1] not in existing_indexes:
        op.create_index(INDEX_NAMES[1], TABLE_NAME, ["plugin_id"], unique=False)
    if INDEX_NAMES[2] not in existing_indexes:
        op.create_index(INDEX_NAMES[2], TABLE_NAME, ["scope_type"], unique=False)
    if INDEX_NAMES[3] not in existing_indexes:
        op.create_index(INDEX_NAMES[3], TABLE_NAME, ["scope_key"], unique=False)
    if INDEX_NAMES[4] not in existing_indexes:
        op.create_index(INDEX_NAMES[4], TABLE_NAME, ["action_key"], unique=False)
    if INDEX_NAMES[5] not in existing_indexes:
        op.create_index(INDEX_NAMES[5], TABLE_NAME, ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if TABLE_NAME not in table_names:
        return

    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    for index_name in INDEX_NAMES:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=TABLE_NAME)

    op.drop_table(TABLE_NAME)
