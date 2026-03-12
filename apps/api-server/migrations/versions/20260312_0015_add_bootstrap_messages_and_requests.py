"""add bootstrap messages and requests

Revision ID: 20260312_0015
Revises: 20260312_0014
Create Date: 2026-03-12 15:00:00
"""

from __future__ import annotations

import json
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260312_0015"
down_revision: str = "20260312_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "family_agent_bootstrap_sessions",
        sa.Column("current_request_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "family_agent_bootstrap_sessions",
        sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "family_agent_bootstrap_messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["family_agent_bootstrap_sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "seq", name="uq_family_agent_bootstrap_messages_session_seq"),
    )
    op.create_index(
        "idx_family_agent_bootstrap_messages_session_id",
        "family_agent_bootstrap_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "idx_family_agent_bootstrap_messages_request_id",
        "family_agent_bootstrap_messages",
        ["request_id"],
        unique=False,
    )

    op.create_table(
        "family_agent_bootstrap_requests",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("user_message_id", sa.Text(), nullable=False),
        sa.Column("assistant_message_id", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["family_agent_bootstrap_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_family_agent_bootstrap_requests_session_id",
        "family_agent_bootstrap_requests",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "idx_family_agent_bootstrap_requests_status",
        "family_agent_bootstrap_requests",
        ["status"],
        unique=False,
    )

    _backfill_bootstrap_messages()


def downgrade() -> None:
    op.drop_index(
        "idx_family_agent_bootstrap_requests_status",
        table_name="family_agent_bootstrap_requests",
    )
    op.drop_index(
        "idx_family_agent_bootstrap_requests_session_id",
        table_name="family_agent_bootstrap_requests",
    )
    op.drop_table("family_agent_bootstrap_requests")

    op.drop_index(
        "idx_family_agent_bootstrap_messages_request_id",
        table_name="family_agent_bootstrap_messages",
    )
    op.drop_index(
        "idx_family_agent_bootstrap_messages_session_id",
        table_name="family_agent_bootstrap_messages",
    )
    op.drop_table("family_agent_bootstrap_messages")

    op.drop_column("family_agent_bootstrap_sessions", "last_event_seq")
    op.drop_column("family_agent_bootstrap_sessions", "current_request_id")


def _backfill_bootstrap_messages() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, transcript_json, created_at, updated_at FROM family_agent_bootstrap_sessions"
        )
    ).mappings()

    insert_stmt = sa.text(
        """
        INSERT INTO family_agent_bootstrap_messages (
            id, session_id, request_id, role, content, seq, created_at
        ) VALUES (
            :id, :session_id, :request_id, :role, :content, :seq, :created_at
        )
        """
    )

    for row in rows:
        transcript_raw = row.get("transcript_json") or "[]"
        try:
            transcript = json.loads(transcript_raw)
        except json.JSONDecodeError:
            transcript = []

        if not isinstance(transcript, list):
            continue

        seq = 0
        for item in transcript:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "")
            if role not in {"assistant", "user", "system"} or not content:
                continue
            seq += 1
            bind.execute(
                insert_stmt,
                {
                    "id": str(uuid4()),
                    "session_id": row["id"],
                    "request_id": None,
                    "role": role,
                    "content": content,
                    "seq": seq,
                    "created_at": row.get("updated_at") or row.get("created_at"),
                },
            )
