"""create plugin dashboard tables

Revision ID: 20260316_0042
Revises: 20260316_0041
Create Date: 2026-03-16 23:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0042"
down_revision = "20260316_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_dashboard_card_snapshots",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("card_key", sa.String(length=64), nullable=False),
        sa.Column("placement", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "plugin_id",
            "placement",
            "card_key",
            name="uq_plugin_dashboard_card_snapshots_household_plugin_card",
        ),
    )
    op.create_index(
        "idx_plugin_dashboard_card_snapshots_household_id",
        "plugin_dashboard_card_snapshots",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_dashboard_card_snapshots_plugin_id",
        "plugin_dashboard_card_snapshots",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_dashboard_card_snapshots_card_key",
        "plugin_dashboard_card_snapshots",
        ["card_key"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_dashboard_card_snapshots_placement",
        "plugin_dashboard_card_snapshots",
        ["placement"],
        unique=False,
    )
    op.create_index(
        "idx_plugin_dashboard_card_snapshots_state",
        "plugin_dashboard_card_snapshots",
        ["state"],
        unique=False,
    )

    op.create_table(
        "member_dashboard_layouts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("placement", sa.String(length=32), nullable=False),
        sa.Column("layout_json", sa.Text(), nullable=False, server_default='{"items":[]}'),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "member_id",
            "placement",
            name="uq_member_dashboard_layouts_member_placement",
        ),
    )
    op.create_index(
        "idx_member_dashboard_layouts_member_id",
        "member_dashboard_layouts",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        "idx_member_dashboard_layouts_placement",
        "member_dashboard_layouts",
        ["placement"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_member_dashboard_layouts_placement", table_name="member_dashboard_layouts")
    op.drop_index("idx_member_dashboard_layouts_member_id", table_name="member_dashboard_layouts")
    op.drop_table("member_dashboard_layouts")

    op.drop_index(
        "idx_plugin_dashboard_card_snapshots_state",
        table_name="plugin_dashboard_card_snapshots",
    )
    op.drop_index(
        "idx_plugin_dashboard_card_snapshots_placement",
        table_name="plugin_dashboard_card_snapshots",
    )
    op.drop_index(
        "idx_plugin_dashboard_card_snapshots_card_key",
        table_name="plugin_dashboard_card_snapshots",
    )
    op.drop_index(
        "idx_plugin_dashboard_card_snapshots_plugin_id",
        table_name="plugin_dashboard_card_snapshots",
    )
    op.drop_index(
        "idx_plugin_dashboard_card_snapshots_household_id",
        table_name="plugin_dashboard_card_snapshots",
    )
    op.drop_table("plugin_dashboard_card_snapshots")
