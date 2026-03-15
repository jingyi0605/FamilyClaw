"""add voiceprint identity enabled to devices

Revision ID: 20260316_0037
Revises: 20260315_0036
Create Date: 2026-03-16 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260316_0037"
down_revision: str = "20260315_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "devices",
        sa.Column("voiceprint_identity_enabled", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        sa.text(
            """
            UPDATE devices
            SET voiceprint_identity_enabled = COALESCE(voiceprint_identity_enabled, 0)
            """
        )
    )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("devices") as batch_op:
            batch_op.alter_column("voiceprint_identity_enabled", server_default=None)
    else:
        op.alter_column("devices", "voiceprint_identity_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("devices", "voiceprint_identity_enabled")
