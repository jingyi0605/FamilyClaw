"""create speaker runtime states

Revision ID: 20260322_0064
Revises: 20260321_0063
Create Date: 2026-03-22 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_0064"
down_revision = "20260321_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "speaker_runtime_states" in existing_tables:
        return

    op.create_table(
        "speaker_runtime_states",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("integration_instance_id", sa.Text(), nullable=False),
        sa.Column("adapter_code", sa.String(length=64), nullable=False),
        sa.Column("runtime_state", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_succeeded_at", sa.Text(), nullable=True),
        sa.Column("last_failed_at", sa.Text(), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_instance_id"], ["integration_instances.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "integration_instance_id",
            name="uq_speaker_runtime_states_integration_instance",
        ),
    )
    op.create_index(
        "idx_speaker_runtime_states_household_id",
        "speaker_runtime_states",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "idx_speaker_runtime_states_plugin_id",
        "speaker_runtime_states",
        ["plugin_id"],
        unique=False,
    )
    op.create_index(
        "idx_speaker_runtime_states_runtime_state",
        "speaker_runtime_states",
        ["runtime_state"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "speaker_runtime_states" not in existing_tables:
        return

    op.drop_index("idx_speaker_runtime_states_runtime_state", table_name="speaker_runtime_states")
    op.drop_index("idx_speaker_runtime_states_plugin_id", table_name="speaker_runtime_states")
    op.drop_index("idx_speaker_runtime_states_household_id", table_name="speaker_runtime_states")
    op.drop_table("speaker_runtime_states")
