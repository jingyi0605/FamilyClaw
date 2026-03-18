import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app.modules.plugin.service as plugin_service
from app.modules.region.plugin_runtime import region_provider_registry, sync_household_plugin_region_providers


class PluginFaultIsolationTests(unittest.TestCase):
    def _write_manifest(self, root: Path, folder: str, payload: dict) -> Path:
        plugin_dir = root / folder
        plugin_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = plugin_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return manifest_path

    def test_list_plugin_mounts_skips_invalid_manifest_and_logs_error(self) -> None:
        plugin_service._REPORTED_PLUGIN_REGISTRY_ISSUES.clear()
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(
                Path(tempdir),
                "broken_mount",
                {
                    "id": "broken_mount",
                    "name": "坏挂载插件",
                    "version": "0.1.0",
                    "types": ["integration"],
                    "permissions": ["health.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"integration": "plugin.integration.sync"},
                },
            )
            mount = SimpleNamespace(
                plugin_id="broken-mount",
                manifest_path=str(manifest_path),
            )

            with patch("app.modules.household.service.get_household_or_404", return_value=None), patch(
                "app.modules.plugin.service.repository.list_plugin_mounts",
                return_value=[mount],
            ), patch.object(plugin_service.logger, "error") as error_mock:
                items = plugin_service.list_plugin_mounts(object(), household_id="demo-household")

        self.assertEqual([], items)
        error_mock.assert_called_once()
        message = error_mock.call_args.args[0]
        self.assertIn("list_plugin_mounts", message)
        self.assertIn("broken-mount", message)

    def test_list_registered_plugin_locales_skips_invalid_resource_and_logs_error(self) -> None:
        plugin_service._REPORTED_PLUGIN_REGISTRY_ISSUES.clear()
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest_path = self._write_manifest(
                root,
                "broken_locale_pack",
                {
                    "id": "broken-locale-pack",
                    "name": "坏语言包",
                    "version": "0.1.0",
                    "types": ["locale-pack"],
                    "permissions": ["locale.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                },
            )
            (manifest_path.parent / "zh-CN.json").write_text("{", encoding="utf-8")
            plugin = SimpleNamespace(
                id="broken-locale-pack",
                enabled=True,
                types=["locale-pack"],
                manifest_path=str(manifest_path),
                source_type="builtin",
                locales=[
                    SimpleNamespace(
                        id="zh-CN",
                        label="简体中文",
                        native_label="简体中文",
                        fallback=None,
                        resource="zh-CN.json",
                    )
                ],
            )
            snapshot = SimpleNamespace(items=[plugin])

            with patch(
                "app.modules.plugin.service.list_registered_plugins_for_household",
                return_value=snapshot,
            ), patch.object(plugin_service.logger, "error") as error_mock:
                result = plugin_service.list_registered_plugin_locales_for_household(
                    object(),
                    household_id="demo-household",
                )

        self.assertEqual([], result.items)
        error_mock.assert_called_once()
        message = error_mock.call_args.args[0]
        self.assertIn("broken-locale-pack", message)
        self.assertIn("zh-CN", message)

    def test_sync_household_plugin_region_providers_skips_invalid_manifest_and_does_not_raise(self) -> None:
        plugin_service._REPORTED_PLUGIN_REGISTRY_ISSUES.clear()
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(
                Path(tempdir),
                "broken_region_provider",
                {
                    "id": "broken_region_provider",
                    "name": "坏地区插件",
                    "version": "0.1.0",
                    "types": ["region-provider"],
                    "permissions": ["region.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"region_provider": "plugin.region.handle"},
                    "capabilities": {
                        "region_provider": {
                            "provider_code": "plugin.jp-sample",
                            "country_codes": ["JP"],
                            "entrypoint": "plugin.region.handle",
                            "reserved": False,
                        }
                    },
                },
            )
            mount = SimpleNamespace(
                plugin_id="broken-region-provider",
                manifest_path=str(manifest_path),
                plugin_root=str(manifest_path.parent),
                python_path="python",
                working_dir=str(manifest_path.parent),
                timeout_seconds=20,
                stdout_limit_bytes=65536,
                stderr_limit_bytes=65536,
            )
            snapshot = SimpleNamespace(items=[SimpleNamespace(id="broken-region-provider", enabled=True)])

            with patch(
                "app.modules.plugin.service.list_registered_plugins_for_household",
                return_value=snapshot,
            ), patch(
                "app.modules.region.plugin_runtime.plugin_repository.list_plugin_mounts",
                return_value=[mount],
            ), patch.object(region_provider_registry, "clear_scope") as clear_scope_mock, patch.object(
                region_provider_registry,
                "register",
            ) as register_mock, patch.object(plugin_service.logger, "error") as error_mock:
                sync_household_plugin_region_providers(object(), "demo-household")

        clear_scope_mock.assert_called_once_with("demo-household")
        register_mock.assert_not_called()
        error_mock.assert_called_once()
        message = error_mock.call_args.args[0]
        self.assertIn("sync_household_plugin_region_providers", message)
        self.assertIn("broken-region-provider", message)


if __name__ == "__main__":
    unittest.main()

