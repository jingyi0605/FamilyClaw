"""add voice takeover settings to devices

Revision ID: 20260315_0035
Revises: 20260315_0034
Create Date: 2026-03-15 17:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260315_0035"
down_revision: str = "20260315_0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("voice_auto_takeover_enabled", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "devices",
        sa.Column("voice_takeover_prefixes", sa.Text(), nullable=False, server_default='["请"]'),
    )

    op.execute(
        sa.text(
            """
            UPDATE devices
            SET voice_auto_takeover_enabled = COALESCE(voice_auto_takeover_enabled, 0),
                voice_takeover_prefixes = COALESCE(voice_takeover_prefixes, '["请"]')
            """
        )
    )

    op.alter_column("devices", "voice_auto_takeover_enabled", server_default=None)
    op.alter_column("devices", "voice_takeover_prefixes", server_default=None)


def downgrade() -> None:
    op.drop_column("devices", "voice_takeover_prefixes")
    op.drop_column("devices", "voice_auto_takeover_enabled")
