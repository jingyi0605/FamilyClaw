import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
from app.modules.plugin.schemas import PluginRunnerConfig


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

    def test_load_locale_pack_manifest_without_entrypoints(self) -> None:
        manifest = load_plugin_manifest(
            self.builtin_root / "locale_zh_tw_pack" / "manifest.json"
        )

        self.assertEqual("locale-zh-tw", manifest.id)
        self.assertEqual(["locale-pack"], manifest.types)
        self.assertEqual(1, len(manifest.locales))
        self.assertEqual("zh-TW", manifest.locales[0].id)
        self.assertIsNone(manifest.entrypoints.connector)

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

    def test_manifest_accepts_region_context_capability_and_reserved_region_provider_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "region-context-plugin",
                        "name": "地区上下文插件",
                        "version": "0.1.0",
                        "types": ["connector"],
                        "permissions": ["region.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"connector": "plugin.connector.sync"},
                        "capabilities": {
                            "context_reads": {"household_region_context": True},
                            "region_provider": {
                                "provider_code": "plugin.future-region-provider",
                                "country_codes": ["JP", "US"],
                                "entrypoint": "plugin.region_provider.build",
                                "reserved": True,
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = load_plugin_manifest(manifest_path)

        self.assertTrue(manifest.capabilities.context_reads.household_region_context)
        assert manifest.capabilities.region_provider is not None
        self.assertEqual("plugin.future-region-provider", manifest.capabilities.region_provider.provider_code)
        self.assertEqual(["JP", "US"], manifest.capabilities.region_provider.country_codes)

    def test_manifest_accepts_runtime_region_provider_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "jp-region-provider",
                        "name": "日本地区提供方",
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

            manifest = load_plugin_manifest(manifest_path)

        self.assertEqual(["region-provider"], manifest.types)
        self.assertEqual("plugin.region_provider.handle", manifest.entrypoints.region_provider)

    def test_reject_runtime_region_provider_without_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-jp-region-provider",
                        "name": "坏地区提供方",
                        "version": "0.1.0",
                        "types": ["region-provider"],
                        "permissions": ["region.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {"region_provider": "plugin.region_provider.handle"},
                        "capabilities": {
                            "region_provider": {
                                "provider_code": "plugin.jp-sample",
                                "country_codes": [],
                                "entrypoint": "plugin.region_provider.handle",
                                "reserved": False,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("至少要声明一个 country_code", str(context.exception))

    def test_discover_builtin_manifests(self) -> None:
        manifests = discover_plugin_manifests(self.builtin_root)

        manifest_ids = {item.id for item in manifests}
        self.assertGreaterEqual(len(manifests), 2)
        self.assertIn("homeassistant-device-sync", manifest_ids)
        self.assertIn("health-basic-reader", manifest_ids)
        self.assertIn("locale-zh-tw", manifest_ids)

    def test_list_registered_plugins_defaults_to_enabled(self) -> None:
        snapshot = list_registered_plugins(self.builtin_root)

        self.assertGreaterEqual(len(snapshot.items), 2)
        self.assertTrue(all(item.enabled for item in snapshot.items))
        locale_pack = next(item for item in snapshot.items if item.id == "locale-zh-tw")
        self.assertEqual(["locale-pack"], locale_pack.types)
        self.assertEqual("zh-TW", locale_pack.locales[0].id)

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

    def test_execute_plugin_marks_builtin_backend_as_in_process(self) -> None:
        result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": "mom"},
            ),
            root_dir=self.builtin_root,
        )

        self.assertTrue(result.success)
        self.assertEqual("in_process", result.execution_backend)

    def test_execute_plugin_dispatches_to_subprocess_runner_for_third_party_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_root = root / "demo_plugin"
            package_dir = plugin_root / "plugin"
            package_dir.mkdir(parents=True)

            (plugin_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "demo-third-party-plugin",
                        "name": "第三方演示插件",
                        "version": "0.1.0",
                        "types": ["connector"],
                        "permissions": ["health.read"],
                        "risk_level": "low",
                        "triggers": ["manual"],
                        "entrypoints": {
                            "connector": "plugin.connector.sync"
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "connector.py").write_text(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    return {\n"
                "        'source': 'demo-third-party-plugin',\n"
                "        'mode': 'connector',\n"
                "        'echo': data,\n"
                "        'records': []\n"
                "    }\n",
                encoding="utf-8",
            )

            result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="demo-third-party-plugin",
                    plugin_type="connector",
                    payload={"member_id": "member-001"},
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
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual("demo-third-party-plugin", result.output["source"])
        self.assertEqual("member-001", result.output["echo"]["member_id"])

    def test_execute_plugin_returns_timeout_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_connector_plugin(Path(tempdir), plugin_id="runner-timeout-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd=[sys.executable], timeout=1)

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-timeout-plugin",
                        plugin_type="connector",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("subprocess_runner", result.execution_backend)
        self.assertEqual("plugin_runner_timeout", result.error_code)

    def test_execute_plugin_returns_invalid_output_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_connector_plugin(Path(tempdir), plugin_id="runner-invalid-json-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[sys.executable, "-m", "app.modules.plugin.runner_protocol"],
                    returncode=0,
                    stdout="not-json",
                    stderr="",
                )

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-invalid-json-plugin",
                        plugin_type="connector",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("plugin_runner_invalid_output", result.error_code)

    def test_execute_plugin_returns_dependency_missing_error_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_connector_plugin(Path(tempdir), plugin_id="runner-missing-dependency-plugin")

            with patch("app.modules.plugin.executors.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[sys.executable, "-m", "app.modules.plugin.runner_protocol"],
                    returncode=1,
                    stdout="",
                    stderr="ModuleNotFoundError: No module named 'missing_dependency'",
                )

                result = execute_plugin(
                    PluginExecutionRequest(
                        plugin_id="runner-missing-dependency-plugin",
                        plugin_type="connector",
                        payload={},
                    ),
                    root_dir=plugin_root,
                    source_type="third_party",
                    runner_config=PluginRunnerConfig(
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=1,
                    ),
                )

        self.assertFalse(result.success)
        self.assertEqual("plugin_runner_dependency_missing", result.error_code)

    def test_ingest_plugin_raw_records_to_memory_uses_subprocess_runner_for_third_party_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_sync_plugin(Path(tempdir), plugin_id="third-party-sync-plugin")

            connector_result = execute_plugin(
                PluginExecutionRequest(
                    plugin_id="third-party-sync-plugin",
                    plugin_type="connector",
                    payload={"member_id": "member-001"},
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

            self.assertTrue(connector_result.success)

    def _create_third_party_connector_plugin(self, root: Path, *, plugin_id: str) -> Path:
        return self._create_third_party_plugin(
            root,
            plugin_id=plugin_id,
            connector_body=(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    return {\n"
                "        'source': '" + plugin_id + "',\n"
                "        'mode': 'connector',\n"
                "        'echo': data,\n"
                "        'records': []\n"
                "    }\n"
            ),
        )

    def _create_third_party_sync_plugin(self, root: Path, *, plugin_id: str) -> Path:
        return self._create_third_party_plugin(
            root,
            plugin_id=plugin_id,
            plugin_types=["connector", "memory-ingestor"],
            entrypoints={
                "connector": "plugin.connector.sync",
                "memory_ingestor": "plugin.ingestor.transform",
            },
            connector_body=(
                "def sync(payload=None):\n"
                "    data = payload or {}\n"
                "    member_id = data.get('member_id', 'member-001')\n"
                "    return {\n"
                "        'source': '" + plugin_id + "',\n"
                "        'records': [\n"
                "            {\n"
                "                'record_type': 'steps',\n"
                "                'member_id': member_id,\n"
                "                'value': 42,\n"
                "                'unit': 'count',\n"
                "                'captured_at': '2026-03-13T07:30:00Z'\n"
                "            }\n"
                "        ]\n"
                "    }\n"
            ),
            ingestor_body=(
                "def transform(payload=None):\n"
                "    data = payload or {}\n"
                "    records = data.get('records', [])\n"
                "    if not records:\n"
                "        return []\n"
                "    record = records[0]\n"
                "    source = record.get('payload', {})\n"
                "    return [\n"
                "        {\n"
                "            'type': 'Observation',\n"
                "            'subject_type': 'Person',\n"
                "            'subject_id': source.get('member_id'),\n"
                "            'category': 'daily_steps',\n"
                "            'value': source.get('value'),\n"
                "            'unit': source.get('unit'),\n"
                "            'observed_at': record.get('captured_at'),\n"
                "            'source_plugin_id': '" + plugin_id + "',\n"
                "            'source_record_ref': record.get('id')\n"
                "        }\n"
                "    ]\n"
            ),
        )

    def _create_third_party_plugin(
        self,
        root: Path,
        *,
        plugin_id: str,
        plugin_types: list[str] | None = None,
        entrypoints: dict[str, str] | None = None,
        connector_body: str | None = None,
        ingestor_body: str | None = None,
    ) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)

        manifest = {
            "id": plugin_id,
            "name": f"{plugin_id}-name",
            "version": "0.1.0",
            "types": plugin_types or ["connector"],
            "permissions": ["health.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": entrypoints or {"connector": "plugin.connector.sync"},
        }
        (plugin_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        if connector_body is not None:
            (package_dir / "connector.py").write_text(connector_body, encoding="utf-8")
        if ingestor_body is not None:
            (package_dir / "ingestor.py").write_text(ingestor_body, encoding="utf-8")
        return plugin_root

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

    def test_reject_locale_pack_manifest_without_locales(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = Path(tempdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "id": "broken-locale-pack",
                        "name": "坏语言包",
                        "version": "0.1.0",
                        "types": ["locale-pack"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("至少要声明一个 locale", str(context.exception))

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
