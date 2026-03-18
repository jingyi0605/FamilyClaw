import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.modules.household.schemas import HouseholdCreate, HouseholdUpdate
from app.modules.household.service import build_household_read, create_household, update_household
from app.modules.plugin.schemas import PluginMountCreate, PluginMountUpdate, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, set_household_plugin_enabled, update_plugin_mount
from app.modules.region.schemas import RegionSelection
from app.modules.region.service import RegionServiceError, list_region_catalog, resolve_household_region_context, search_region_catalog
from tests.test_db_support import PostgresTestDatabase


class PluginRegionProviderRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_mounted_region_provider_returns_region_representative_coordinate(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Plugin Provider Household", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(
                Path(plugin_tempdir),
                plugin_id="jp-region-provider",
                with_coordinates=True,
            )
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

            provinces = list_region_catalog(
                self.db,
                provider_code="plugin.jp-sample",
                country_code="JP",
                household_id=household.id,
                admin_level="province",
            )
            matches = search_region_catalog(
                self.db,
                provider_code="plugin.jp-sample",
                country_code="JP",
                household_id=household.id,
                keyword="Shinjuku",
                admin_level="district",
            )

            updated_household, _ = update_household(
                self.db,
                household,
                HouseholdUpdate(
                    region_selection=RegionSelection(
                        provider_code="plugin.jp-sample",
                        country_code="JP",
                        region_code="131004",
                    )
                ),
            )
            self.db.flush()
            updated = build_household_read(self.db, updated_household)

        self.assertEqual(["Tokyo"], [item.name for item in provinces])
        self.assertEqual(["Shinjuku"], [item.name for item in matches])
        self.assertEqual("plugin.jp-sample", updated.region.provider_code)
        self.assertEqual("JP", updated.region.country_code)
        self.assertTrue(updated.region.coordinate.available)
        self.assertEqual("region_representative", updated.region.coordinate.source_type)
        self.assertEqual(35.6938, updated.region.coordinate.latitude)

    def test_provider_disable_keeps_snapshot_coordinate_but_marks_provider_unavailable(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Provider Lifecycle Household", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(
                Path(plugin_tempdir),
                plugin_id="jp-region-provider",
                with_coordinates=True,
            )
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
            update_household(
                self.db,
                household,
                HouseholdUpdate(
                    region_selection=RegionSelection(
                        provider_code="plugin.jp-sample",
                        country_code="JP",
                        region_code="131004",
                    )
                ),
            )
            self.db.flush()

            update_plugin_mount(
                self.db,
                household_id=household.id,
                plugin_id="jp-region-provider",
                payload=PluginMountUpdate(enabled=False),
            )

            context = resolve_household_region_context(self.db, household.id)

            with self.assertRaises(RegionServiceError) as raised:
                list_region_catalog(
                    self.db,
                    provider_code="plugin.jp-sample",
                    country_code="JP",
                    household_id=household.id,
                    admin_level="province",
                )

        self.assertEqual("provider_unavailable", context.status)
        self.assertTrue(context.coordinate.available)
        self.assertEqual("region_representative", context.coordinate.source_type)
        self.assertEqual("region_provider_not_found", raised.exception.error_code)

    def test_household_override_disables_provider_without_losing_exact_coordinate_priority(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Exact Override Household", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        household.latitude = 35.7001
        household.longitude = 139.7002
        household.coordinate_source = "manual_app"
        household.coordinate_precision = "point"
        household.coordinate_updated_at = "2026-03-18T00:10:00Z"
        self.db.add(household)
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(
                Path(plugin_tempdir),
                plugin_id="jp-region-provider",
                with_coordinates=True,
            )
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
            update_household(
                self.db,
                household,
                HouseholdUpdate(
                    region_selection=RegionSelection(
                        provider_code="plugin.jp-sample",
                        country_code="JP",
                        region_code="131004",
                    )
                ),
            )
            self.db.flush()

            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="jp-region-provider",
                payload=PluginStateUpdateRequest(enabled=False),
                updated_by="tester",
            )

            context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("provider_unavailable", context.status)
        self.assertEqual("household_exact", context.coordinate.source_type)
        self.assertEqual(35.7001, context.coordinate.latitude)

    def test_old_style_plugin_provider_without_coordinates_returns_unavailable_coordinate(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Legacy Plugin Provider Household", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(
                Path(plugin_tempdir),
                plugin_id="jp-region-provider-legacy",
                with_coordinates=False,
            )
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
            update_household(
                self.db,
                household,
                HouseholdUpdate(
                    region_selection=RegionSelection(
                        provider_code="plugin.jp-sample",
                        country_code="JP",
                        region_code="131004",
                    )
                ),
            )
            self.db.flush()

            context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("configured", context.status)
        self.assertFalse(context.coordinate.available)
        self.assertEqual("unavailable", context.coordinate.source_type)

    def _create_region_provider_plugin(self, root: Path, *, plugin_id: str, with_coordinates: bool) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

        def coordinate_block(latitude: float, longitude: float, precision: str) -> str:
            if not with_coordinates:
                return ""
            return (
                f"        'latitude': {latitude},\n"
                f"        'longitude': {longitude},\n"
                f"        'coordinate_precision': '{precision}',\n"
                "        'coordinate_source': 'provider_external',\n"
                "        'coordinate_updated_at': '2026-03-18T00:00:00Z',\n"
            )

        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "JP Region Provider",
                    "version": "0.1.0",
                    "types": ["region-provider"],
                    "permissions": ["region.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"region_provider": "plugin.region_provider.handle"},
                    "capabilities": {
                        "region_provider": {
                            "provider_code": "plugin.jp-sample",
                            "country_codes": ["JP"],
                            "entrypoint": "plugin.region_provider.handle",
                            "reserved": False,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        (package_dir / "region_provider.py").write_text(
            "NODES = [\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '130000',\n"
            "        'parent_region_code': None,\n"
            "        'admin_level': 'province',\n"
            "        'name': 'Tokyo',\n"
            "        'full_name': 'Tokyo',\n"
            "        'path_codes': ['130000'],\n"
            "        'path_names': ['Tokyo'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            f"{coordinate_block(35.6762, 139.6503, 'province')}"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131000',\n"
            "        'parent_region_code': '130000',\n"
            "        'admin_level': 'city',\n"
            "        'name': 'Tokyo City',\n"
            "        'full_name': 'Tokyo / Tokyo City',\n"
            "        'path_codes': ['130000', '131000'],\n"
            "        'path_names': ['Tokyo', 'Tokyo City'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            f"{coordinate_block(35.6895, 139.6917, 'city')}"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131004',\n"
            "        'parent_region_code': '131000',\n"
            "        'admin_level': 'district',\n"
            "        'name': 'Shinjuku',\n"
            "        'full_name': 'Tokyo / Tokyo City / Shinjuku',\n"
            "        'path_codes': ['130000', '131000', '131004'],\n"
            "        'path_names': ['Tokyo', 'Tokyo City', 'Shinjuku'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            f"{coordinate_block(35.6938, 139.7034, 'district')}"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131005',\n"
            "        'parent_region_code': '131000',\n"
            "        'admin_level': 'district',\n"
            "        'name': 'Bunkyo',\n"
            "        'full_name': 'Tokyo / Tokyo City / Bunkyo',\n"
            "        'path_codes': ['130000', '131000', '131005'],\n"
            "        'path_names': ['Tokyo', 'Tokyo City', 'Bunkyo'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            f"{coordinate_block(35.7081, 139.7522, 'district')}"
            "        'source_version': 'jp-v1'\n"
            "    }\n"
            "]\n\n"
            "def _matches_keyword(item, keyword):\n"
            "    keyword = (keyword or '').strip().lower()\n"
            "    if not keyword:\n"
            "        return True\n"
            "    return keyword in item['name'].lower() or keyword in item['full_name'].lower()\n\n"
            "def handle(payload=None):\n"
            "    data = payload or {}\n"
            "    operation = data.get('operation')\n"
            "    admin_level = data.get('admin_level')\n"
            "    parent_region_code = data.get('parent_region_code')\n"
            "    if operation == 'list_children':\n"
            "        return [item for item in NODES if item['parent_region_code'] == parent_region_code and (admin_level is None or item['admin_level'] == admin_level)]\n"
            "    if operation == 'search':\n"
            "        keyword = data.get('keyword')\n"
            "        return [item for item in NODES if (admin_level is None or item['admin_level'] == admin_level) and (parent_region_code is None or item['parent_region_code'] == parent_region_code) and _matches_keyword(item, keyword)]\n"
            "    if operation == 'resolve':\n"
            "        region_code = data.get('region_code')\n"
            "        for item in NODES:\n"
            "            if item['region_code'] == region_code:\n"
            "                return item\n"
            "        return None\n"
            "    if operation == 'build_snapshot':\n"
            "        node = data.get('node') or {}\n"
            "        snapshot = {\n"
            "            'provider_code': node.get('provider_code'),\n"
            "            'country_code': node.get('country_code'),\n"
            "            'region_code': node.get('region_code'),\n"
            "            'admin_level': node.get('admin_level'),\n"
            "            'province': {'code': node.get('path_codes', [None])[0], 'name': node.get('path_names', [None])[0]},\n"
            "            'city': {'code': node.get('path_codes', [None, None])[1], 'name': node.get('path_names', [None, None])[1]},\n"
            "            'district': {'code': node.get('path_codes', [None, None, None])[2], 'name': node.get('path_names', [None, None, None])[2]},\n"
            "            'display_name': f\"{node.get('path_names', ['', '', ''])[0]} {node.get('path_names', ['', '', ''])[2]}\".strip(),\n"
            "            'timezone': node.get('timezone')\n"
            "        }\n"
            "        if node.get('latitude') is not None and node.get('longitude') is not None:\n"
            "            snapshot['representative_coordinate'] = {\n"
            "                'latitude': node.get('latitude'),\n"
            "                'longitude': node.get('longitude'),\n"
            "                'coordinate_precision': node.get('coordinate_precision'),\n"
            "                'coordinate_source': node.get('coordinate_source'),\n"
            "                'coordinate_updated_at': node.get('coordinate_updated_at')\n"
            "            }\n"
            "        return snapshot\n"
            "    raise ValueError(f'unsupported operation: {operation}')\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
