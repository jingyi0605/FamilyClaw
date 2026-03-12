"""create conversation foundation

Revision ID: 20260312_0016
Revises: 20260312_0015
Create Date: 2026-03-12 17:25:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260312_0016"
down_revision: str = "20260312_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("requester_member_id", sa.Text(), nullable=True),
        sa.Column("session_mode", sa.String(length=30), nullable=False, server_default="family_chat"),
        sa.Column("active_agent_id", sa.Text(), nullable=True),
        sa.Column("current_request_id", sa.Text(), nullable=True),
        sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=200), nullable=False, server_default="新对话"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_message_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["active_agent_id"], ["family_agents.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_conversation_sessions_household_last_message_at",
        "conversation_sessions",
        ["household_id", "last_message_at"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_sessions_requester_status",
        "conversation_sessions",
        ["requester_member_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_sessions_active_agent_id",
        "conversation_sessions",
        ["active_agent_id"],
        unique=False,
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("effective_agent_id", sa.Text(), nullable=True),
        sa.Column("ai_provider_code", sa.String(length=100), nullable=True),
        sa.Column("ai_trace_id", sa.String(length=100), nullable=True),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("facts_json", sa.Text(), nullable=True),
        sa.Column("suggestions_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["effective_agent_id"], ["family_agents.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_conversation_messages_session_seq",
        "conversation_messages",
        ["session_id", "seq"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_messages_request_id",
        "conversation_messages",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_messages_status",
        "conversation_messages",
        ["status"],
        unique=False,
    )

    op.create_table(
        "conversation_memory_candidates",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.Text(), nullable=True),
        sa.Column("requester_member_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_review"),
        sa.Column("memory_type", sa.String(length=30), nullable=False, server_default="fact"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_member_id"], ["members.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_conversation_memory_candidates_session_status",
        "conversation_memory_candidates",
        ["session_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_memory_candidates_source_message_id",
        "conversation_memory_candidates",
        ["source_message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_conversation_memory_candidates_source_message_id",
        table_name="conversation_memory_candidates",
    )
    op.drop_index(
        "idx_conversation_memory_candidates_session_status",
        table_name="conversation_memory_candidates",
    )
    op.drop_table("conversation_memory_candidates")

    op.drop_index(
        "idx_conversation_messages_status",
        table_name="conversation_messages",
    )
    op.drop_index(
        "idx_conversation_messages_request_id",
        table_name="conversation_messages",
    )
    op.drop_index(
        "idx_conversation_messages_session_seq",
        table_name="conversation_messages",
    )
    op.drop_table("conversation_messages")

    op.drop_index(
        "idx_conversation_sessions_active_agent_id",
        table_name="conversation_sessions",
    )
    op.drop_index(
        "idx_conversation_sessions_requester_status",
        table_name="conversation_sessions",
    )
    op.drop_index(
        "idx_conversation_sessions_household_last_message_at",
        table_name="conversation_sessions",
    )
    op.drop_table("conversation_sessions")
