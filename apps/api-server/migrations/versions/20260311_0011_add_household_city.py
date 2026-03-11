"""add household city column

Revision ID: 20260311_0011
Revises: 20260311_0009
Create Date: 2026-03-11 21:05:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0011"
down_revision: str = "20260311_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("households")}

    if "city" not in columns:
        op.add_column("households", sa.Column("city", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("households", "city")
