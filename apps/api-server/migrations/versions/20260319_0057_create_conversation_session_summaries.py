"""create conversation session summaries and relax memory trace fk

Revision ID: 20260319_0057
Revises: 20260319_0056
Create Date: 2026-03-19 15:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0057"
down_revision = "20260319_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_session_summaries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("requester_member_id", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("open_topics_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recent_confirmations_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("covered_message_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'stale'")),
        sa.Column("generated_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("session_id", name="uq_conversation_session_summaries_session_id"),
    )
    op.create_index(
        "idx_conversation_session_summaries_household_status",
        "conversation_session_summaries",
        ["household_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_session_summaries_requester_status",
        "conversation_session_summaries",
        ["requester_member_id", "status"],
        unique=False,
    )
    op.alter_column("conversation_session_summaries", "summary", server_default=None)
    op.alter_column("conversation_session_summaries", "open_topics_json", server_default=None)
    op.alter_column("conversation_session_summaries", "recent_confirmations_json", server_default=None)
    op.alter_column("conversation_session_summaries", "covered_message_seq", server_default=None)
    op.alter_column("conversation_session_summaries", "status", server_default=None)

    op.drop_constraint("conversation_memory_reads_memory_id_fkey", "conversation_memory_reads", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "conversation_memory_reads_memory_id_fkey",
        "conversation_memory_reads",
        "memory_cards",
        ["memory_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index(
        "idx_conversation_session_summaries_requester_status",
        table_name="conversation_session_summaries",
    )
    op.drop_index(
        "idx_conversation_session_summaries_household_status",
        table_name="conversation_session_summaries",
    )
    op.drop_table("conversation_session_summaries")
