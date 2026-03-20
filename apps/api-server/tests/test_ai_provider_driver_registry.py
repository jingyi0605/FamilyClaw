import json
import tempfile
import unittest
from pathlib import Path

from app.modules.plugin.service import list_registered_plugins


class AiProviderDriverRegistryTests(unittest.TestCase):
    def _write_ai_provider_resources(self, root: Path) -> None:
        resources_dir = root / "resources"
        resources_dir.mkdir(parents=True, exist_ok=True)
        (resources_dir / "logo.svg").write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'></svg>",
            encoding="utf-8",
        )
        (resources_dir / "description.json").write_text(
            json.dumps({"zh-CN": "provider description"}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_resolve_driver_from_plugin_entrypoint(self) -> None:
        from app.modules.ai_gateway.provider_driver import resolve_ai_provider_driver

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = Path(tempdir) / "demo_ai_provider"
            package_dir = plugin_root / "plugin"
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "driver.py").write_text(
                "class DemoDriver:\n"
                "    def __init__(self):\n"
                "        self.driver_name = 'demo-driver'\n"
                "\n"
                "    def invoke(self, **kwargs):\n"
                "        return None\n"
                "\n"
                "    async def ainvoke(self, **kwargs):\n"
                "        return None\n"
                "\n"
                "    async def stream(self, **kwargs):\n"
                "        if False:\n"
                "            yield ''\n"
                "\n"
                "def build_driver(plugin):\n"
                "    return DemoDriver()\n",
                encoding="utf-8",
            )
            self._write_ai_provider_resources(plugin_root)
            (plugin_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "id": "demo-ai-provider",
                        "name": "Demo AI Provider",
                        "version": "0.1.0",
                        "types": ["ai-provider"],
                        "permissions": [],
                        "risk_level": "low",
                        "triggers": [],
                        "entrypoints": {"ai_provider": "plugin.driver.build_driver"},
                        "capabilities": {
                            "ai_provider": {
                                "adapter_code": "demo-ai-provider",
                                "display_name": "Demo AI Provider",
                                "branding": {
                                    "logo_resource": "resources/logo.svg",
                                    "description_resource": "resources/description.json",
                                },
                                "field_schema": [
                                    {
                                        "key": "secret_ref",
                                        "label": "API Key",
                                        "field_type": "secret",
                                        "required": True,
                                        "options": [],
                                    }
                                ],
                                "config_ui": {
                                    "field_order": ["secret_ref"],
                                    "sections": [
                                        {
                                            "key": "connection",
                                            "title": "Connection",
                                            "fields": ["secret_ref"],
                                        }
                                    ],
                                    "actions": [],
                                },
                                "model_discovery": {
                                    "enabled": False,
                                    "action_key": None,
                                    "depends_on_fields": [],
                                    "target_field": None,
                                    "debounce_ms": 500,
                                    "empty_state_text": None,
                                    "discovery_hint_text": None,
                                    "discovering_text": None,
                                    "discovered_text_template": None,
                                },
                                "supported_model_types": ["llm"],
                                "llm_workflow": "openai_chat_completions",
                                "runtime_capability": {
                                    "transport_type": "openai_compatible",
                                    "api_family": "openai_chat_completions",
                                    "default_privacy_level": "public_cloud",
                                    "default_supported_capabilities": ["text"],
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            registry = list_registered_plugins(plugin_root.parent)
            plugin = next(item for item in registry.items if item.id == "demo-ai-provider")

        driver = resolve_ai_provider_driver(plugin)
        self.assertEqual("demo-driver", getattr(driver, "driver_name", None))

    def test_builtin_ai_provider_entry_comes_from_plugin_directory(self) -> None:
        builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        registry = list_registered_plugins(builtin_root)

        plugin = next(item for item in registry.items if item.id == "builtin.provider.chatgpt")
        expected_manifest = builtin_root / "ai_provider_chatgpt" / "manifest.json"

        self.assertEqual(["ai-provider"], plugin.types)
        self.assertEqual(expected_manifest.resolve(), Path(plugin.manifest_path).resolve())
        self.assertEqual(
            "app.plugins.builtin.ai_provider_chatgpt.driver.build_driver",
            plugin.entrypoints.ai_provider,
        )


if __name__ == "__main__":
    unittest.main()
