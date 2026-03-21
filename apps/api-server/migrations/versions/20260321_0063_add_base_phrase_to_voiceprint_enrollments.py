"""add base phrase to voiceprint enrollments

Revision ID: 20260321_0063
Revises: 20260320_0062
Create Date: 2026-03-21 12:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_0063"
down_revision = "20260320_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    enrollment_columns = {column["name"] for column in inspector.get_columns("voiceprint_enrollments")}

    if "base_phrase" not in enrollment_columns:
        op.add_column("voiceprint_enrollments", sa.Column("base_phrase", sa.Text(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE voiceprint_enrollments
            SET base_phrase = expected_phrase
            WHERE base_phrase IS NULL
              AND expected_phrase IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    enrollment_columns = {column["name"] for column in inspector.get_columns("voiceprint_enrollments")}
    if "base_phrase" in enrollment_columns:
        op.drop_column("voiceprint_enrollments", "base_phrase")
