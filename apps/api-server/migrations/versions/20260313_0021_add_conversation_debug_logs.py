"""add conversation debug logs

Revision ID: 20260313_0021
Revises: 20260313_0020
Create Date: 2026-03-13 23:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0021"
down_revision: str = "20260313_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_debug_logs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="service"),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_conversation_debug_logs_session_created_at",
        "conversation_debug_logs",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_debug_logs_request_id",
        "conversation_debug_logs",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_debug_logs_stage",
        "conversation_debug_logs",
        ["stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conversation_debug_logs_stage", table_name="conversation_debug_logs")
    op.drop_index("idx_conversation_debug_logs_request_id", table_name="conversation_debug_logs")
    op.drop_index("idx_conversation_debug_logs_session_created_at", table_name="conversation_debug_logs")
    op.drop_table("conversation_debug_logs")
