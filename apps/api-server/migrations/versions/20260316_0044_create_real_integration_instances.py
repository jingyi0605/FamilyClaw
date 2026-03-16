"""create real integration instances

Revision ID: 20260316_0044
Revises: 20260316_0043
Create Date: 2026-03-16 22:40:00
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

from app.modules.plugin.config_crypto import encrypt_plugin_config_secrets


revision = "20260316_0044"
down_revision = "20260316_0043"
branch_labels = None
depends_on = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_display_name(plugin_id: str) -> str:
    if plugin_id == "homeassistant":
        return "Home Assistant"
    normalized = plugin_id.replace("_", " ").replace("-", " ").strip()
    return normalized.title() if normalized else plugin_id


def upgrade() -> None:
    op.create_table(
        "integration_instances",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("last_synced_at", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_integration_instances_household_id", "integration_instances", ["household_id"], unique=False)
    op.create_index("ix_integration_instances_plugin_id", "integration_instances", ["plugin_id"], unique=False)
    op.create_index("ix_integration_instances_status", "integration_instances", ["status"], unique=False)

    op.add_column("plugin_config_instances", sa.Column("integration_instance_id", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_plugin_config_instances_integration_instance_id",
        "plugin_config_instances",
        "integration_instances",
        ["integration_instance_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_plugin_config_instances_integration_instance_id",
        "plugin_config_instances",
        ["integration_instance_id"],
        unique=False,
    )

    op.add_column("device_bindings", sa.Column("integration_instance_id", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_device_bindings_integration_instance_id",
        "device_bindings",
        "integration_instances",
        ["integration_instance_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_device_bindings_integration_instance_id", "device_bindings", ["integration_instance_id"], unique=False)

    bind = op.get_bind()
    now = _now_iso()

    plugin_rows = bind.execute(
        sa.text(
            """
            SELECT
                id,
                household_id,
                plugin_id,
                created_at,
                updated_at
            FROM plugin_config_instances
            WHERE scope_type = 'plugin'
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()

    for row in plugin_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO integration_instances (
                    id,
                    household_id,
                    plugin_id,
                    display_name,
                    status,
                    last_synced_at,
                    last_error_code,
                    last_error_message,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :household_id,
                    :plugin_id,
                    :display_name,
                    :status,
                    :last_synced_at,
                    NULL,
                    NULL,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": row["id"],
                "household_id": row["household_id"],
                "plugin_id": row["plugin_id"],
                "display_name": _build_display_name(str(row["plugin_id"])),
                "status": "active",
                "last_synced_at": None,
                "created_at": row["created_at"] or now,
                "updated_at": row["updated_at"] or row["created_at"] or now,
            },
        )
        bind.execute(
            sa.text(
                """
                UPDATE plugin_config_instances
                SET integration_instance_id = :integration_instance_id
                WHERE id = :plugin_config_instance_id
                """
            ),
            {
                "integration_instance_id": row["id"],
                "plugin_config_instance_id": row["id"],
            },
        )

    legacy_rows = bind.execute(
        sa.text(
            """
            SELECT
                household_id,
                base_url,
                access_token,
                sync_rooms_enabled,
                last_device_sync_at,
                updated_at
            FROM household_ha_configs
            WHERE household_id NOT IN (
                SELECT household_id
                FROM integration_instances
                WHERE plugin_id = 'homeassistant'
            )
            """
        )
    ).mappings()

    for row in legacy_rows:
        instance_id = str(uuid.uuid4())
        config_id = str(uuid.uuid4())
        created_at = row["updated_at"] or now
        updated_at = row["updated_at"] or created_at
        bind.execute(
            sa.text(
                """
                INSERT INTO integration_instances (
                    id,
                    household_id,
                    plugin_id,
                    display_name,
                    status,
                    last_synced_at,
                    last_error_code,
                    last_error_message,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :household_id,
                    'homeassistant',
                    'Home Assistant',
                    'active',
                    :last_synced_at,
                    NULL,
                    NULL,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": instance_id,
                "household_id": row["household_id"],
                "last_synced_at": row["last_device_sync_at"],
                "created_at": created_at,
                "updated_at": updated_at,
            },
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO plugin_config_instances (
                    id,
                    household_id,
                    integration_instance_id,
                    plugin_id,
                    scope_type,
                    scope_key,
                    schema_version,
                    data_json,
                    secret_data_encrypted,
                    updated_by,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :household_id,
                    :integration_instance_id,
                    'homeassistant',
                    'plugin',
                    :scope_key,
                    1,
                    :data_json,
                    :secret_data_encrypted,
                    'migration:20260316_0044',
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": config_id,
                "household_id": row["household_id"],
                "integration_instance_id": instance_id,
                "scope_key": instance_id,
                "data_json": json.dumps(
                    {
                        "base_url": row["base_url"],
                        "sync_rooms_enabled": bool(row["sync_rooms_enabled"]),
                    },
                    ensure_ascii=False,
                ),
                "secret_data_encrypted": encrypt_plugin_config_secrets(
                    {"access_token": row["access_token"]}
                )
                if row["access_token"]
                else None,
                "created_at": created_at,
                "updated_at": updated_at,
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE device_bindings AS bindings
            SET integration_instance_id = configs.integration_instance_id
            FROM devices, plugin_config_instances AS configs
            WHERE devices.id = bindings.device_id
              AND bindings.plugin_id IS NOT NULL
              AND configs.household_id = devices.household_id
              AND configs.plugin_id = bindings.plugin_id
              AND configs.scope_type = 'plugin'
              AND configs.integration_instance_id IS NOT NULL
              AND bindings.integration_instance_id IS NULL
            """
        )
    )

    op.drop_constraint("uq_device_bindings_platform_entity", "device_bindings", type_="unique")
    op.create_unique_constraint(
        "uq_device_bindings_instance_platform_entity",
        "device_bindings",
        ["integration_instance_id", "platform", "external_entity_id"],
    )

    op.drop_table("household_ha_configs")


