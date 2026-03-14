"""add conversation action strategy

Revision ID: 20260313_0020
Revises: 20260313_0019
Create Date: 2026-03-13 21:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0020"
down_revision: str = "20260313_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("family_agent_runtime_policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "autonomous_action_policy_json",
                sa.Text(),
                nullable=False,
                server_default='{"memory":"ask","config":"ask","action":"ask"}',
            )
        )

    op.create_table(
        "conversation_action_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("trigger_message_id", sa.Text(), nullable=True),
        sa.Column("source_message_id", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(length=40), nullable=False),
        sa.Column("action_category", sa.String(length=20), nullable=False),
        sa.Column("action_name", sa.String(length=50), nullable=False),
        sa.Column("policy_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_confirmation"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("target_ref", sa.Text(), nullable=True),
        sa.Column("plan_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_payload_json", sa.Text(), nullable=True),
        sa.Column("undo_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("executed_at", sa.Text(), nullable=True),
        sa.Column("undone_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trigger_message_id"], ["conversation_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_message_id"], ["conversation_messages.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_conversation_action_records_session_created_at",
        "conversation_action_records",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_action_records_source_message_id",
        "conversation_action_records",
        ["source_message_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_action_records_target_ref",
        "conversation_action_records",
        ["target_ref"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_action_records_status",
        "conversation_action_records",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conversation_action_records_status", table_name="conversation_action_records")
    op.drop_index("idx_conversation_action_records_target_ref", table_name="conversation_action_records")
    op.drop_index("idx_conversation_action_records_source_message_id", table_name="conversation_action_records")
    op.drop_index("idx_conversation_action_records_session_created_at", table_name="conversation_action_records")
    op.drop_table("conversation_action_records")

    with op.batch_alter_table("family_agent_runtime_policies") as batch_op:
        batch_op.drop_column("autonomous_action_policy_json")
