import unittest

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.ai_gateway.gateway_service import invoke_capability
from app.modules.ai_gateway.schemas import (
    AiCapabilityRouteUpsert,
    AiGatewayInvokeRequest,
    AiProviderProfileCreate,
)
from app.modules.ai_gateway.service import (
    create_provider_profile,
    list_provider_adapters_for_household,
    upsert_capability_route,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin import PluginServiceError, set_household_plugin_enabled
from app.modules.plugin.schemas import PluginStateUpdateRequest


class AiProviderPluginStateTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_household_provider_adapters_hide_disabled_plugins(self) -> None:
        household = self._create_household()
        self._disable_plugin(household.id, "builtin.provider.chatgpt")

        adapters = list_provider_adapters_for_household(self.db, household_id=household.id)
        adapter_codes = {item.adapter_code for item in adapters}

        self.assertNotIn("chatgpt", adapter_codes)
        self.assertIn("glm", adapter_codes)

    def test_create_provider_profile_rejects_disabled_household_plugin(self) -> None:
        household = self._create_household()
        self._disable_plugin(household.id, "builtin.provider.chatgpt")

        with self.assertRaises(PluginServiceError) as ctx:
            create_provider_profile(
                self.db,
                self._build_chatgpt_profile_payload("family-chatgpt-disabled"),
                household_id=household.id,
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual("plugin_disabled", ctx.exception.error_code)
        self.assertEqual("plugin_id", ctx.exception.field)

    def test_capability_route_rejects_profile_bound_to_disabled_plugin(self) -> None:
        household = self._create_household()
        profile = create_provider_profile(
            self.db,
            self._build_chatgpt_profile_payload("family-chatgpt-route"),
        )
        self._disable_plugin(household.id, "builtin.provider.chatgpt")

        with self.assertRaises(PluginServiceError) as ctx:
            upsert_capability_route(
                self.db,
                AiCapabilityRouteUpsert(
                    capability="text",
                    household_id=household.id,
                    primary_provider_profile_id=profile.id,
                    fallback_provider_profile_ids=[],
                    routing_mode="primary_then_fallback",
                    timeout_ms=15000,
                    max_retry_count=0,
                    allow_remote=True,
                    prompt_policy={},
                    response_policy={},
                    enabled=True,
                ),
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual("plugin_disabled", ctx.exception.error_code)

    def test_invoke_capability_returns_plugin_disabled_for_disabled_household_plugin(self) -> None:
        household = self._create_household()
        profile = create_provider_profile(
            self.db,
            self._build_chatgpt_profile_payload("family-chatgpt-runtime"),
        )
        upsert_capability_route(
            self.db,
            AiCapabilityRouteUpsert(
                capability="text",
                household_id=household.id,
                primary_provider_profile_id=profile.id,
                fallback_provider_profile_ids=[],
                routing_mode="primary_then_fallback",
                timeout_ms=15000,
                max_retry_count=0,
                allow_remote=True,
                prompt_policy={},
                response_policy={"template_fallback_enabled": False},
                enabled=True,
            ),
        )
        self._disable_plugin(household.id, "builtin.provider.chatgpt")

        with self.assertRaises(HTTPException) as ctx:
            invoke_capability(
                self.db,
                AiGatewayInvokeRequest(
                    capability="text",
                    household_id=household.id,
                    payload={"question": "你好"},
                ),
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual("plugin_disabled", ctx.exception.detail["error_code"])
        self.assertEqual("plugin_id", ctx.exception.detail["field"])
        self.assertEqual("builtin.provider.chatgpt", ctx.exception.detail["plugin_id"])

    def _create_household(self):
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Plugin State Home",
                city="Hangzhou",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.flush()
        return household

    def _disable_plugin(self, household_id: str, plugin_id: str) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=household_id,
            plugin_id=plugin_id,
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="test-suite",
        )
        self.db.flush()

    @staticmethod
    def _build_chatgpt_profile_payload(provider_code: str) -> AiProviderProfileCreate:
        return AiProviderProfileCreate(
            provider_code=provider_code,
            display_name="家庭 ChatGPT",
            transport_type="openai_compatible",
            api_family="openai_chat_completions",
            base_url="https://api.openai.com/v1",
            api_version=None,
            secret_ref="env://OPENAI_API_KEY",
            enabled=True,
            supported_capabilities=["text"],
            privacy_level="public_cloud",
            latency_budget_ms=15000,
            cost_policy={},
            extra_config={
                "adapter_code": "chatgpt",
                "model_name": "gpt-4o-mini",
            },
        )


if __name__ == "__main__":
    unittest.main()
