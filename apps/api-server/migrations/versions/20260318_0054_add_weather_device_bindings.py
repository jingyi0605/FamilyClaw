"""add weather device bindings

Revision ID: 20260318_0054
Revises: 20260318_0053
Create Date: 2026-03-18 18:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0054"
down_revision = "20260318_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weather_device_bindings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("binding_type", sa.String(length=32), nullable=False),
        sa.Column("binding_key", sa.String(length=255), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=True),
        sa.Column("region_code", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("latest_snapshot_json", sa.Text(), nullable=True),
        sa.Column("cache_expires_at", sa.Text(), nullable=True),
        sa.Column("last_refresh_attempt_at", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", name="uq_weather_device_bindings_device"),
        sa.UniqueConstraint("household_id", "binding_key", name="uq_weather_device_bindings_household_binding_key"),
    )
    op.create_index(op.f("ix_weather_device_bindings_device_id"), "weather_device_bindings", ["device_id"], unique=False)
    op.create_index(op.f("ix_weather_device_bindings_household_id"), "weather_device_bindings", ["household_id"], unique=False)
    op.create_index(op.f("ix_weather_device_bindings_plugin_id"), "weather_device_bindings", ["plugin_id"], unique=False)
    op.create_index(op.f("ix_weather_device_bindings_state"), "weather_device_bindings", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_weather_device_bindings_state"), table_name="weather_device_bindings")
    op.drop_index(op.f("ix_weather_device_bindings_plugin_id"), table_name="weather_device_bindings")
    op.drop_index(op.f("ix_weather_device_bindings_household_id"), table_name="weather_device_bindings")
    op.drop_index(op.f("ix_weather_device_bindings_device_id"), table_name="weather_device_bindings")
    op.drop_table("weather_device_bindings")
