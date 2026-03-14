"""create conversation proposal tables

Revision ID: 20260314_0026
Revises: 20260314_0025
Create Date: 2026-03-14 20:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260314_0026"
down_revision: str = "20260314_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_proposal_batches",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("source_message_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("source_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("lane_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_policy"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_conversation_proposal_batches_session_created_at",
        "conversation_proposal_batches",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_proposal_batches_request_id",
        "conversation_proposal_batches",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_proposal_batches_status",
        "conversation_proposal_batches",
        ["status"],
        unique=False,
    )

    op.create_table(
        "conversation_proposal_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("proposal_kind", sa.String(length=40), nullable=False),
        sa.Column("policy_category", sa.String(length=20), nullable=False, server_default="ask"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_policy"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_message_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("evidence_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["conversation_proposal_batches.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_conversation_proposal_items_batch_created_at",
        "conversation_proposal_items",
        ["batch_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_proposal_items_kind_status",
        "conversation_proposal_items",
        ["proposal_kind", "status"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_proposal_items_dedupe_key",
        "conversation_proposal_items",
        ["dedupe_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conversation_proposal_items_dedupe_key", table_name="conversation_proposal_items")
    op.drop_index("idx_conversation_proposal_items_kind_status", table_name="conversation_proposal_items")
    op.drop_index("idx_conversation_proposal_items_batch_created_at", table_name="conversation_proposal_items")
    op.drop_table("conversation_proposal_items")

    op.drop_index("idx_conversation_proposal_batches_status", table_name="conversation_proposal_batches")
    op.drop_index("idx_conversation_proposal_batches_request_id", table_name="conversation_proposal_batches")
    op.drop_index(
        "idx_conversation_proposal_batches_session_created_at",
        table_name="conversation_proposal_batches",
    )
    op.drop_table("conversation_proposal_batches")
