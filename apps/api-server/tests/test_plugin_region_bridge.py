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
from app.modules.plugin.schemas import PluginExecutionRequest, PluginRunnerConfig
from app.modules.plugin.service import execute_household_plugin, resolve_plugin_household_region_context
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog


class PluginRegionBridgeTests(unittest.TestCase):
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
        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="鍖椾含甯?,
                    full_name="鍖椾含甯?,
                    path_codes=["110000"],
                    path_names=["鍖椾含甯?],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="鍖椾含甯?,
                    full_name="鍖椾含甯?/ 鍖椾含甯?,
                    path_codes=["110000", "110100"],
                    path_names=["鍖椾含甯?, "鍖椾含甯?],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="鏈濋槼鍖?,
                    full_name="鍖椾含甯?/ 鍖椾含甯?/ 鏈濋槼鍖?,
                    path_codes=["110000", "110100", "110105"],
                    path_names=["鍖椾含甯?, "鍖椾含甯?, "鏈濋槼鍖?],
                ),
            ],
            source_version="plugin-region-test-v1",
        )
        self.household = create_household(
            self.db,
            HouseholdCreate(
                name="鍦板尯鎻掍欢瀹跺涵",
                timezone="Asia/Shanghai",
                locale="zh-CN",
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                ),
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_plugin_can_resolve_household_region_context_through_controlled_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_region_reader_plugin(Path(tempdir))

            context = resolve_plugin_household_region_context(
                self.db,
                household_id=self.household.id,
                plugin_id="region-context-reader",
                root_dir=plugin_root,
            )

        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual("configured", context.status)
        self.assertEqual("110105", context.region_code)

    def test_execute_household_plugin_injects_region_context_when_manifest_declares_need(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_region_reader_plugin(Path(tempdir))

            result = execute_household_plugin(
                self.db,
                household_id=self.household.id,
                request=PluginExecutionRequest(
                    plugin_id="region-context-reader",
                    plugin_type="connector",
                    payload={"note": "test"},
                ),
                root_dir=plugin_root,
                source_type="third_party",
                runner_config=PluginRunnerConfig(
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )

        self.assertTrue(result.success)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        system_context = result.output["system_context"]
        self.assertEqual("region.resolve_household_context", system_context["region"]["entry"])
        self.assertEqual("110105", system_context["region"]["household_context"]["region_code"])
        self.assertEqual("鍖椾含甯?鏈濋槼鍖?, system_context["region"]["household_context"]["display_name"])

    def _create_region_reader_plugin(self, root: Path) -> Path:
        plugin_root = root / "region-context-reader"
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "region-context-reader",
                    "name": "鍦板尯涓婁笅鏂囪鍙栨彃浠?,
                    "version": "0.1.0",
                    "types": ["connector"],
                    "permissions": ["region.read"],
                    "risk_level": "low",
                    "triggers": ["manual", "agent"],
                    "entrypoints": {"connector": "plugin.connector.sync"},
                    "capabilities": {
                        "context_reads": {
                            "household_region_context": True
                        },
                        "region_provider": {
                            "provider_code": "plugin.future-region-provider",
                            "country_codes": ["JP"],
                            "entrypoint": "plugin.region_provider.build",
                            "reserved": True
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "connector.py").write_text(
            "def sync(payload=None):\n"
            "    data = payload or {}\n"
            "    return {'system_context': data.get('_system_context'), 'records': []}\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()

