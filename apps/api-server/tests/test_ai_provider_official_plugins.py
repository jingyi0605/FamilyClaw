import sys
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
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

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

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
        self.assertTrue(all(item.source_type == "official" for item in official_plugins.values()))
        mounted_roots = [item.plugin_root for item in list_plugin_mounts(self.db, household_id=household.id)]
        expected_prefix = str((BASE_DIR / "data" / "plugins" / "official").resolve())
        self.assertTrue(all(str(Path(root).resolve()).startswith(expected_prefix) for root in mounted_roots))

        adapters = {item.adapter_code: item for item in list_provider_adapters_for_household(self.db, household_id=household.id)}
        self.assertIn("bailian-coding-plan", adapters)
        self.assertIn("kimi-coding-plan", adapters)
        self.assertIn("glm-coding-plan", adapters)
        self.assertEqual(["text"], adapters["bailian-coding-plan"].default_supported_capabilities)
        self.assertEqual(["text"], adapters["kimi-coding-plan"].default_supported_capabilities)
        self.assertEqual(["text"], adapters["glm-coding-plan"].default_supported_capabilities)

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
        plugin_root = BASE_DIR / "data" / "plugins" / "official" / plugin_dir_name
        register_plugin_mount(
            self.db,
            household_id=household_id,
            payload=PluginMountCreate(
                source_type="official",
                plugin_root=str(plugin_root),
                python_path=sys.executable,
                working_dir=str(plugin_root),
                timeout_seconds=20,
            ),
        )
        self.db.flush()

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
