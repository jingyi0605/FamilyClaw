"""add device binding plugin route fields

Revision ID: 20260315_0034
Revises: 20260315_0033
Create Date: 2026-03-15 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0034"
down_revision: str = "20260315_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("device_bindings", sa.Column("plugin_id", sa.String(length=64), nullable=True))
    op.add_column(
        "device_bindings",
        sa.Column("binding_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_device_bindings_plugin_id", "device_bindings", ["plugin_id"], unique=False)

    op.execute(
        sa.text(
            """
            UPDATE device_bindings
            SET plugin_id = (
                SELECT CASE
                    WHEN devices.device_type = 'lock' THEN 'homeassistant-door-lock-action'
                    ELSE 'homeassistant-device-action'
                END
                FROM devices
                WHERE devices.id = device_bindings.device_id
            )
            WHERE platform = 'home_assistant'
              AND plugin_id IS NULL
            """
        )
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("device_bindings") as batch_op:
            batch_op.alter_column("binding_version", server_default=None)
    else:
        op.alter_column("device_bindings", "binding_version", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_device_bindings_plugin_id", table_name="device_bindings")
    op.drop_column("device_bindings", "binding_version")
    op.drop_column("device_bindings", "plugin_id")
