"""create memory foundation tables

Revision ID: 20260310_0005
Revises: 20260310_0004
Create Date: 2026-03-10 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260310_0005"
down_revision = "20260310_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("subject_member_id", sa.Text(), nullable=True),
        sa.Column("room_id", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=20), nullable=False),
        sa.Column("generate_memory_card", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("household_id", "dedupe_key", name="uq_event_records_household_dedupe_key"),
    )
    op.create_index(
        "idx_event_records_household_occurred_at",
        "event_records",
        ["household_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_event_records_processing_status",
        "event_records",
        ["processing_status"],
        unique=False,
    )
    op.create_index("idx_event_records_event_type", "event_records", ["event_type"], unique=False)
    op.create_index("idx_event_records_source_type", "event_records", ["source_type"], unique=False)
    op.create_index(
        "idx_event_records_subject_member_id",
        "event_records",
        ["subject_member_id"],
        unique=False,
    )
    op.create_index("idx_event_records_room_id", "event_records", ["room_id"], unique=False)

    op.create_table(
        "memory_cards",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("content_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("subject_member_id", sa.Text(), nullable=True),
        sa.Column("source_event_id", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.Text(), nullable=True),
        sa.Column("last_observed_at", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("invalidated_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_event_id"], ["event_records.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("household_id", "dedupe_key", name="uq_memory_cards_household_dedupe_key"),
    )
    op.create_index(
        "idx_memory_cards_household_updated_at",
        "memory_cards",
        ["household_id", "updated_at"],
        unique=False,
    )
    op.create_index("idx_memory_cards_memory_type", "memory_cards", ["memory_type"], unique=False)
    op.create_index("idx_memory_cards_status", "memory_cards", ["status"], unique=False)
    op.create_index("idx_memory_cards_visibility", "memory_cards", ["visibility"], unique=False)
    op.create_index(
        "idx_memory_cards_subject_member_id",
        "memory_cards",
        ["subject_member_id"],
        unique=False,
    )
    op.create_index("idx_memory_cards_source_event_id", "memory_cards", ["source_event_id"], unique=False)

    op.create_table(
        "memory_card_members",
        sa.Column("memory_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("relation_role", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("memory_id", "member_id", "relation_role"),
    )
    op.create_index(
        "idx_memory_card_members_member_id",
        "memory_card_members",
        ["member_id"],
        unique=False,
    )

    op.create_table(
        "memory_card_revisions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("memory_id", sa.Text(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_memory_card_revisions_memory_id_revision_no",
        "memory_card_revisions",
        ["memory_id", "revision_no"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_memory_card_revisions_memory_id_revision_no", table_name="memory_card_revisions")
    op.drop_table("memory_card_revisions")
    op.drop_index("idx_memory_card_members_member_id", table_name="memory_card_members")
    op.drop_table("memory_card_members")
    op.drop_index("idx_memory_cards_source_event_id", table_name="memory_cards")
    op.drop_index("idx_memory_cards_subject_member_id", table_name="memory_cards")
    op.drop_index("idx_memory_cards_visibility", table_name="memory_cards")
    op.drop_index("idx_memory_cards_status", table_name="memory_cards")
    op.drop_index("idx_memory_cards_memory_type", table_name="memory_cards")
    op.drop_index("idx_memory_cards_household_updated_at", table_name="memory_cards")
    op.drop_table("memory_cards")
    op.drop_index("idx_event_records_room_id", table_name="event_records")
    op.drop_index("idx_event_records_subject_member_id", table_name="event_records")
    op.drop_index("idx_event_records_source_type", table_name="event_records")
    op.drop_index("idx_event_records_event_type", table_name="event_records")
    op.drop_index("idx_event_records_processing_status", table_name="event_records")
    op.drop_index("idx_event_records_household_occurred_at", table_name="event_records")
    op.drop_table("event_records")
