"""add memory layer revision tables

Revision ID: 20260319_0059
Revises: 20260319_0058
Create Date: 2026-03-19 21:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260319_0059"
down_revision: str | Sequence[str] | None = "20260319_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "episodic_memory_entry_revisions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["episodic_memory_entries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id",
            "revision_no",
            name="uq_episodic_memory_entry_revisions_entry_revision",
        ),
    )
    op.create_index(
        "ix_episodic_memory_entry_revisions_entry_id",
        "episodic_memory_entry_revisions",
        ["entry_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_document_revisions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "revision_no",
            name="uq_knowledge_document_revisions_document_revision",
        ),
    )
    op.create_index(
        "ix_knowledge_document_revisions_document_id",
        "knowledge_document_revisions",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_document_revisions_document_id", table_name="knowledge_document_revisions")
    op.drop_table("knowledge_document_revisions")
    op.drop_index("ix_episodic_memory_entry_revisions_entry_id", table_name="episodic_memory_entry_revisions")
    op.drop_table("episodic_memory_entry_revisions")
