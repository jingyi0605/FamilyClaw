"""create household foundation schema

Revision ID: 20260309_0001
Revises:
Create Date: 2026-03-09 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260309_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_households_status", "households", ["status"], unique=False)

    op.create_table(
        "members",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("age_group", sa.String(length=30), nullable=True),
        sa.Column("birthday", sa.String(length=10), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("guardian_member_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["guardian_member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_members_guardian_member_id", "members", ["guardian_member_id"], unique=False)
    op.create_index("idx_members_household_id", "members", ["household_id"], unique=False)
    op.create_index("idx_members_role", "members", ["role"], unique=False)

    op.create_table(
        "member_preferences",
        sa.Column("member_id", sa.Text(), primary_key=True),
        sa.Column("preferred_name", sa.String(length=100), nullable=True),
        sa.Column("light_preference", sa.Text(), nullable=True),
        sa.Column("climate_preference", sa.Text(), nullable=True),
        sa.Column("content_preference", sa.Text(), nullable=True),
        sa.Column("reminder_channel_preference", sa.Text(), nullable=True),
        sa.Column("sleep_schedule", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "member_relationships",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("source_member_id", sa.Text(), nullable=False),
        sa.Column("target_member_id", sa.Text(), nullable=False),
        sa.Column("relation_type", sa.String(length=30), nullable=False),
        sa.Column("visibility_scope", sa.String(length=30), nullable=False),
        sa.Column("delegation_scope", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_member_id"], ["members.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "source_member_id",
            "target_member_id",
            "relation_type",
            name="uq_member_relationships_source_target_type",
        ),
    )

    op.create_table(
        "member_permissions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_scope", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("effect", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_member_permissions_member_id", "member_permissions", ["member_id"], unique=False)

    op.create_table(
        "rooms",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("room_type", sa.String(length=30), nullable=False),
        sa.Column("privacy_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_rooms_household_id", "rooms", ["household_id"], unique=False)

    op.create_table(
        "devices",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("room_id", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("device_type", sa.String(length=30), nullable=False),
        sa.Column("vendor", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("controllable", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_devices_device_type", "devices", ["device_type"], unique=False)
    op.create_index("idx_devices_household_id", "devices", ["household_id"], unique=False)
    op.create_index("idx_devices_room_id", "devices", ["room_id"], unique=False)

    op.create_table(
        "device_bindings",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("external_entity_id", sa.String(length=255), nullable=False),
        sa.Column("external_device_id", sa.String(length=255), nullable=True),
        sa.Column("capabilities", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("platform", "external_entity_id", name="uq_device_bindings_platform_entity"),
    )
    op.create_index("idx_device_bindings_device_id", "device_bindings", ["device_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_audit_logs_household_id", "audit_logs", ["household_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_audit_logs_household_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_device_bindings_device_id", table_name="device_bindings")
    op.drop_table("device_bindings")

    op.drop_index("idx_devices_room_id", table_name="devices")
    op.drop_index("idx_devices_household_id", table_name="devices")
    op.drop_index("idx_devices_device_type", table_name="devices")
    op.drop_table("devices")

    op.drop_index("idx_rooms_household_id", table_name="rooms")
    op.drop_table("rooms")

    op.drop_index("idx_member_permissions_member_id", table_name="member_permissions")
    op.drop_table("member_permissions")

    op.drop_table("member_relationships")
    op.drop_table("member_preferences")

    op.drop_index("idx_members_role", table_name="members")
    op.drop_index("idx_members_household_id", table_name="members")
    op.drop_index("idx_members_guardian_member_id", table_name="members")
    op.drop_table("members")

    op.drop_index("idx_households_status", table_name="households")
    op.drop_table("households")

