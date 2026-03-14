"""add scheduler once constraints

Revision ID: 20260314_0032
Revises: 20260314_0031
Create Date: 2026-03-14 23:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260314_0032"
down_revision = "20260314_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scheduled_task_definitions", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_scheduled_task_definitions_schedule_type",
            "schedule_type IS NULL OR schedule_type IN ('daily', 'interval', 'cron', 'once')",
        )


def downgrade() -> None:
    with op.batch_alter_table("scheduled_task_definitions", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_scheduled_task_definitions_schedule_type", type_="check")
