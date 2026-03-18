"""add region and household coordinates

Revision ID: 20260318_0053
Revises: 20260318_0052
Create Date: 2026-03-18 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0053"
down_revision = "20260318_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("region_nodes", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("region_nodes", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("region_nodes", sa.Column("coordinate_precision", sa.String(length=32), nullable=True))
    op.add_column("region_nodes", sa.Column("coordinate_source", sa.String(length=32), nullable=True))
    op.add_column("region_nodes", sa.Column("coordinate_updated_at", sa.Text(), nullable=True))

    op.add_column("households", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("households", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("households", sa.Column("coordinate_source", sa.String(length=32), nullable=True))
    op.add_column("households", sa.Column("coordinate_precision", sa.String(length=32), nullable=True))
    op.add_column("households", sa.Column("coordinate_updated_at", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("households", "coordinate_updated_at")
    op.drop_column("households", "coordinate_precision")
    op.drop_column("households", "coordinate_source")
    op.drop_column("households", "longitude")
    op.drop_column("households", "latitude")

    op.drop_column("region_nodes", "coordinate_updated_at")
    op.drop_column("region_nodes", "coordinate_source")
    op.drop_column("region_nodes", "coordinate_precision")
    op.drop_column("region_nodes", "longitude")
    op.drop_column("region_nodes", "latitude")
