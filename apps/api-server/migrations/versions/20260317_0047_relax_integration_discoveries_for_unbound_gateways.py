"""relax integration discoveries for unbound gateways

Revision ID: 20260317_0047
Revises: 20260317_0046
Create Date: 2026-03-17 22:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0047"
down_revision = "20260317_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_discoveries", sa.Column("gateway_id", sa.String(length=100), nullable=True))
    op.execute(
        """
        UPDATE integration_discoveries
        SET gateway_id = COALESCE(
            NULLIF((payload::jsonb ->> 'gateway_id'), ''),
            NULLIF((metadata::jsonb ->> 'gateway_id'), '')
        )
        """
    )
    op.alter_column("integration_discoveries", "household_id", existing_type=sa.Text(), nullable=True)
    op.alter_column("integration_discoveries", "integration_instance_id", existing_type=sa.Text(), nullable=True)
    op.drop_constraint("uq_integration_discoveries_instance_key", "integration_discoveries", type_="unique")
    op.create_unique_constraint(
        "uq_integration_discoveries_plugin_key",
        "integration_discoveries",
        ["plugin_id", "discovery_key"],
    )
    op.create_index("ix_integration_discoveries_gateway_id", "integration_discoveries", ["gateway_id"], unique=False)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM integration_discoveries
        WHERE household_id IS NULL OR integration_instance_id IS NULL
        """
    )
    op.drop_index("ix_integration_discoveries_gateway_id", table_name="integration_discoveries")
    op.drop_constraint("uq_integration_discoveries_plugin_key", "integration_discoveries", type_="unique")
    op.create_unique_constraint(
        "uq_integration_discoveries_instance_key",
        "integration_discoveries",
        ["plugin_id", "integration_instance_id", "discovery_key"],
    )
    op.alter_column("integration_discoveries", "integration_instance_id", existing_type=sa.Text(), nullable=False)
    op.alter_column("integration_discoveries", "household_id", existing_type=sa.Text(), nullable=False)
    op.drop_column("integration_discoveries", "gateway_id")
