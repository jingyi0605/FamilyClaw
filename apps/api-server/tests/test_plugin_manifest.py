import json
import tempfile
import unittest
from pathlib import Path

from app.modules.plugin.service import (
    PluginManifestValidationError,
    disable_plugin,
    discover_plugin_manifests,
    enable_plugin,
    execute_plugin,
    list_registered_plugins,
    load_plugin_manifest,
)
from app.modules.plugin.schemas import PluginExecutionRequest


class PluginManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

    def test_load_valid_manifest(self) -> None:
        manifest = load_plugin_manifest(
            self.builtin_root / "health_basic" / "manifest.json"
        )

        self.assertEqual("health-basic-reader", manifest.id)
        self.assertEqual(["connector", "memory-ingestor"], manifest.types)
        self.assertEqual("app.plugins.builtin.health_basic.ingestor.transform", manifest.entrypoints.memory_ingestor)

    def test_reject_manifest_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-plugin",
                        "name": "坏插件",
                        "types": ["connector"],
                        "permissions": ["device.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"connector": "app.plugins.demo.connector.sync"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("version", str(context.exception))

    def test_discover_builtin_manifests(self) -> None:
        manifests = discover_plugin_manifests(self.builtin_root)

        manifest_ids = {item.id for item in manifests}
        self.assertEqual(2, len(manifests))
        self.assertIn("homeassistant-device-sync", manifest_ids)
        self.assertIn("health-basic-reader", manifest_ids)

    def test_list_registered_plugins_defaults_to_enabled(self) -> None:
        snapshot = list_registered_plugins(self.builtin_root)

        self.assertEqual(2, len(snapshot.items))
        self.assertTrue(all(item.enabled for item in snapshot.items))

    def test_disable_and_enable_plugin_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            state_file = Path(tempdir) / "plugin_registry_state.json"

            disabled = disable_plugin(
                "health-basic-reader",
                root_dir=self.builtin_root,
                state_file=state_file,
            )
            self.assertFalse(disabled.enabled)

            disabled_snapshot = list_registered_plugins(self.builtin_root, state_file=state_file)
            disabled_item = next(item for item in disabled_snapshot.items if item.id == "health-basic-reader")
            self.assertFalse(disabled_item.enabled)

            enabled = enable_plugin(
                "health-basic-reader",
                root_dir=self.builtin_root,
                state_file=state_file,
            )
            self.assertTrue(enabled.enabled)

            enabled_snapshot = list_registered_plugins(self.builtin_root, state_file=state_file)
            enabled_item = next(item for item in enabled_snapshot.items if item.id == "health-basic-reader")
            self.assertTrue(enabled_item.enabled)

    def test_execute_plugin_returns_success_result(self) -> None:
        result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual("health-basic-reader", result.output["source"])
        self.assertEqual("mom", result.output["member_id"])

    def test_execute_plugin_returns_failure_when_plugin_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            state_file = Path(tempdir) / "plugin_registry_state.json"
            disable_plugin("health-basic-reader", root_dir=self.builtin_root, state_file=state_file)

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="health-basic-reader",
                    plugin_type="connector",
                    payload={},
                ),
                root_dir=self.builtin_root,
                state_file=state_file,
            )

        self.assertFalse(result.success)
        self.assertEqual("plugin_execution_failed", result.error_code)
        self.assertIn("已禁用", result.error_message or "")

    def test_execute_plugin_returns_failure_when_handler_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_dir = root / "broken"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "broken-runtime-plugin",
                        "name": "运行失败插件",
                        "version": "0.1.0",
                        "types": ["connector"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "connector": "app.plugins.builtin.health_basic.connector.fail_sync"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="broken-runtime-plugin",
                    plugin_type="connector",
                    payload={},
                ),
                root_dir=root,
            )

        self.assertFalse(result.success)
        self.assertEqual("plugin_execution_failed", result.error_code)
        self.assertIn("demo plugin failure", result.error_message or "")

    def test_stage1_framework_checkpoint_smoke(self) -> None:
        registry = list_registered_plugins(self.builtin_root)
        self.assertGreaterEqual(len(registry.items), 2)

        health_plugin = next(item for item in registry.items if item.id == "health-basic-reader")
        self.assertTrue(health_plugin.enabled)
        self.assertIn("connector", health_plugin.types)

        success_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "dad"},
            ),
            root_dir=self.builtin_root,
        )
        self.assertTrue(success_result.success)
        self.assertEqual("health-basic-reader", success_result.plugin_id)

        failure_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="not-exists-plugin",
                plugin_type="connector",
                payload={},
            ),
            root_dir=self.builtin_root,
        )
        self.assertFalse(failure_result.success)
        self.assertEqual("plugin_execution_failed", failure_result.error_code)
        self.assertIn("插件不存在", failure_result.error_message or "")
