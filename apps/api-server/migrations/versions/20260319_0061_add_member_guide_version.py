"""add member guide version

Revision ID: 20260319_0061
Revises: 20260319_0060
Create Date: 2026-03-19 23:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0061"
down_revision = "20260319_0060"
branch_labels = None
depends_on = None

CHECK_NAME = "ck_member_preferences_user_app_guide_version_non_negative"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("member_preferences")}
    check_constraints = {constraint["name"] for constraint in inspector.get_check_constraints("member_preferences")}

    if "user_app_guide_version" not in columns:
        op.add_column("member_preferences", sa.Column("user_app_guide_version", sa.Integer(), nullable=True))

    if CHECK_NAME not in check_constraints:
        op.create_check_constraint(
            CHECK_NAME,
            "member_preferences",
            "user_app_guide_version IS NULL OR user_app_guide_version >= 1",
        )


def downgrade() -> None:
    op.drop_constraint(CHECK_NAME, "member_preferences", type_="check")
    op.drop_column("member_preferences", "user_app_guide_version")
