"""create device control shortcuts

Revision ID: 20260317_0049
Revises: 20260317_0048
Create Date: 2026-03-17 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0049"
down_revision = "20260317_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_control_shortcuts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("resolution_source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_used_at", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_device_control_shortcuts_match_member",
        "device_control_shortcuts",
        ["household_id", "member_id", "normalized_text", "status"],
        unique=False,
    )
    op.create_index(
        "idx_device_control_shortcuts_match_household",
        "device_control_shortcuts",
        ["household_id", "normalized_text", "status"],
        unique=False,
    )
    op.create_index(
        "idx_device_control_shortcuts_device_id",
        "device_control_shortcuts",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_device_control_shortcuts_device_id", table_name="device_control_shortcuts")
    op.drop_index("idx_device_control_shortcuts_match_household", table_name="device_control_shortcuts")
    op.drop_index("idx_device_control_shortcuts_match_member", table_name="device_control_shortcuts")
    op.drop_table("device_control_shortcuts")
