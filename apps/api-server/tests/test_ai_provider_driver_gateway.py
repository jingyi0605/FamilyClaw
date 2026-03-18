import unittest
from unittest.mock import patch

from app.modules.ai_gateway.schemas import AiGatewayInvokeRequest, AiProviderProfileCreate
from app.modules.ai_gateway.service import create_provider_profile, upsert_capability_route
from app.modules.ai_gateway.schemas import AiCapabilityRouteUpsert
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household


class _FakeDriverResult:
    provider_code = "family-chatgpt"
    model_name = "driver-model"
    latency_ms = 7
    finish_reason = "stop"
    normalized_output = {"text": "driver reply"}
    raw_response_ref = "driver://reply"


class _FakeDriver:
    def invoke(self, **kwargs):
        return _FakeDriverResult()


class AiProviderDriverGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_gateway_invokes_via_provider_driver_resolution(self) -> None:
        from app.modules.ai_gateway.gateway_service import invoke_capability

        household = create_household(
            self.db,
            HouseholdCreate(name="Driver Gateway Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        profile = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="family-chatgpt",
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
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
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

        with patch("app.modules.ai_gateway.gateway_service.resolve_ai_provider_driver_for_profile", return_value=_FakeDriver()) as driver_mock:
            with patch("app.modules.ai_gateway.gateway_service.get_provider_adapter", side_effect=AssertionError("legacy transport adapter should not be used")):
                response = invoke_capability(
                    self.db,
                    AiGatewayInvokeRequest(
                        capability="text",
                        household_id=household.id,
                        payload={"question": "你好"},
                    ),
                )

        self.assertEqual("family-chatgpt", response.provider_code)
        self.assertEqual("driver-model", response.model_name)
        self.assertEqual("driver reply", response.normalized_output["text"])
        self.assertEqual(1, driver_mock.call_count)


if __name__ == "__main__":
    unittest.main()
