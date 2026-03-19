"""create device entities

Revision ID: 20260319_0060
Revises: 20260319_0059
Create Date: 2026-03-19 21:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0060"
down_revision = "20260319_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_entities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("binding_id", sa.Text(), nullable=False),
        sa.Column("integration_instance_id", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("state_display", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("control_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["binding_id"], ["device_bindings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_instance_id"], ["integration_instances.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "entity_id", name="uq_device_entities_device_entity"),
    )
    op.create_index(op.f("ix_device_entities_binding_id"), "device_entities", ["binding_id"], unique=False)
    op.create_index(op.f("ix_device_entities_device_id"), "device_entities", ["device_id"], unique=False)
    op.create_index(
        op.f("ix_device_entities_integration_instance_id"),
        "device_entities",
        ["integration_instance_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_device_entities_integration_instance_id"), table_name="device_entities")
    op.drop_index(op.f("ix_device_entities_device_id"), table_name="device_entities")
    op.drop_index(op.f("ix_device_entities_binding_id"), table_name="device_entities")
    op.drop_table("device_entities")
