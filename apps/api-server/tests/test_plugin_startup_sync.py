import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.models import PluginMount
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin_marketplace.models import PluginMarketplaceEntrySnapshot, PluginMarketplaceSource
from app.modules.plugin_marketplace.repository import (
    get_marketplace_instance_for_plugin,
    list_marketplace_install_tasks,
)


class PluginStartupSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_plugin_storage_root = settings.plugin_storage_root
        self._previous_marketplace_install_root = settings.plugin_marketplace_install_root
        settings.plugin_storage_root = self._tempdir.name
        settings.plugin_marketplace_install_root = self._tempdir.name

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        settings.plugin_storage_root = self._previous_plugin_storage_root
        settings.plugin_marketplace_install_root = self._previous_marketplace_install_root
        self._tempdir.cleanup()

    def test_sync_official_plugins_mounts_all_households_and_is_idempotent(self) -> None:
        plugin_root = self._create_plugin_dir(
            Path(self._tempdir.name) / "official" / "ai_provider_kimi_coding_plan",
            plugin_id="ai-provider-kimi-coding-plan",
            name="Kimi Coding Plan",
            version="1.0.0",
        )
        first_household = self._create_household("官方家庭A")
        second_household = self._create_household("官方家庭B")
        self.db.commit()

        first_result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()
        second_result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(2, first_result.official_created)
        self.assertEqual(0, second_result.official_created)
        self.assertEqual(0, second_result.official_updated)

        for household_id in (first_household.id, second_household.id):
            mounts = plugin_repository.list_plugin_mounts(self.db, household_id=household_id)
            self.assertEqual(1, len(mounts))
            self.assertEqual("official", mounts[0].source_type)
            self.assertEqual(str(plugin_root.resolve()), str(Path(mounts[0].plugin_root).resolve()))
            self.assertTrue(mounts[0].enabled)

    def test_sync_manual_plugins_repairs_paths_and_preserves_enabled_state(self) -> None:
        household = self._create_household("手工插件家庭")
        manual_root = self._create_plugin_dir(
            Path(self._tempdir.name) / "third_party" / "manual" / household.id / "manual-sync-plugin",
            plugin_id="manual-sync-plugin",
            name="Manual Sync Plugin",
            version="0.1.0",
        )
        missing_row_root = self._create_plugin_dir(
            Path(self._tempdir.name) / "third_party" / "manual" / household.id / "manual-created-plugin",
            plugin_id="manual-created-plugin",
            name="Manual Created Plugin",
            version="0.1.0",
        )
        stale_mount = PluginMount(
            id=new_uuid(),
            household_id=household.id,
            plugin_id="manual-sync-plugin",
            source_type="third_party",
            execution_backend="subprocess_runner",
            manifest_path=str((Path(self._tempdir.name) / "stale" / "manifest.json").resolve()),
            plugin_root=str((Path(self._tempdir.name) / "stale").resolve()),
            python_path="python-stale",
            working_dir=str((Path(self._tempdir.name) / "stale").resolve()),
            enabled=False,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        self.db.add(stale_mount)
        self.db.commit()

        result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(1, result.manual_created)
        self.assertEqual(1, result.manual_updated)

        mounts = {item.plugin_id: item for item in plugin_repository.list_plugin_mounts(self.db, household_id=household.id)}
        repaired = mounts["manual-sync-plugin"]
        created = mounts["manual-created-plugin"]
        self.assertEqual(str(manual_root.resolve()), str(Path(repaired.plugin_root).resolve()))
        self.assertFalse(repaired.enabled)
        self.assertEqual(str(missing_row_root.resolve()), str(Path(created.plugin_root).resolve()))
        self.assertFalse(created.enabled)

    def test_sync_manual_plugins_recognizes_release_directory_layout(self) -> None:
        household = self._create_household("手工发布目录家庭")
        release_root = self._create_plugin_dir(
            Path(self._tempdir.name)
            / "third_party"
            / "manual"
            / household.id
            / "manual-release-plugin"
            / "1.2.0--20260319T120000Z--abcd1234",
            plugin_id="manual-release-plugin",
            name="Manual Release Plugin",
            version="1.2.0",
        )
        self.db.commit()

        result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(1, result.manual_created)
        mounts = plugin_repository.list_plugin_mounts(self.db, household_id=household.id)
        self.assertEqual(1, len(mounts))
        self.assertEqual("manual-release-plugin", mounts[0].plugin_id)
        self.assertEqual(str(release_root.resolve()), str(Path(mounts[0].plugin_root).resolve()))
        self.assertEqual("subprocess_runner", mounts[0].execution_backend)

    def test_sync_official_theme_pack_plugins_mounts_all_households(self) -> None:
        theme_root = self._create_theme_pack_dir(
            Path(self._tempdir.name) / "official" / "theme_chun_he_jing_ming_pack",
            plugin_id="official.theme.chun-he-jing-ming",
            theme_id="chun-he-jing-ming",
            name="Official Theme Chun He Jing Ming",
            version="1.0.0",
        )
        first_household = self._create_household("主题家庭A")
        second_household = self._create_household("主题家庭B")
        self.db.commit()

        result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(2, result.official_created)
        for household_id in (first_household.id, second_household.id):
            mounts = plugin_repository.list_plugin_mounts(self.db, household_id=household_id)
            by_plugin = {item.plugin_id: item for item in mounts}
            self.assertIn("official.theme.chun-he-jing-ming", by_plugin)
            self.assertEqual(str(theme_root.resolve()), str(Path(by_plugin["official.theme.chun-he-jing-ming"].plugin_root).resolve()))
            self.assertEqual("official", by_plugin["official.theme.chun-he-jing-ming"].source_type)

    def test_sync_marketplace_plugins_restores_instance_without_reinstall(self) -> None:
        household = self._create_household("市场插件家庭")
        plugin_root = self._create_plugin_dir(
            Path(self._tempdir.name) / "third_party" / "marketplace" / household.id / "demo-plugin" / "1.0.0",
            plugin_id="demo-plugin",
            name="Demo Plugin",
            version="1.0.0",
        )
        source = PluginMarketplaceSource(
            source_id=new_uuid(),
            market_id="demo-market",
            name="Demo Market",
            owner="demo",
            repo_url="https://github.com/demo/marketplace",
            repo_provider="github",
            api_base_url=None,
            mirror_repo_url=None,
            mirror_repo_provider=None,
            mirror_api_base_url=None,
            branch="main",
            entry_root="plugins",
            trusted_level="third_party",
            enabled=True,
            last_sync_status="success",
            last_sync_error_json=None,
            last_synced_at=utc_now_iso(),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        snapshot = PluginMarketplaceEntrySnapshot(
            id=new_uuid(),
            source_id=source.source_id,
            plugin_id="demo-plugin",
            name="Demo Plugin",
            summary="demo",
            source_repo="https://github.com/demo/demo-plugin",
            manifest_path="manifest.json",
            readme_url="https://github.com/demo/demo-plugin#readme",
            publisher_json="{}",
            categories_json="[]",
            permissions_json="[]",
            maintainers_json="[]",
            versions_json="[]",
            install_json="{}",
            repository_metrics_json=None,
            raw_entry_json=json.dumps(
                {
                    "plugin_id": "demo-plugin",
                    "name": "Demo Plugin",
                    "summary": "demo",
                    "source_repo": "https://github.com/demo/demo-plugin",
                    "manifest_path": "manifest.json",
                    "readme_url": "https://github.com/demo/demo-plugin#readme",
                    "publisher": {"name": "Demo Publisher"},
                    "categories": ["demo"],
                    "risk_level": "low",
                    "permissions": ["device.read"],
                    "latest_version": "1.0.0",
                    "versions": [
                        {
                            "version": "1.0.0",
                            "git_ref": "refs/tags/v1.0.0",
                            "artifact_type": "source_archive",
                            "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                            "min_app_version": "0.1.0",
                        }
                    ],
                    "install": {
                        "requirements_path": "requirements.txt",
                        "readme_path": "README.md",
                    },
                    "maintainers": [{"name": "Maintainer"}],
                },
                ensure_ascii=False,
            ),
            risk_level="low",
            latest_version="1.0.0",
            manifest_digest=None,
            sync_status="ready",
            sync_error_json=None,
            synced_at=utc_now_iso(),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        stale_mount = PluginMount(
            id=new_uuid(),
            household_id=household.id,
            plugin_id="demo-plugin",
            source_type="third_party",
            execution_backend="subprocess_runner",
            manifest_path=str((Path(self._tempdir.name) / "stale-market" / "manifest.json").resolve()),
            plugin_root=str((Path(self._tempdir.name) / "stale-market").resolve()),
            python_path=sys.executable,
            working_dir=str((Path(self._tempdir.name) / "stale-market").resolve()),
            enabled=True,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        self.db.add(source)
        self.db.add(snapshot)
        self.db.add(stale_mount)
        self.db.commit()

        result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(1, result.marketplace_mount_updated)
        self.assertEqual(1, result.marketplace_instance_created)
        self.assertEqual([], list_marketplace_install_tasks(self.db, household_id=household.id, plugin_id="demo-plugin"))

        restored_instance = get_marketplace_instance_for_plugin(
            self.db,
            household_id=household.id,
            plugin_id="demo-plugin",
        )
        assert restored_instance is not None
        self.assertEqual(source.source_id, restored_instance.source_id)
        self.assertEqual("installed", restored_instance.install_status)
        self.assertEqual("https://github.com/demo/demo-plugin", restored_instance.source_repo)
        self.assertEqual("https://github.com/demo/marketplace", restored_instance.market_repo)
        self.assertEqual(str(plugin_root.resolve()), str(Path(restored_instance.plugin_root).resolve()))
        self.assertTrue(restored_instance.enabled)

    def test_startup_sync_marks_theme_pack_registry_refresh_when_theme_pack_mount_changes(self) -> None:
        household = self._create_household("主题插件家庭")
        self._create_plugin_dir(
            Path(self._tempdir.name) / "third_party" / "manual" / household.id / "third-party-theme-pack",
            plugin_id="third-party-theme-pack",
            name="Third Theme Pack",
            version="0.1.0",
            plugin_types=["theme-pack"],
            capabilities={
                "theme_pack": {
                    "theme_id": "aurora",
                    "display_name": "极光主题",
                    "tokens_resource": "themes/aurora.json",
                    "resource_source": "managed_plugin_dir",
                    "resource_version": "0.1.0",
                    "theme_schema_version": 1,
                    "platform_targets": ["h5", "rn"]
                }
            },
        )
        self.db.commit()

        result = sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        self.assertEqual(1, result.manual_created)
        self.assertEqual(1, result.theme_pack_registry_refresh)

    def _create_household(self, name: str):
        household = create_household(
            self.db,
            HouseholdCreate(name=name, city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        return household

    def _create_plugin_dir(
        self,
        root: Path,
        *,
        plugin_id: str,
        name: str,
        version: str,
        plugin_types: list[str] | None = None,
        capabilities: dict | None = None,
    ) -> Path:
        package_dir = root / "plugin"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n    return {'ok': True, 'payload': payload or {}}\n",
            encoding="utf-8",
        )
        manifest = {
            "id": plugin_id,
            "name": name,
            "version": version,
            "types": plugin_types or ["integration"],
            "permissions": ["device.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
        }
        if capabilities is not None:
            manifest["capabilities"] = capabilities
            if "theme-pack" in (plugin_types or []):
                manifest["permissions"] = []
                manifest["triggers"] = []
                manifest["entrypoints"] = {}
                themes_dir = root / "themes"
                themes_dir.mkdir(parents=True, exist_ok=True)
                (themes_dir / "aurora.json").write_text(
                    json.dumps(
                        {
                            "theme_id": "aurora",
                            "theme_schema_version": 1,
                            "resource_version": "0.1.0",
                            "tokens": {
                                "brandPrimary": "#66ccff",
                                "bgApp": "#060b15"
                            }
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return root

    def _create_theme_pack_dir(
        self,
        root: Path,
        *,
        plugin_id: str,
        theme_id: str,
        name: str,
        version: str,
    ) -> Path:
        theme_dir = root / "themes"
        theme_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": plugin_id,
            "name": name,
            "version": version,
            "types": ["theme-pack"],
            "permissions": [],
            "risk_level": "low",
            "triggers": [],
            "entrypoints": {},
            "capabilities": {
                "theme_pack": {
                    "theme_id": theme_id,
                    "display_name": "春和景明",
                    "description": "主题测试",
                    "tokens_resource": f"themes/{theme_id}.json",
                    "resource_source": "managed_plugin_dir",
                    "resource_version": version,
                    "theme_schema_version": 1,
                    "platform_targets": ["h5", "rn"],
                    "preview": {
                        "accent_color": "#d97756",
                        "preview_surface": "#f7f5f2",
                        "emoji": "🌸",
                    },
                    "fallback_theme_id": None,
                }
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (theme_dir / f"{theme_id}.json").write_text(
            json.dumps(
                {
                    "theme_id": theme_id,
                    "resource_version": version,
                    "theme_schema_version": 1,
                    "platform_targets": ["h5", "rn"],
                    "tokens": {
                        "brandPrimary": "#d97756",
                        "bgApp": "#f7f5f2",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return root


if __name__ == "__main__":
    unittest.main()

