"""add plugin source to memory cards

Revision ID: 20260313_0018
Revises: 20260313_0017
Create Date: 2026-03-13 11:10:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0018"
down_revision: str = "20260313_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("memory_cards")}
    index_names = {index["name"] for index in inspector.get_indexes("memory_cards")}

    if "source_plugin_id" not in column_names:
        op.add_column("memory_cards", sa.Column("source_plugin_id", sa.String(length=64), nullable=True))
    if "source_raw_record_id" not in column_names:
        op.add_column("memory_cards", sa.Column("source_raw_record_id", sa.Text(), nullable=True))
    if "idx_memory_cards_source_plugin_id" not in index_names:
        op.create_index("idx_memory_cards_source_plugin_id", "memory_cards", ["source_plugin_id"], unique=False)
    if "idx_memory_cards_source_raw_record_id" not in index_names:
        op.create_index("idx_memory_cards_source_raw_record_id", "memory_cards", ["source_raw_record_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("memory_cards")}
    index_names = {index["name"] for index in inspector.get_indexes("memory_cards")}

    if "idx_memory_cards_source_raw_record_id" in index_names:
        op.drop_index("idx_memory_cards_source_raw_record_id", table_name="memory_cards")
    if "idx_memory_cards_source_plugin_id" in index_names:
        op.drop_index("idx_memory_cards_source_plugin_id", table_name="memory_cards")
    if "source_raw_record_id" in column_names:
        op.drop_column("memory_cards", "source_raw_record_id")
    if "source_plugin_id" in column_names:
        op.drop_column("memory_cards", "source_plugin_id")
