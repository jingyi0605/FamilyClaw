from __future__ import annotations

from contextlib import contextmanager
import hashlib
from pathlib import Path
import sys
from threading import Lock

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
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

    # 只允许宿主内置插件在主进程里执行私有迁移，避免第三方插件拿到过高权限。
    if plugin.source_type != "builtin":
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
    alembic_config.attributes["connection"] = db.connection()

    with _plugin_runtime_import_path(_resolve_plugin_root(plugin)):
        command.upgrade(alembic_config, "head")


@contextmanager
def _plugin_runtime_import_path(plugin_root: Path):
    candidate_paths = [str(plugin_root.parent), str(plugin_root)]
    inserted_paths: list[str] = []
    for candidate in candidate_paths:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            inserted_paths.append(candidate)
    try:
        yield
    finally:
        for candidate in reversed(inserted_paths):
            try:
                sys.path.remove(candidate)
            except ValueError:
                pass
