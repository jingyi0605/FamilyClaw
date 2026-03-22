from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from .import_path import collect_plugin_import_roots, plugin_runtime_import_path
from .schemas import PluginRegistryItem


_PLUGIN_PRIVATE_MIGRATION_LOCK = Lock()


def ensure_plugin_private_migrations(
    db: Session,
    *,
    plugin: PluginRegistryItem,
) -> None:
    migration_root = _resolve_plugin_migration_root(plugin)
    if migration_root is None:
        return

    # 私有迁移由宿主统一跑，builtin / third_party 都走同一条受控入口。
    if plugin.source_type not in {"builtin", "third_party"}:
        return

    database_url = _resolve_database_url(db)
    with _PLUGIN_PRIVATE_MIGRATION_LOCK:
        _run_plugin_private_migrations(
            db=db,
            plugin=plugin,
            migration_root=migration_root,
            database_url=database_url,
        )


def _resolve_plugin_migration_root(plugin: PluginRegistryItem) -> Path | None:
    plugin_root = _resolve_plugin_root(plugin)
    migration_root = (plugin_root / "migrations").resolve()
    if not migration_root.exists():
        return None
    if not migration_root.is_dir():
        raise ValueError(f"插件私有迁移目录不是文件夹: {migration_root}")
    env_path = migration_root / "env.py"
    if not env_path.is_file():
        raise ValueError(f"插件私有迁移目录缺少 env.py: {migration_root}")
    return migration_root


def _resolve_plugin_root(plugin: PluginRegistryItem) -> Path:
    if plugin.runner_config is not None and plugin.runner_config.plugin_root:
        return Path(plugin.runner_config.plugin_root).resolve()
    manifest_path = Path(plugin.manifest_path).resolve()
    return manifest_path.parent


def _resolve_database_url(db: Session) -> str:
    bind = db.get_bind()
    bind_url = getattr(bind, "url", None)
    if bind_url is not None:
        return bind_url.render_as_string(hide_password=False)
    engine = getattr(bind, "engine", None)
    if engine is not None and getattr(engine, "url", None) is not None:
        return engine.url.render_as_string(hide_password=False)
    return settings.database_url


def _build_plugin_version_table_name(plugin_id: str) -> str:
    suffix = hashlib.sha1(plugin_id.encode("utf-8")).hexdigest()[:12]
    return f"plugin_alembic_version_{suffix}"


def _run_plugin_private_migrations(
    *,
    db: Session,
    plugin: PluginRegistryItem,
    migration_root: Path,
    database_url: str,
) -> None:
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(migration_root))
    alembic_config.attributes["sqlalchemy_url"] = database_url
    alembic_config.attributes["plugin_root"] = str(_resolve_plugin_root(plugin))
    alembic_config.attributes["version_table"] = _build_plugin_version_table_name(plugin.id)

    with plugin_runtime_import_path(
        _resolve_plugin_root(plugin),
        package_names=collect_plugin_import_roots(plugin),
    ):
        command.upgrade(alembic_config, "head")
