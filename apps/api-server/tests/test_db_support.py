import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.engine import build_database_engine

DEFAULT_TEST_DATABASE_URL = os.getenv("FAMILYCLAW_TEST_DATABASE_URL") or settings.database_url


def get_test_database_url() -> str:
    database_url = DEFAULT_TEST_DATABASE_URL
    backend_name = make_url(database_url).get_backend_name()
    if backend_name != "postgresql":
        raise RuntimeError(
            "测试数据库必须是 PostgreSQL，请在 .env 或环境变量里配置 FAMILYCLAW_TEST_DATABASE_URL。"
        )
    return database_url


def build_schema_database_url(database_url: str, schema_name: str) -> str:
    url = make_url(database_url)
    options = str(url.query.get("options") or "").strip()
    search_path_option = f"-csearch_path={schema_name}"
    merged_options = search_path_option if not options else f"{options} {search_path_option}"
    schema_url: URL = url.update_query_dict({"options": merged_options})
    return schema_url.render_as_string(hide_password=False)


class PostgresTestDatabase:
    def __init__(self, *, test_id: str):
        self.test_id = test_id
        self.base_database_url = get_test_database_url()
        self.schema_name = self._build_schema_name(test_id)
        self.database_url = build_schema_database_url(self.base_database_url, self.schema_name)
        self._previous_database_url: str | None = None
        self._previous_plugin_dev_root: str | None = None
        self._plugin_dev_root_tempdir: tempfile.TemporaryDirectory[str] | None = None
        self._admin_engine = None
        self.engine = None
        self.SessionLocal = None

    def setup(self, *, upgrade_head: bool = True) -> None:
        self._previous_database_url = settings.database_url
        self._previous_plugin_dev_root = settings.plugin_dev_root
        settings.database_url = self.database_url
        self._plugin_dev_root_tempdir = tempfile.TemporaryDirectory(prefix="familyclaw-test-plugins-dev-")
        settings.plugin_dev_root = str(Path(self._plugin_dev_root_tempdir.name).resolve())
        self._seed_builtin_test_dev_plugins()

        self._admin_engine = build_database_engine(
            self.base_database_url,
            pool_size=1,
            max_overflow=0,
            pool_timeout_seconds=30,
            pool_recycle_seconds=1800,
        )
        with self._admin_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema_name}"'))

        self.engine = build_database_engine(
            self.database_url,
            pool_size=1,
            max_overflow=0,
            pool_timeout_seconds=30,
            pool_recycle_seconds=1800,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

        if upgrade_head:
            alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
            alembic_config.attributes["sqlalchemy_url"] = self.database_url
            with self.engine.connect() as connection:
                alembic_config.attributes["connection"] = connection
                command.upgrade(alembic_config, "head")

    def close(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
        if self._admin_engine is not None:
            with self._admin_engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE'))
            self._admin_engine.dispose()
        if self._previous_database_url is not None:
            settings.database_url = self._previous_database_url
        if self._previous_plugin_dev_root is not None:
            settings.plugin_dev_root = self._previous_plugin_dev_root
        if self._plugin_dev_root_tempdir is not None:
            self._plugin_dev_root_tempdir.cleanup()
            self._plugin_dev_root_tempdir = None

    def _seed_builtin_test_dev_plugins(self) -> None:
        plugin_dev_root = Path(settings.plugin_dev_root).resolve()
        plugin_dev_root.mkdir(parents=True, exist_ok=True)

        repo_plugin_dev_root = Path(__file__).resolve().parents[1] / "plugins-dev"
        weather_plugin_root = repo_plugin_dev_root / "official_weather"
        if not weather_plugin_root.exists():
            return

        shutil.copytree(
            weather_plugin_root,
            plugin_dev_root / "official_weather",
            dirs_exist_ok=True,
        )

    @staticmethod
    def _build_schema_name(test_id: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", test_id.lower()).strip("_")
        normalized = normalized[:40] or "test"
        return f"t_{normalized}_{uuid.uuid4().hex[:10]}"
