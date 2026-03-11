"""给 ai provider 增加 api_family 字段

Revision ID: 20260311_0013
Revises: 20260311_0012
Create Date: 2026-03-11 23:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260311_0013"
down_revision = "20260311_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_profiles",
        sa.Column("api_family", sa.String(length=50), nullable=True),
    )

    op.execute(
        """
        UPDATE ai_provider_profiles
        SET api_family = CASE
            WHEN transport_type = 'native_sdk'
                 AND (
                    lower(coalesce(extra_config_json, '')) LIKE '%claude%'
                    OR lower(coalesce(base_url, '')) LIKE '%anthropic.com%'
                 )
                THEN 'anthropic_messages'
            WHEN transport_type = 'native_sdk'
                 AND (
                    lower(coalesce(extra_config_json, '')) LIKE '%gemini%'
                    OR lower(coalesce(base_url, '')) LIKE '%generativelanguage.googleapis.com%'
                 )
                THEN 'gemini_generate_content'
            ELSE 'openai_chat_completions'
        END
        WHERE api_family IS NULL
        """
    )

    with op.batch_alter_table("ai_provider_profiles") as batch_op:
        batch_op.alter_column(
            "api_family",
            existing_type=sa.String(length=50),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_provider_profiles") as batch_op:
        batch_op.drop_column("api_family")
