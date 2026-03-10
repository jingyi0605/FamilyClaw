"""Add gender column to members table.

Revision ID: 20260310_0006
Revises: 20260310_0005_create_memory_foundation
Create Date: 2026-03-10 22:43:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260310_0006"
down_revision: str = "20260310_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("gender", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "gender")
