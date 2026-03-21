import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.ai_gateway.schemas import AiProviderProfileCreate
from app.modules.ai_gateway.service import (
    AiGatewayConfigurationError,
    create_provider_profile,
    list_provider_adapters_for_household,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import list_plugin_mounts, list_registered_plugins_for_household, register_plugin_mount


class AiProviderOfficialPluginTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_plugin_dev_root = settings.plugin_dev_root
        settings.plugin_dev_root = str((Path(self._tempdir.name) / "plugins-dev").resolve())
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        settings.plugin_dev_root = self._previous_plugin_dev_root
        self._tempdir.cleanup()

    def test_household_provider_adapters_include_mounted_official_coding_plan_plugins(self) -> None:
        household = self._create_household()

        self._mount_official_plugin(household.id, "ai_provider_bailian_coding_plan")
        self._mount_official_plugin(household.id, "ai_provider_kimi_coding_plan")
        self._mount_official_plugin(household.id, "ai_provider_glm_coding_plan")

        snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
        official_plugins = {
            item.id: item
            for item in snapshot.items
            if item.id in {
                "ai-provider-bailian-coding-plan",
                "ai-provider-kimi-coding-plan",
                "ai-provider-glm-coding-plan",
            }
        }
        self.assertEqual(
            {
                "ai-provider-bailian-coding-plan",
                "ai-provider-kimi-coding-plan",
                "ai-provider-glm-coding-plan",
            },
            set(official_plugins),
        )
        self.assertTrue(all(item.source_type == "third_party" for item in official_plugins.values()))
        self.assertTrue(all(item.install_method == "local" for item in official_plugins.values()))
        mounted_roots = [item.plugin_root for item in list_plugin_mounts(self.db, household_id=household.id)]
        expected_prefix = str(
            (Path(settings.plugin_storage_root).resolve() / "third_party" / "local" / household.id).resolve()
        )
        self.assertTrue(all(str(Path(root).resolve()).startswith(expected_prefix) for root in mounted_roots))

        adapters = {item.adapter_code: item for item in list_provider_adapters_for_household(self.db, household_id=household.id)}
        self.assertIn("bailian-coding-plan", adapters)
        self.assertIn("kimi-coding-plan", adapters)
        self.assertIn("glm-coding-plan", adapters)
        self.assertEqual(["text"], adapters["bailian-coding-plan"].default_supported_capabilities)
        self.assertEqual(["text"], adapters["kimi-coding-plan"].default_supported_capabilities)
        self.assertEqual(["text"], adapters["glm-coding-plan"].default_supported_capabilities)

    def test_plugins_dev_ai_provider_is_visible_without_mount(self) -> None:
        household = self._create_household()
        self._create_ai_provider_plugin_dir(
            "ai_provider_kimi_coding_plan",
            base_root=Path(settings.plugin_dev_root),
        )

        snapshot = list_registered_plugins_for_household(self.db, household_id=household.id)
        kimi = next(item for item in snapshot.items if item.id == "ai-provider-kimi-coding-plan")
        self.assertEqual("third_party", kimi.source_type)
        self.assertEqual("local", kimi.install_method)
        self.assertTrue(kimi.is_dev_active)
        self.assertEqual(str((Path(settings.plugin_dev_root) / "ai_provider_kimi_coding_plan").resolve()), str(Path(kimi.runner_config.plugin_root).resolve()))
        self.assertEqual([], list_plugin_mounts(self.db, household_id=household.id))

        adapters = {item.adapter_code: item for item in list_provider_adapters_for_household(self.db, household_id=household.id)}
        self.assertIn("kimi-coding-plan", adapters)
        self.assertEqual("native_sdk", adapters["kimi-coding-plan"].transport_type)

    def test_create_provider_profile_accepts_mounted_official_ai_provider(self) -> None:
        household = self._create_household()
        self._mount_official_plugin(household.id, "ai_provider_kimi_coding_plan")

        adapters = {item.adapter_code: item for item in list_provider_adapters_for_household(self.db, household_id=household.id)}
        kimi = adapters["kimi-coding-plan"]

        created = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="family-kimi-coding-main",
                display_name="Kimi Coding",
                transport_type=kimi.transport_type,
                api_family=kimi.api_family,
                base_url=self._read_field_default(kimi.field_schema, "base_url"),
                api_version=None,
                secret_ref="env://KIMI_CODING_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level=kimi.default_privacy_level,
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={
                    "adapter_code": kimi.adapter_code,
                    "model_name": self._read_field_default(kimi.field_schema, "model_name"),
                    "anthropic_version": self._read_field_default(kimi.field_schema, "anthropic_version"),
                },
            ),
            household_id=household.id,
        )

        self.assertEqual("kimi-coding-plan", created.extra_config["adapter_code"])
        self.assertEqual("native_sdk", created.transport_type)
        self.assertEqual("anthropic_messages", created.api_family)

    def test_create_provider_profile_rejects_unmounted_official_ai_provider(self) -> None:
        household = self._create_household()

        with self.assertRaises(AiGatewayConfigurationError):
            create_provider_profile(
                self.db,
                AiProviderProfileCreate(
                    provider_code="family-bailian-coding-main",
                    display_name="百炼 Coding",
                    transport_type="openai_compatible",
                    api_family="openai_chat_completions",
                    base_url="https://coding.dashscope.aliyuncs.com/v1",
                    api_version=None,
                    secret_ref="env://DASHSCOPE_CODING_API_KEY",
                    enabled=True,
                    supported_capabilities=["text"],
                    privacy_level="public_cloud",
                    latency_budget_ms=15000,
                    cost_policy={},
                    extra_config={
                        "adapter_code": "bailian-coding-plan",
                        "model_name": "qwen3-coder-plus",
                    },
                ),
                household_id=household.id,
            )

    def _mount_official_plugin(self, household_id: str, plugin_dir_name: str) -> None:
        plugin_root = self._create_ai_provider_plugin_dir(plugin_dir_name)
        register_plugin_mount(
            self.db,
            household_id=household_id,
            payload=PluginMountCreate(
                source_type="third_party",
                install_method="local",
                plugin_root=str(plugin_root),
                python_path=sys.executable,
                working_dir=str(plugin_root),
                timeout_seconds=20,
            ),
        )
        self.db.flush()

    def _create_ai_provider_plugin_dir(self, plugin_dir_name: str, *, base_root: Path | None = None) -> Path:
        plugin_specs = {
            "ai_provider_bailian_coding_plan": {
                "plugin_id": "ai-provider-bailian-coding-plan",
                "name": "Bailian Coding Plan",
                "adapter_code": "bailian-coding-plan",
                "display_name": "Bailian Coding",
                "driver_entrypoint": "app.plugins.builtin.ai_provider_chatgpt.driver.build_driver",
                "transport_type": "openai_compatible",
                "api_family": "openai_chat_completions",
                "base_url": "https://coding.dashscope.aliyuncs.com/v1",
                "model_name": "qwen3-coder-plus",
            },
            "ai_provider_kimi_coding_plan": {
                "plugin_id": "ai-provider-kimi-coding-plan",
                "name": "Kimi Coding Plan",
                "adapter_code": "kimi-coding-plan",
                "display_name": "Kimi Coding",
                "driver_entrypoint": "app.plugins.builtin.ai_provider_claude.driver.build_driver",
                "transport_type": "native_sdk",
                "api_family": "anthropic_messages",
                "base_url": "https://api.moonshot.cn/anthropic",
                "model_name": "kimi-k2-0905-preview",
                "extra_fields": [
                    {
                        "key": "anthropic_version",
                        "label": "Anthropic Version",
                        "field_type": "text",
                        "required": False,
                        "default_value": "2023-06-01",
                        "options": [],
                    }
                ],
            },
            "ai_provider_glm_coding_plan": {
                "plugin_id": "ai-provider-glm-coding-plan",
                "name": "GLM Coding Plan",
                "adapter_code": "glm-coding-plan",
                "display_name": "GLM Coding",
                "driver_entrypoint": "app.plugins.builtin.ai_provider_chatgpt.driver.build_driver",
                "transport_type": "openai_compatible",
                "api_family": "openai_chat_completions",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model_name": "glm-4.5",
            },
        }
        spec = plugin_specs[plugin_dir_name]
        root = (base_root or Path(self._tempdir.name)) / plugin_dir_name
        resources_dir = root / "resources"
        resources_dir.mkdir(parents=True, exist_ok=True)
        (resources_dir / "logo.svg").write_text("<svg></svg>\n", encoding="utf-8")
        (resources_dir / "description.json").write_text(
            json.dumps({"summary": spec["display_name"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        field_schema = [
            {
                "key": "display_name",
                "label": "Display Name",
                "field_type": "text",
                "required": True,
                "default_value": spec["display_name"],
                "options": [],
            },
            {
                "key": "provider_code",
                "label": "Provider Code",
                "field_type": "text",
                "required": True,
                "default_value": spec["adapter_code"],
                "options": [],
            },
            {
                "key": "base_url",
                "label": "Base URL",
                "field_type": "text",
                "required": False,
                "default_value": spec["base_url"],
                "options": [],
            },
            {
                "key": "secret_ref",
                "label": "Secret Reference",
                "field_type": "secret",
                "required": True,
                "options": [],
            },
            {
                "key": "model_name",
                "label": "Model Name",
                "field_type": "text",
                "required": True,
                "default_value": spec["model_name"],
                "options": [],
            },
            {
                "key": "privacy_level",
                "label": "Privacy Level",
                "field_type": "select",
                "required": True,
                "default_value": "public_cloud",
                "options": [
                    {"label": "Public Cloud", "value": "public_cloud"},
                    {"label": "Private Cloud", "value": "private_cloud"},
                ],
            },
            {
                "key": "latency_budget_ms",
                "label": "Latency Budget (ms)",
                "field_type": "number",
                "required": False,
                "default_value": 15000,
                "options": [],
            },
        ]
        field_schema.extend(spec.get("extra_fields", []))

        field_order = ["display_name", "base_url", "secret_ref", "model_name", "privacy_level", "latency_budget_ms"]
        if spec.get("extra_fields"):
            field_order.insert(4, "anthropic_version")

        manifest = {
            "id": spec["plugin_id"],
            "name": spec["name"],
            "version": "1.0.0",
            "types": ["ai-provider"],
            "permissions": [],
            "risk_level": "low",
            "triggers": [],
            "entrypoints": {
                "ai_provider": spec["driver_entrypoint"],
            },
            "capabilities": {
                "ai_provider": {
                    "adapter_code": spec["adapter_code"],
                    "display_name": spec["display_name"],
                    "branding": {
                        "logo_resource": "resources/logo.svg",
                        "logo_resource_dark": "resources/logo.svg",
                        "description_resource": "resources/description.json",
                    },
                    "field_schema": field_schema,
                    "config_ui": {
                        "field_order": field_order,
                        "sections": [
                            {
                                "key": "connection",
                                "title": "Connection",
                                "description": "Provider connection settings.",
                                "fields": field_order,
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
                    "llm_workflow": spec["api_family"],
                    "runtime_capability": {
                        "transport_type": spec["transport_type"],
                        "api_family": spec["api_family"],
                        "default_privacy_level": "public_cloud",
                        "default_supported_capabilities": ["text"],
                    },
                }
            },
            "compatibility": {
                "provider_profile_schema_version": 1,
                "transport_type": spec["transport_type"],
                "api_family": spec["api_family"],
                "description": spec["display_name"],
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return root

    def _create_household(self):
        household = create_household(
            self.db,
            HouseholdCreate(name="Official Plugin Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        return household

    @staticmethod
    def _read_field_default(field_schema: list[object], field_key: str) -> str | None:
        for field in field_schema:
            if getattr(field, "key", None) == field_key:
                default_value = getattr(field, "default_value", None)
                return str(default_value) if default_value is not None else None
        return None


if __name__ == "__main__":
    unittest.main()
