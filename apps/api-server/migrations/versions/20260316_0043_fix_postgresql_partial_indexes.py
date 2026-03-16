"""fix partial unique indexes for postgresql

Revision ID: 20260316_0043
Revises: 20260316_0042
Create Date: 2026-03-16 21:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20260316_0043"
down_revision = "20260316_0042"
branch_labels = None
depends_on = None

PARTIAL_UNIQUE_INDEXES: Sequence[tuple[str, str, list[str], str]] = (
    (
        "uq_ai_capability_routes_global_capability",
        "ai_capability_routes",
        ["capability"],
        "household_id IS NULL",
    ),
    (
        "uq_ai_capability_routes_household_capability",
        "ai_capability_routes",
        ["household_id", "capability"],
        "household_id IS NOT NULL",
    ),
    (
        "uq_family_agents_household_primary",
        "family_agents",
        ["household_id"],
        "is_primary = true",
    ),
    (
        "uq_family_agent_soul_profiles_agent_active",
        "family_agent_soul_profiles",
        ["agent_id"],
        "is_active = true",
    ),
)


def _create_partial_unique_index(name: str, table_name: str, columns: list[str], predicate: str) -> None:
    op.create_index(
        name,
        table_name,
        columns,
        unique=True,
        postgresql_where=sa.text(predicate),
    )


def upgrade() -> None:
    for name, table_name, columns, predicate in PARTIAL_UNIQUE_INDEXES:
        op.drop_index(name, table_name=table_name)
        _create_partial_unique_index(name, table_name, columns, predicate)


def downgrade() -> None:
    for name, table_name, columns, predicate in PARTIAL_UNIQUE_INDEXES:
        op.drop_index(name, table_name=table_name)
        op.create_index(name, table_name, columns, unique=True)
