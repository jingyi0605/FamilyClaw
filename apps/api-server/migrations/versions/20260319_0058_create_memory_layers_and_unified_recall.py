"""create memory layers and unified recall documents

Revision ID: 20260319_0058
Revises: 20260319_0057
Create Date: 2026-03-19 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0058"
down_revision = "20260319_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episodic_memory_entries",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("subject_member_id", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default=sa.text("'family'")),
        sa.Column("importance", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("promotion_key", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "household_id",
            "source_kind",
            "source_id",
            name="uq_episodic_memory_entries_household_source",
        ),
    )
    op.create_index(
        "idx_episodic_memory_entries_household_status",
        "episodic_memory_entries",
        ["household_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_episodic_memory_entries_subject_status",
        "episodic_memory_entries",
        ["subject_member_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_episodic_memory_entries_promotion_key",
        "episodic_memory_entries",
        ["promotion_key"],
        unique=False,
    )
    op.create_index(
        "idx_episodic_memory_entries_occurred_at",
        "episodic_memory_entries",
        ["occurred_at"],
        unique=False,
    )
    op.alter_column("episodic_memory_entries", "content_json", server_default=None)
    op.alter_column("episodic_memory_entries", "visibility", server_default=None)
    op.alter_column("episodic_memory_entries", "importance", server_default=None)
    op.alter_column("episodic_memory_entries", "confidence", server_default=None)
    op.alter_column("episodic_memory_entries", "status", server_default=None)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default=sa.text("'family'")),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "source_kind",
            "source_ref",
            name="uq_knowledge_documents_household_source",
        ),
    )
    op.create_index(
        "idx_knowledge_documents_household_status",
        "knowledge_documents",
        ["household_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_knowledge_documents_source_kind",
        "knowledge_documents",
        ["source_kind"],
        unique=False,
    )
    op.create_index(
        "idx_knowledge_documents_visibility",
        "knowledge_documents",
        ["visibility"],
        unique=False,
    )
    op.alter_column("knowledge_documents", "visibility", server_default=None)
    op.alter_column("knowledge_documents", "status", server_default=None)

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

    op.create_table(
        "memory_recall_documents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("layer", sa.String(length=10), nullable=False),
        sa.Column("source_kind", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("subject_member_id", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("group_hint", sa.String(length=30), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.8")),
        sa.Column("occurred_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ready'")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "household_id",
            "layer",
            "source_kind",
            "source_id",
            name="uq_memory_recall_documents_household_source",
        ),
    )
    if vector_installed:
        op.execute("ALTER TABLE memory_recall_documents ADD COLUMN embedding vector(16)")
    else:
        op.add_column("memory_recall_documents", sa.Column("embedding", sa.Text(), nullable=True))

    op.create_index(
        "idx_memory_recall_documents_household_status",
        "memory_recall_documents",
        ["household_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_memory_recall_documents_layer_group",
        "memory_recall_documents",
        ["layer", "group_hint"],
        unique=False,
    )
    op.create_index(
        "idx_memory_recall_documents_subject_visibility",
        "memory_recall_documents",
        ["subject_member_id", "visibility"],
        unique=False,
    )
    op.create_index(
        "idx_memory_recall_documents_occurred_at",
        "memory_recall_documents",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_memory_recall_documents_search_tsv",
        "memory_recall_documents",
        ["search_tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.alter_column("memory_recall_documents", "importance", server_default=None)
    op.alter_column("memory_recall_documents", "confidence", server_default=None)
    op.alter_column("memory_recall_documents", "status", server_default=None)

    op.execute(
        """
        INSERT INTO memory_recall_documents (
            id,
            household_id,
            layer,
            source_kind,
            source_id,
            subject_member_id,
            visibility,
            group_hint,
            search_text,
            search_tsv,
            importance,
            confidence,
            occurred_at,
            updated_at,
            status,
            embedding
        )
        SELECT
            concat('recall:l1:', css.id),
            css.household_id,
            'L1',
            'conversation_session_summary',
            css.id,
            css.requester_member_id,
            'private',
            'session_summary',
            trim(
                regexp_replace(
                    concat_ws(
                        ' ',
                        coalesce(css.summary, ''),
                        coalesce(css.open_topics_json, ''),
                        coalesce(css.recent_confirmations_json, '')
                    ),
                    '\s+',
                    ' ',
                    'g'
                )
            ),
            CASE
                WHEN trim(
                    regexp_replace(
                        concat_ws(
                            ' ',
                            coalesce(css.summary, ''),
                            coalesce(css.open_topics_json, ''),
                            coalesce(css.recent_confirmations_json, '')
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
                                coalesce(css.summary, ''),
                                coalesce(css.open_topics_json, ''),
                                coalesce(css.recent_confirmations_json, '')
                            ),
                            '\s+',
                            ' ',
                            'g'
                        )
                    )
                )
            END,
            3,
            0.85,
            css.generated_at,
            css.updated_at,
            CASE
                WHEN css.status IN ('fresh', 'stale') THEN 'ready'
                ELSE 'stale'
            END,
            NULL
        FROM conversation_session_summaries css
        """
    )
    op.execute(
        """
        INSERT INTO memory_recall_documents (
            id,
            household_id,
            layer,
            source_kind,
            source_id,
            subject_member_id,
            visibility,
            group_hint,
            search_text,
            search_tsv,
            importance,
            confidence,
            occurred_at,
            updated_at,
            status,
            embedding
        )
        SELECT
            concat('recall:l3:', mc.id),
            mc.household_id,
            'L3',
            'memory_card',
            mc.id,
            mc.subject_member_id,
            mc.visibility,
            CASE
                WHEN mc.memory_type IN ('event', 'growth', 'observation') THEN 'recent_events'
                ELSE 'stable_facts'
            END,
            coalesce(mc.search_text, trim(regexp_replace(concat_ws(' ', mc.memory_type, mc.title, mc.summary, mc.normalized_text), '\s+', ' ', 'g'))),
            mc.search_tsv,
            mc.importance,
            mc.confidence,
            coalesce(mc.last_observed_at, mc.effective_at, mc.updated_at),
            mc.updated_at,
            CASE
                WHEN mc.status = 'active' THEN 'ready'
                ELSE 'stale'
            END,
            mc.embedding
        FROM memory_cards mc
        """
    )


def downgrade() -> None:
    op.drop_index("idx_memory_recall_documents_search_tsv", table_name="memory_recall_documents")
    op.drop_index("idx_memory_recall_documents_occurred_at", table_name="memory_recall_documents")
    op.drop_index("idx_memory_recall_documents_subject_visibility", table_name="memory_recall_documents")
    op.drop_index("idx_memory_recall_documents_layer_group", table_name="memory_recall_documents")
    op.drop_index("idx_memory_recall_documents_household_status", table_name="memory_recall_documents")
    op.drop_table("memory_recall_documents")

    op.drop_index("idx_knowledge_documents_visibility", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_source_kind", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_household_status", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("idx_episodic_memory_entries_occurred_at", table_name="episodic_memory_entries")
    op.drop_index("idx_episodic_memory_entries_promotion_key", table_name="episodic_memory_entries")
    op.drop_index("idx_episodic_memory_entries_subject_status", table_name="episodic_memory_entries")
    op.drop_index("idx_episodic_memory_entries_household_status", table_name="episodic_memory_entries")
    op.drop_table("episodic_memory_entries")
