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
from app.modules.household.schemas import HouseholdCreate, HouseholdUpdate
from app.modules.household.service import build_household_read, create_household, update_household
from app.modules.plugin.service import PluginManifestValidationError
from app.modules.plugin.schemas import PluginMountCreate, PluginMountUpdate, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, set_household_plugin_enabled, update_plugin_mount
from app.modules.region.schemas import RegionSelection
from app.modules.region.service import (
    RegionServiceError,
    list_region_catalog,
    resolve_household_region_context,
    search_region_catalog,
)


class PluginRegionProviderRuntimeTests(unittest.TestCase):
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

    def test_mounted_region_provider_supports_catalog_search_and_household_binding(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="插件地区家庭", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(Path(plugin_tempdir), plugin_id="jp-region-provider")
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
                keyword="新宿",
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

        self.assertEqual(["东京都"], [item.name for item in provinces])
        self.assertEqual(["新宿区"], [item.name for item in matches])
        self.assertEqual("plugin.jp-sample", updated.region.provider_code)
        self.assertEqual("JP", updated.region.country_code)
        self.assertEqual("东京都 新宿区", updated.city)
        self.assertEqual("Asia/Tokyo", updated.region.timezone)

    def test_provider_lifecycle_tracks_mount_enable_state(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="生命周期家庭", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(Path(plugin_tempdir), plugin_id="jp-region-provider")
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
            unavailable_context = resolve_household_region_context(self.db, household.id)

            with self.assertRaises(RegionServiceError) as context:
                list_region_catalog(
                    self.db,
                    provider_code="plugin.jp-sample",
                    country_code="JP",
                    household_id=household.id,
                    admin_level="province",
                )

            update_plugin_mount(
                self.db,
                household_id=household.id,
                plugin_id="jp-region-provider",
                payload=PluginMountUpdate(enabled=True),
            )
            recovered_context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("provider_unavailable", unavailable_context.status)
        self.assertEqual("region_provider_not_found", context.exception.error_code)
        self.assertEqual("configured", recovered_context.status)
        self.assertEqual("plugin.jp-sample", recovered_context.provider_code)

    def test_provider_mount_conflict_rejects_same_provider_code_in_one_household(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="冲突家庭", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            root = Path(plugin_tempdir)
            first_root = self._create_region_provider_plugin(root, plugin_id="jp-region-provider-a")
            second_root = self._create_region_provider_plugin(root, plugin_id="jp-region-provider-b")

            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(first_root),
                    python_path=sys.executable,
                    working_dir=str(first_root),
                    timeout_seconds=20,
                ),
            )

            with self.assertRaisesRegex(PluginManifestValidationError, "plugin.jp-sample"):
                register_plugin_mount(
                    self.db,
                    household_id=household.id,
                    payload=PluginMountCreate(
                        source_type="third_party",
                        plugin_root=str(second_root),
                        python_path=sys.executable,
                        working_dir=str(second_root),
                        timeout_seconds=20,
                    ),
                )

    def test_household_override_disables_region_provider_without_changing_mount_base_state(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="覆盖禁用家庭", timezone="Asia/Tokyo", locale="ja-JP"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_region_provider_plugin(Path(plugin_tempdir), plugin_id="jp-region-provider")
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

            unavailable_context = resolve_household_region_context(self.db, household.id)

        self.assertEqual("provider_unavailable", unavailable_context.status)

    def _create_region_provider_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "日本地区提供方",
                    "version": "0.1.0",
                    "types": ["region-provider"],
                    "permissions": ["region.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "region_provider": "plugin.region_provider.handle"
                    },
                    "capabilities": {
                        "region_provider": {
                            "provider_code": "plugin.jp-sample",
                            "country_codes": ["JP"],
                            "entrypoint": "plugin.region_provider.handle",
                            "reserved": False
                        }
                    }
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
            "        'name': '东京都',\n"
            "        'full_name': '东京都',\n"
            "        'path_codes': ['130000'],\n"
            "        'path_names': ['东京都'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131000',\n"
            "        'parent_region_code': '130000',\n"
            "        'admin_level': 'city',\n"
            "        'name': '东京都区部',\n"
            "        'full_name': '东京都 / 东京都区部',\n"
            "        'path_codes': ['130000', '131000'],\n"
            "        'path_names': ['东京都', '东京都区部'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131004',\n"
            "        'parent_region_code': '131000',\n"
            "        'admin_level': 'district',\n"
            "        'name': '新宿区',\n"
            "        'full_name': '东京都 / 东京都区部 / 新宿区',\n"
            "        'path_codes': ['130000', '131000', '131004'],\n"
            "        'path_names': ['东京都', '东京都区部', '新宿区'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
            "        'source_version': 'jp-v1'\n"
            "    },\n"
            "    {\n"
            "        'provider_code': 'plugin.jp-sample',\n"
            "        'country_code': 'JP',\n"
            "        'region_code': '131005',\n"
            "        'parent_region_code': '131000',\n"
            "        'admin_level': 'district',\n"
            "        'name': '文京区',\n"
            "        'full_name': '东京都 / 东京都区部 / 文京区',\n"
            "        'path_codes': ['130000', '131000', '131005'],\n"
            "        'path_names': ['东京都', '东京都区部', '文京区'],\n"
            "        'timezone': 'Asia/Tokyo',\n"
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
            "        return {\n"
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
            "    raise ValueError(f'unsupported operation: {operation}')\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
