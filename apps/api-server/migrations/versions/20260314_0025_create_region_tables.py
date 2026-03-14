"""create region tables

Revision ID: 20260314_0025
Revises: 20260314_0024
Create Date: 2026-03-14 16:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260314_0025"
down_revision: str = "20260314_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "region_nodes",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("country_code", sa.String(length=16), nullable=False),
        sa.Column("region_code", sa.String(length=32), nullable=False),
        sa.Column("parent_region_code", sa.String(length=32), nullable=True),
        sa.Column("admin_level", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("path_codes", sa.Text(), nullable=False),
        sa.Column("path_names", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("imported_at", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_code", "region_code", name="uq_region_nodes_provider_region_code"),
    )
    op.create_index("idx_region_nodes_provider_parent", "region_nodes", ["provider_code", "parent_region_code"], unique=False)
    op.create_index("idx_region_nodes_provider_level", "region_nodes", ["provider_code", "admin_level"], unique=False)

    op.create_table(
        "household_regions",
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("country_code", sa.String(length=16), nullable=False),
        sa.Column("region_code", sa.String(length=32), nullable=False),
        sa.Column("admin_level", sa.String(length=16), nullable=False),
        sa.Column("province_code", sa.String(length=32), nullable=False),
        sa.Column("province_name", sa.String(length=100), nullable=False),
        sa.Column("city_code", sa.String(length=32), nullable=False),
        sa.Column("city_name", sa.String(length=100), nullable=False),
        sa.Column("district_code", sa.String(length=32), nullable=False),
        sa.Column("district_name", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("household_id"),
    )
    op.create_index("idx_household_regions_provider_region", "household_regions", ["provider_code", "region_code"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_household_regions_provider_region", table_name="household_regions")
    op.drop_table("household_regions")
    op.drop_index("idx_region_nodes_provider_level", table_name="region_nodes")
    op.drop_index("idx_region_nodes_provider_parent", table_name="region_nodes")
    op.drop_table("region_nodes")
