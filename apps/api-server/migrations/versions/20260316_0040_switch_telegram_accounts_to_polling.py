"""switch telegram accounts to polling

Revision ID: 20260316_0040
Revises: 20260316_0039
Create Date: 2026-03-16 22:40:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260316_0040"
down_revision = "20260316_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE channel_plugin_accounts
            SET connection_mode = 'polling'
            WHERE plugin_id = 'channel-telegram'
            """
        )
    )

    rows = bind.execute(
        sa.text(
            """
            SELECT id, config_json
            FROM channel_plugin_accounts
            WHERE plugin_id = 'channel-telegram'
            """
        )
    ).fetchall()
    for row in rows:
        config = _load_config(row.config_json)
        if "webhook_secret" not in config:
            continue
        config.pop("webhook_secret", None)
        bind.execute(
            sa.text(
                """
                UPDATE channel_plugin_accounts
                SET config_json = :config_json
                WHERE id = :account_id
                """
            ),
            {
                "account_id": row.id,
                "config_json": json.dumps(config, ensure_ascii=False),
            },
        )


def downgrade() -> None:
    # 这里只做数据收口，不可靠地反推旧配置会制造更大的脏状态。
    pass


def _load_config(raw_value: str | None) -> dict[str, object]:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}
