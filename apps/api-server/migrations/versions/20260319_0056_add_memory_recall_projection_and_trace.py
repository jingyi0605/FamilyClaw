"""add memory recall projection and conversation trace

Revision ID: 20260319_0056
Revises: 20260318_0055
Create Date: 2026-03-19 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0056"
down_revision = "20260318_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memory_cards", sa.Column("search_text", sa.Text(), nullable=True))
    op.add_column("memory_cards", sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True))
    op.add_column(
        "memory_cards",
        sa.Column("projection_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column("memory_cards", sa.Column("projection_updated_at", sa.Text(), nullable=True))

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = 'vector'
            ) THEN
                CREATE EXTENSION IF NOT EXISTS vector;
            END IF;
        END
        $$;
        """
    )

    bind = op.get_bind()
    vector_installed = bool(
        bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")).scalar()
    )
    if vector_installed:
        op.execute("ALTER TABLE memory_cards ADD COLUMN embedding vector(16)")
    else:
        op.add_column("memory_cards", sa.Column("embedding", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE memory_cards
        SET search_text = NULLIF(
                trim(
                    regexp_replace(
                        concat_ws(
                            ' ',
                            coalesce(memory_type, ''),
                            coalesce(title, ''),
                            coalesce(summary, ''),
                            coalesce(normalized_text, '')
                        ),
                        '\s+',
                        ' ',
                        'g'
                    )
                ),
                ''
            ),
            search_tsv = CASE
                WHEN trim(
                    regexp_replace(
                        concat_ws(
                            ' ',
                            coalesce(memory_type, ''),
                            coalesce(title, ''),
                            coalesce(summary, ''),
                            coalesce(normalized_text, '')
                        ),
                        '\s+',
                        ' ',
                        'g'
                    )
                ) = '' THEN NULL
                ELSE to_tsvector(
                    'simple',
                    trim(
                        regexp_replace(
                            concat_ws(
                                ' ',
                                coalesce(memory_type, ''),
                                coalesce(title, ''),
                                coalesce(summary, ''),
                                coalesce(normalized_text, '')
                            ),
                            '\s+',
                            ' ',
                            'g'
                        )
                    )
                )
            END,
            projection_version = 1,
            projection_updated_at = coalesce(updated_at, created_at)
        """
    )
    op.create_index(
        "idx_memory_cards_search_tsv",
        "memory_cards",
        ["search_tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.alter_column("memory_cards", "projection_version", server_default=None)

    op.create_table(
        "conversation_memory_reads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("group_name", sa.String(length=30), nullable=False),
        sa.Column("layer", sa.String(length=10), nullable=False, server_default=sa.text("'L3'")),
        sa.Column("memory_id", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False, server_default=sa.text("'memory_card'")),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rank", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reason_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["conversation_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_conversation_memory_reads_session_request",
        "conversation_memory_reads",
        ["session_id", "request_id"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_memory_reads_group_rank",
        "conversation_memory_reads",
        ["group_name", "rank"],
        unique=False,
    )
    op.create_index(
        "idx_conversation_memory_reads_memory_id",
        "conversation_memory_reads",
        ["memory_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conversation_memory_reads_memory_id", table_name="conversation_memory_reads")
    op.drop_index("idx_conversation_memory_reads_group_rank", table_name="conversation_memory_reads")
    op.drop_index("idx_conversation_memory_reads_session_request", table_name="conversation_memory_reads")
    op.drop_table("conversation_memory_reads")

    op.drop_index("idx_memory_cards_search_tsv", table_name="memory_cards")
    op.drop_column("memory_cards", "embedding")
    op.drop_column("memory_cards", "projection_updated_at")
    op.drop_column("memory_cards", "projection_version")
    op.drop_column("memory_cards", "search_tsv")
    op.drop_column("memory_cards", "search_text")
