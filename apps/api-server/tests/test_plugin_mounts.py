import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.channel.models import ChannelPluginAccount
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin_marketplace.models import PluginMarketplaceInstance
from app.modules.plugin.models import PluginConfigInstance, PluginStateOverride
from app.modules.plugin.schemas import PluginMountCreate, PluginMountUpdate
from app.modules.plugin.service import (
    PluginServiceError,
    delete_household_plugin_installation,
    delete_plugin_mount,
    get_household_plugin,
    install_plugin_package,
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
        self._previous_plugin_storage_root = settings.plugin_storage_root
        self._previous_plugin_dev_root = settings.plugin_dev_root
        settings.plugin_storage_root = self._tempdir.name
        settings.plugin_dev_root = str((Path(self._tempdir.name) / "plugins-dev").resolve())

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
        settings.plugin_storage_root = self._previous_plugin_storage_root
        settings.plugin_dev_root = self._previous_plugin_dev_root
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
                str((self._plugin_storage_root() / "third_party" / "local" / household.id).resolve()),
                str(Path(created.plugin_root).resolve()),
            )

            mounted = list_plugin_mounts(self.db, household_id=household.id)
            self.assertEqual(1, len(mounted))
            self.assertEqual("third-party-sync-plugin", mounted[0].plugin_id)

            snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
            mounted_plugin = next(item for item in snapshot.items if item.id == "third-party-sync-plugin")
            self.assertEqual("third_party", mounted_plugin.source_type)
            self.assertEqual("local", mounted_plugin.install_method)
            self.assertEqual("subprocess_runner", mounted_plugin.execution_backend)
            self.assertFalse(mounted_plugin.is_dev_active)

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
                        "types": ["integration"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "integration": "plugin.integration.sync",
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

    def test_plugins_dev_overrides_installed_third_party_plugin_and_survives_installation_delete(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Dev Override Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        mounted_root = self._create_plugin_fixture(Path(self._tempdir.name), plugin_id="dev-shadow-plugin", version="1.0.0")
        register_plugin_mount(
            self.db,
            household_id=household.id,
            payload=PluginMountCreate(
                source_type="third_party",
                install_method="local",
                plugin_root=str(mounted_root),
                python_path=sys.executable,
                working_dir=str(mounted_root),
                timeout_seconds=20,
            ),
        )
        self.db.flush()

        dev_root = self._create_plugin_fixture(
            Path(settings.plugin_dev_root),
            plugin_id="dev-shadow-plugin",
            version="9.9.9",
            name="Dev Shadow Plugin",
        )

        plugin = get_household_plugin(self.db, household_id=household.id, plugin_id="dev-shadow-plugin")
        self.assertEqual("9.9.9", plugin.version)
        self.assertEqual("third_party", plugin.source_type)
        self.assertEqual("local", plugin.install_method)
        self.assertTrue(plugin.is_dev_active)
        assert plugin.runner_config is not None
        self.assertEqual(str(dev_root.resolve()), str(Path(plugin.runner_config.plugin_root).resolve()))
        self.assertEqual(str((dev_root / "manifest.json").resolve()), str(Path(plugin.manifest_path).resolve()))

        delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="dev-shadow-plugin")
        self.db.commit()

        self.assertEqual([], list_plugin_mounts(self.db, household_id=household.id))
        plugin_after_delete = get_household_plugin(self.db, household_id=household.id, plugin_id="dev-shadow-plugin")
        assert plugin_after_delete.runner_config is not None
        self.assertEqual("9.9.9", plugin_after_delete.version)
        self.assertTrue(plugin_after_delete.is_dev_active)
        self.assertEqual(str(dev_root.resolve()), str(Path(plugin_after_delete.runner_config.plugin_root).resolve()))
        self.assertTrue(dev_root.exists())

    def test_plugins_dev_cannot_override_builtin_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Builtin Priority Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        builtin_snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
        builtin_plugin = next(item for item in builtin_snapshot.items if item.source_type == "builtin")
        self._create_plugin_fixture(
            Path(settings.plugin_dev_root),
            plugin_id=builtin_plugin.id,
            version="9.9.9",
            name="Builtin Shadow Attempt",
        )

        current = get_household_plugin(self.db, household_id=household.id, plugin_id=builtin_plugin.id)
        self.assertEqual("builtin", current.source_type)
        self.assertFalse(current.is_dev_active)
        self.assertEqual(str(Path(builtin_plugin.manifest_path).resolve()), str(Path(current.manifest_path).resolve()))
        self.assertFalse(str(Path(current.manifest_path).resolve()).startswith(str(Path(settings.plugin_dev_root).resolve())))

    def test_install_plugin_package_creates_manual_release_mount_with_subprocess_runner(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Install Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        result = install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.flush()

        self.assertEqual("installed", result.install_action)
        self.assertFalse(result.overwritten)
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertEqual("third_party", result.source_type)
        plugin_root = Path(result.plugin_root).resolve()
        self.assertTrue(plugin_root.is_relative_to(self._plugin_storage_root()))
        self.assertEqual("zip-sync-plugin", plugin_root.parent.name)
        self.assertIn("--", plugin_root.name)

        mounts = list_plugin_mounts(self.db, household_id=household.id)
        self.assertEqual(1, len(mounts))
        self.assertEqual(result.plugin_root, mounts[0].plugin_root)
        self.assertEqual("subprocess_runner", mounts[0].execution_backend)
        self.assertFalse(mounts[0].enabled)

        plugin = get_household_plugin(self.db, household_id=household.id, plugin_id="zip-sync-plugin")
        self.assertEqual("1.0.0", plugin.version)
        self.assertEqual("third_party", plugin.source_type)
        self.assertEqual("subprocess_runner", plugin.execution_backend)
        self.assertFalse(plugin.enabled)

    def test_install_plugin_package_overwrite_upgrade_updates_mount_to_new_release(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Upgrade Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        first_result = install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.flush()

        second_result = install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.1.0"),
            overwrite=True,
        )
        self.db.flush()

        self.assertEqual("upgraded", second_result.install_action)
        self.assertTrue(second_result.overwritten)
        self.assertEqual("1.0.0", second_result.previous_version)
        self.assertEqual("subprocess_runner", second_result.execution_backend)
        self.assertNotEqual(first_result.plugin_root, second_result.plugin_root)

        mounts = list_plugin_mounts(self.db, household_id=household.id)
        self.assertEqual(1, len(mounts))
        self.assertEqual(second_result.plugin_root, mounts[0].plugin_root)
        self.assertEqual("subprocess_runner", mounts[0].execution_backend)

        plugin = get_household_plugin(self.db, household_id=household.id, plugin_id="zip-sync-plugin")
        self.assertEqual("1.1.0", plugin.version)
        self.assertEqual("subprocess_runner", plugin.execution_backend)

    def test_install_plugin_package_requires_overwrite_for_existing_manual_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Conflict Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            install_plugin_package(
                self.db,
                household_id=household.id,
                file_name="zip-sync-plugin.zip",
                content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.1.0"),
            )

        self.assertEqual("plugin_package_conflict", ctx.exception.error_code)
        self.assertEqual("overwrite", ctx.exception.field)

    def test_install_plugin_package_rejects_marketplace_managed_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Marketplace Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        marketplace_root = (Path(self._tempdir.name) / "marketplace" / "marketplace-plugin" / "1.0.0").resolve()
        marketplace_root.mkdir(parents=True, exist_ok=True)
        manifest_path = marketplace_root / "manifest.json"
        manifest_path.write_text("{}", encoding="utf-8")
        self.db.add(
            PluginMarketplaceInstance(
                id=new_uuid(),
                household_id=household.id,
                source_id="marketplace-source-001",
                plugin_id="marketplace-plugin",
                installed_version="1.0.0",
                install_status="installed",
                enabled=False,
                config_status="configured",
                source_repo="https://github.com/demo/marketplace-plugin",
                market_repo="https://github.com/demo/marketplace",
                plugin_root=str(marketplace_root),
                manifest_path=str(manifest_path),
                python_path=sys.executable,
                working_dir=str(marketplace_root),
                installed_at=utc_now_iso(),
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            install_plugin_package(
                self.db,
                household_id=household.id,
                file_name="marketplace-plugin.zip",
                content=self._build_plugin_archive(plugin_id="marketplace-plugin", version="2.0.0"),
                overwrite=True,
            )

        self.assertEqual("plugin_source_mismatch", ctx.exception.error_code)
        self.assertEqual("plugin_id", ctx.exception.field)
        self.assertIn("插件市场管理", str(ctx.exception))

    def test_delete_household_plugin_installation_removes_manual_installation_state_and_files(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Delete Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        result = install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.flush()

        self.db.add(
            PluginConfigInstance(
                id=new_uuid(),
                household_id=household.id,
                plugin_id="zip-sync-plugin",
                scope_type="plugin",
                scope_key="default",
                schema_version=1,
                data_json='{"token":"demo"}',
                secret_data_encrypted=None,
                updated_by="test-suite",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.add(
            PluginStateOverride(
                id=new_uuid(),
                household_id=household.id,
                plugin_id="zip-sync-plugin",
                enabled=True,
                source_type="third_party",
                updated_by="test-suite",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.flush()

        plugin_root = Path(result.plugin_root).resolve()
        plugin_id_root = plugin_root.parent

        delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="zip-sync-plugin")
        self.db.commit()

        self.assertEqual([], list_plugin_mounts(self.db, household_id=household.id))
        self.assertEqual(
            [],
            plugin_repository.list_plugin_config_instances(
                self.db,
                household_id=household.id,
                plugin_id="zip-sync-plugin",
            ),
        )
        self.assertIsNone(
            plugin_repository.get_plugin_state_override(
                self.db,
                household_id=household.id,
                plugin_id="zip-sync-plugin",
            )
        )
        self.assertFalse(plugin_id_root.exists())

        with self.assertRaises(PluginServiceError) as ctx:
            get_household_plugin(self.db, household_id=household.id, plugin_id="zip-sync-plugin")
        self.assertEqual("plugin_not_visible_in_household", ctx.exception.error_code)

    def test_delete_household_plugin_installation_blocks_when_integration_instance_exists(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Integration Block Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.add(
            IntegrationInstance(
                id=new_uuid(),
                household_id=household.id,
                plugin_id="zip-sync-plugin",
                display_name="Weather Sync",
                status="ready",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="zip-sync-plugin")

        self.assertEqual("plugin_in_use", ctx.exception.error_code)
        self.assertEqual("1", ctx.exception.field_errors.get("integration_instances"))

    def test_delete_household_plugin_installation_blocks_when_channel_account_exists(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Channel Block Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.add(
            ChannelPluginAccount(
                id=new_uuid(),
                household_id=household.id,
                plugin_id="zip-sync-plugin",
                platform_code="telegram",
                account_code="telegram-main",
                display_name="Telegram Main",
                connection_mode="webhook",
                config_json="{}",
                status="ready",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="zip-sync-plugin")

        self.assertEqual("plugin_in_use", ctx.exception.error_code)
        self.assertEqual("1", ctx.exception.field_errors.get("channel_accounts"))

    def test_delete_household_plugin_installation_blocks_when_device_binding_exists(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Device Block Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        device = Device(
            id=new_uuid(),
            household_id=household.id,
            room_id=None,
            name="Bedroom Light",
            device_type="light",
            vendor="demo",
            status="active",
            controllable=1,
            voice_auto_takeover_enabled=0,
            voiceprint_identity_enabled=0,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        self.db.add(device)
        self.db.flush()
        self.db.add(
            DeviceBinding(
                id=new_uuid(),
                device_id=device.id,
                integration_instance_id=None,
                platform="demo",
                external_entity_id="light.bedroom",
                external_device_id="device.bedroom-light",
                plugin_id="zip-sync-plugin",
                binding_version=1,
                capabilities='["on","off"]',
                last_sync_at=utc_now_iso(),
            )
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="zip-sync-plugin")

        self.assertEqual("plugin_in_use", ctx.exception.error_code)
        self.assertEqual("1", ctx.exception.field_errors.get("device_bindings"))

    def test_delete_household_plugin_installation_blocks_when_integration_discovery_exists(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="ZIP Discovery Block Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        install_plugin_package(
            self.db,
            household_id=household.id,
            file_name="zip-sync-plugin.zip",
            content=self._build_plugin_archive(plugin_id="zip-sync-plugin", version="1.0.0"),
        )
        self.db.add(
            IntegrationDiscovery(
                id=new_uuid(),
                household_id=household.id,
                integration_instance_id=None,
                plugin_id="zip-sync-plugin",
                gateway_id=None,
                discovery_key="demo-gateway:device-001",
                discovery_type="device",
                resource_type="device",
                status="pending",
                title="Living Room Sensor",
                subtitle=None,
                external_device_id="device-001",
                external_entity_id="sensor.living_room",
                adapter_type=None,
                capability_tags_json='["sensor"]',
                metadata_json="{}",
                payload_json="{}",
                claimed_device_id=None,
                discovered_at=utc_now_iso(),
                last_seen_at=utc_now_iso(),
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            delete_household_plugin_installation(self.db, household_id=household.id, plugin_id="zip-sync-plugin")

        self.assertEqual("plugin_in_use", ctx.exception.error_code)
        self.assertEqual("1", ctx.exception.field_errors.get("integration_discoveries"))

    def test_delete_household_plugin_installation_rejects_builtin_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Builtin Delete Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        builtin_snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
        builtin_plugin = next(item for item in builtin_snapshot.items if item.source_type == "builtin")

        with self.assertRaises(PluginServiceError) as ctx:
            delete_household_plugin_installation(self.db, household_id=household.id, plugin_id=builtin_plugin.id)

        self.assertEqual("plugin_builtin_delete_forbidden", ctx.exception.error_code)

    def _create_third_party_plugin(
        self,
        root: Path,
        *,
        plugin_id: str,
        version: str = "0.1.0",
        name: str = "第三方插件",
    ) -> Path:
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
                    "types": ["integration"],
                    "permissions": ["health.read", "memory.write.observation"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "integration": "plugin.integration.sync",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n    return {'records': []}\n",
            encoding="utf-8",
        )
        (package_dir / "ingestor.py").write_text(
            "def transform(payload=None):\n    return []\n",
            encoding="utf-8",
        )
        return plugin_root

    def _create_plugin_fixture(
        self,
        root: Path,
        *,
        plugin_id: str,
        version: str = "0.1.0",
        name: str = "Third Party Plugin",
    ) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": name,
                    "version": version,
                    "types": ["integration"],
                    "permissions": ["health.read", "memory.write.observation"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "integration": "plugin.integration.sync",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n    return {'records': []}\n",
            encoding="utf-8",
        )
        (package_dir / "ingestor.py").write_text(
            "def transform(payload=None):\n    return []\n",
            encoding="utf-8",
        )
        return plugin_root

    def _build_plugin_archive(self, *, plugin_id: str, version: str) -> bytes:
        manifest = {
            "id": plugin_id,
            "name": f"{plugin_id} Plugin",
            "version": version,
            "types": ["integration"],
            "permissions": ["health.read", "memory.write.observation"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive_root = f"{plugin_id}-{version}"
            archive.writestr(f"{archive_root}/manifest.json", json.dumps(manifest, ensure_ascii=False))
            archive.writestr(f"{archive_root}/plugin/__init__.py", "")
            archive.writestr(
                f"{archive_root}/plugin/integration.py",
                "def sync(payload=None):\n    return {'records': []}\n",
            )
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
