"""add household setup status column

Revision ID: 20260311_0009
Revises: 20260310_0002
Create Date: 2026-03-11 20:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260311_0009"
down_revision: str = "20260310_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("households")}
    indexes = {index["name"] for index in inspector.get_indexes("households")}

    if "setup_status" not in columns:
        op.add_column("households", sa.Column("setup_status", sa.String(length=20), nullable=True))

    if "idx_households_setup_status" not in indexes:
        op.create_index("idx_households_setup_status", "households", ["setup_status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_households_setup_status", table_name="households")
    op.drop_column("households", "setup_status")
