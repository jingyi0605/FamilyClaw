"""add presence and context tables

Revision ID: 20260309_0002
Revises: 20260309_0001
Create Date: 2026-03-09 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260309_0002"
down_revision = "20260309_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "presence_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("room_id", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_presence_events_household_occurred_at",
        "presence_events",
        ["household_id", "occurred_at"],
        unique=False,
    )
    op.create_index("idx_presence_events_member_id", "presence_events", ["member_id"], unique=False)
    op.create_index(
        "idx_presence_events_source_type",
        "presence_events",
        ["source_type"],
        unique=False,
    )

    op.create_table(
        "member_presence_state",
        sa.Column("member_id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_room_id", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_summary", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_room_id"], ["rooms.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_member_presence_state_household_id",
        "member_presence_state",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_member_presence_state_status",
        "member_presence_state",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_member_presence_state_current_room_id",
        "member_presence_state",
        ["current_room_id"],
        unique=False,
    )

    op.create_table(
        "context_configs",
        sa.Column("household_id", sa.Text(), primary_key=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("context_configs")
    op.drop_index("idx_member_presence_state_current_room_id", table_name="member_presence_state")
    op.drop_index("idx_member_presence_state_status", table_name="member_presence_state")
    op.drop_index("idx_member_presence_state_household_id", table_name="member_presence_state")
    op.drop_table("member_presence_state")
    op.drop_index("idx_presence_events_source_type", table_name="presence_events")
    op.drop_index("idx_presence_events_member_id", table_name="presence_events")
    op.drop_index("idx_presence_events_household_occurred_at", table_name="presence_events")
    op.drop_table("presence_events")
