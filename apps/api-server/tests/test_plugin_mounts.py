import json
import sys
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginMountCreate, PluginMountUpdate
from app.modules.plugin.service import (
    delete_plugin_mount,
    list_plugin_mounts,
    list_registered_plugins_for_household,
    register_plugin_mount,
    update_plugin_mount,
)


class PluginMountTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_register_update_delete_plugin_mount(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Mount Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_third_party_plugin(Path(plugin_tempdir), plugin_id="third-party-sync-plugin")

            created = register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.flush()

            self.assertEqual("third-party-sync-plugin", created.plugin_id)
            self.assertEqual("subprocess_runner", created.execution_backend)

            mounted = list_plugin_mounts(self.db, household_id=household.id)
            self.assertEqual(1, len(mounted))
            self.assertEqual("third-party-sync-plugin", mounted[0].plugin_id)

            snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
            mounted_plugin = next(item for item in snapshot.items if item.id == "third-party-sync-plugin")
            self.assertEqual("third_party", mounted_plugin.source_type)
            self.assertEqual("subprocess_runner", mounted_plugin.execution_backend)

            updated = update_plugin_mount(
                self.db,
                household_id=household.id,
                plugin_id="third-party-sync-plugin",
                payload=PluginMountUpdate(timeout_seconds=45, enabled=False),
            )
            self.db.flush()

            self.assertEqual(45, updated.timeout_seconds)
            self.assertFalse(updated.enabled)

            delete_plugin_mount(self.db, household_id=household.id, plugin_id="third-party-sync-plugin")
            self.db.commit()

            mounted_after_delete = list_plugin_mounts(self.db, household_id=household.id)
            self.assertEqual([], mounted_after_delete)

    def _create_third_party_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "第三方插件",
                    "version": "0.1.0",
                    "types": ["connector", "memory-ingestor"],
                    "permissions": ["health.read", "memory.write.observation"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "connector": "plugin.connector.sync",
                        "memory_ingestor": "plugin.ingestor.transform",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "connector.py").write_text(
            "def sync(payload=None):\n    return {'records': []}\n",
            encoding="utf-8",
        )
        (package_dir / "ingestor.py").write_text(
            "def transform(payload=None):\n    return []\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
