"""reset ai config after capability refactor

Revision ID: 20260318_0055
Revises: 20260318_0054
Create Date: 2026-03-18 20:10:00
"""

from __future__ import annotations

from alembic import op


revision = "20260318_0055"
down_revision = "20260318_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 这次能力枚举是彻底切换，不保留旧配置兼容。
    # 直接清空旧 AI 配置与绑定，让数据和新模型能力定义保持一致。
    op.execute("DELETE FROM ai_capability_routes")
    op.execute("DELETE FROM ai_provider_profiles")
    op.execute("DELETE FROM ai_model_call_logs")
    op.execute("UPDATE family_agent_runtime_policies SET model_bindings_json = '[]'")
    op.execute("UPDATE family_agent_runtime_policies SET agent_skill_model_bindings_json = '[]'")


def downgrade() -> None:
    # 数据重置不可逆，不提供回滚。
    pass
