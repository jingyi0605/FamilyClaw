import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    @staticmethod
    def _plugin_storage_root() -> Path:
        return Path(settings.plugin_storage_root).resolve()

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
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
            self.assertTrue(Path(created.plugin_root).resolve().is_relative_to(self._plugin_storage_root()))
            self.assertIn(
                str((self._plugin_storage_root() / "third_party" / "manual" / household.id).resolve()),
                str(Path(created.plugin_root).resolve()),
            )

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

    def test_list_registered_plugins_for_household_skips_invalid_mounted_manifest_and_logs_error(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Broken Mount Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_third_party_plugin(Path(plugin_tempdir), plugin_id="third-party-sync-plugin")

            register_plugin_mount(
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

            mounted_manifest_path = Path(list_plugin_mounts(self.db, household_id=household.id)[0].manifest_path)
            mounted_manifest_path.write_text(
                json.dumps(
                    {
                        "id": "third_party_sync_plugin",
                        "name": "坏挂载插件",
                        "version": "0.1.0",
                        "types": ["connector"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "connector": "plugin.connector.sync",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("app.modules.plugin.service.logger.error") as log_error:
                snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)

        self.assertNotIn("third-party-sync-plugin", [item.id for item in snapshot.items])
        log_error.assert_called_once()
        message = log_error.call_args.args[0]
        self.assertIn("家庭插件 manifest 无效", message)
        self.assertIn("third-party-sync-plugin", message)

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

