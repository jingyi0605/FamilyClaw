"""merge account and household city heads

Revision ID: 20260311_0012
Revises: 20260311_0010, 20260311_0011
Create Date: 2026-03-11 21:40:00
"""

from __future__ import annotations

from typing import Sequence, Union


revision: str = "20260311_0012"
down_revision: Union[str, Sequence[str], None] = ("20260311_0010", "20260311_0011")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
