"""refine channel binding uniqueness

Revision ID: 20260316_0038
Revises: 20260316_0037
Create Date: 2026-03-16 18:30:00
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0038"
down_revision = "20260316_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_member_channel_bindings_household_platform_external_user",
        "member_channel_bindings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_member_channel_bindings_household_account_external_user",
        "member_channel_bindings",
        ["household_id", "channel_account_id", "external_user_id"],
    )

    op.create_index(
        "idx_channel_inbound_events_account_status_error_received",
        "channel_inbound_events",
        ["channel_account_id", "status", "error_code", "received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_channel_inbound_events_account_status_error_received",
        table_name="channel_inbound_events",
    )

    op.drop_constraint(
        "uq_member_channel_bindings_household_account_external_user",
        "member_channel_bindings",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_member_channel_bindings_household_platform_external_user",
        "member_channel_bindings",
        ["household_id", "platform_code", "external_user_id"],
    )
