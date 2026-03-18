import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginExecutionRequest, PluginRunnerConfig
from app.modules.plugin.service import execute_household_plugin, resolve_plugin_household_region_context
from app.modules.region.providers import BUILTIN_CN_MAINLAND_PROVIDER, CnMainlandRegionProvider, region_provider_registry
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog
from tests.test_db_support import PostgresTestDatabase


class PluginRegionBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        self._original_builtin_provider = region_provider_registry.get(BUILTIN_CN_MAINLAND_PROVIDER)
        region_provider_registry.register(CnMainlandRegionProvider())

        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="Beijing",
                    full_name="Beijing",
                    path_codes=["110000"],
                    path_names=["Beijing"],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="Beijing City",
                    full_name="Beijing / Beijing City",
                    path_codes=["110000", "110100"],
                    path_names=["Beijing", "Beijing City"],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="Chaoyang",
                    full_name="Beijing / Beijing City / Chaoyang",
                    path_codes=["110000", "110100", "110105"],
                    path_names=["Beijing", "Beijing City", "Chaoyang"],
                    latitude=39.9219,
                    longitude=116.4436,
                    coordinate_precision="district",
                    coordinate_source="provider_builtin",
                    coordinate_updated_at="2026-03-18T00:00:00Z",
                ),
            ],
            source_version="plugin-bridge-test-v1",
        )
        self.household = create_household(
            self.db,
            HouseholdCreate(
                name="Plugin Region Household",
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
        if self._original_builtin_provider is not None:
            region_provider_registry.register(self._original_builtin_provider)
        self._db_helper.close()

    def test_plugin_can_resolve_household_region_context(self) -> None:
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
        self.assertEqual("region_representative", context.coordinate.source_type)
        self.assertEqual(39.9219, context.coordinate.latitude)

    def test_execute_household_plugin_injects_coordinate_context(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_region_reader_plugin(Path(tempdir))
            result = execute_household_plugin(
                self.db,
                household_id=self.household.id,
                request=PluginExecutionRequest(
                    plugin_id="region-context-reader",
                    plugin_type="integration",
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
        assert isinstance(result.output, dict)
        system_context = result.output["system_context"]
        household_context = system_context["region"]["household_context"]

        self.assertEqual("region.resolve_household_context", system_context["region"]["entry"])
        self.assertEqual("110105", household_context["region_code"])
        self.assertEqual("region_representative", household_context["coordinate"]["source_type"])
        self.assertEqual(39.9219, household_context["coordinate"]["latitude"])

    def _create_region_reader_plugin(self, root: Path) -> Path:
        plugin_root = root / "region-context-reader"
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": "region-context-reader",
                    "name": "Region Context Reader",
                    "version": "0.1.0",
                    "types": ["integration"],
                    "permissions": ["region.read"],
                    "risk_level": "low",
                    "triggers": ["manual", "agent"],
                    "entrypoints": {"integration": "plugin.integration.sync"},
                    "capabilities": {
                        "context_reads": {"household_region_context": True},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n"
            "    data = payload or {}\n"
            "    return {'system_context': data.get('_system_context'), 'records': []}\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()