def downgrade() -> None:
    op.create_table(
        "household_ha_configs",
        sa.Column("household_id", sa.Text(), primary_key=True),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("sync_rooms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_device_sync_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT
                instances.household_id,
                instances.last_synced_at,
                instances.updated_at,
                configs.data_json
            FROM integration_instances AS instances
            JOIN plugin_config_instances AS configs
              ON configs.integration_instance_id = instances.id
            WHERE instances.plugin_id = 'homeassistant'
              AND configs.plugin_id = 'homeassistant'
              AND configs.scope_type = 'plugin'
            """
        )
    ).mappings()

    for row in rows:
        payload = json.loads(row["data_json"] or "{}")
        bind.execute(
            sa.text(
                """
                INSERT INTO household_ha_configs (
                    household_id,
                    base_url,
                    access_token,
                    sync_rooms_enabled,
                    last_device_sync_at,
                    updated_at
                ) VALUES (
                    :household_id,
                    :base_url,
                    NULL,
                    :sync_rooms_enabled,
                    :last_device_sync_at,
                    :updated_at
                )
                ON CONFLICT (household_id) DO NOTHING
                """
            ),
            {
                "household_id": row["household_id"],
                "base_url": payload.get("base_url"),
                "sync_rooms_enabled": bool(payload.get("sync_rooms_enabled")),
                "last_device_sync_at": row["last_synced_at"],
                "updated_at": row["updated_at"] or _now_iso(),
            },
        )

    op.drop_constraint("uq_device_bindings_instance_platform_entity", "device_bindings", type_="unique")
    op.create_unique_constraint(
        "uq_device_bindings_platform_entity",
        "device_bindings",
        ["platform", "external_entity_id"],
    )
    op.drop_index("ix_device_bindings_integration_instance_id", table_name="device_bindings")
    op.drop_constraint("fk_device_bindings_integration_instance_id", "device_bindings", type_="foreignkey")
    op.drop_column("device_bindings", "integration_instance_id")

    op.drop_index("ix_plugin_config_instances_integration_instance_id", table_name="plugin_config_instances")
    op.drop_constraint("fk_plugin_config_instances_integration_instance_id", "plugin_config_instances", type_="foreignkey")
    op.drop_column("plugin_config_instances", "integration_instance_id")

    op.drop_index("ix_integration_instances_status", table_name="integration_instances")
    op.drop_index("ix_integration_instances_plugin_id", table_name="integration_instances")
    op.drop_index("ix_integration_instances_household_id", table_name="integration_instances")
    op.drop_table("integration_instances")
