import json
import unittest

from app.db.utils import new_uuid, utc_now_iso
from app.modules.ai_gateway.models import AiProviderProfile
from app.plugins.builtin.ai_provider_openrouter.driver import _prepare_request as prepare_openrouter_request
from app.plugins.builtin.ai_provider_siliconflow.driver import _prepare_request as prepare_siliconflow_request


class AiProviderBuiltinDriverSpecialsTests(unittest.TestCase):
    def test_openrouter_driver_maps_site_headers_in_plugin_side(self) -> None:
        profile = self._build_profile(
            provider_code="family-openrouter-main",
            base_url="https://openrouter.ai/api/v1",
            extra_config={
                "adapter_code": "openrouter",
                "model_name": "openai/gpt-4o-mini",
                "site_url": "https://familyclaw.local",
                "app_name": "FamilyClaw",
            },
        )

        prepared_profile, prepared_payload = prepare_openrouter_request(profile, "text", {"question": "hello"})
        prepared_extra_config = json.loads(prepared_profile.extra_config_json or "{}")

        self.assertEqual({"question": "hello"}, prepared_payload)
        self.assertEqual("https://familyclaw.local", prepared_extra_config["headers"]["HTTP-Referer"])
        self.assertEqual("FamilyClaw", prepared_extra_config["headers"]["X-Title"])

    def test_siliconflow_driver_applies_thinking_defaults_in_plugin_side(self) -> None:
        profile = self._build_profile(
            provider_code="family-siliconflow-main",
            base_url="https://api.siliconflow.cn/v1",
            extra_config={
                "adapter_code": "siliconflow",
                "model_name": "Qwen/Qwen3.5-9B",
            },
        )

        prepared_profile, prepared_payload = prepare_siliconflow_request(
            profile,
            "text",
            {"scene_name": "Living Room", "max_tokens": 400},
        )
        prepared_extra_config = json.loads(prepared_profile.extra_config_json or "{}")

        self.assertEqual(128, prepared_payload["max_tokens"])
        self.assertEqual(False, prepared_extra_config["default_request_body"]["enable_thinking"])
        self.assertEqual(128, prepared_extra_config["default_request_body"]["thinking_budget"])
        self.assertEqual(128, prepared_extra_config["max_tokens"])

    @staticmethod
    def _build_profile(
        *,
        provider_code: str,
        base_url: str,
        extra_config: dict[str, object],
    ) -> AiProviderProfile:
        return AiProviderProfile(
            id=new_uuid(),
            provider_code=provider_code,
            display_name=provider_code,
            transport_type="openai_compatible",
            api_family="openai_chat_completions",
            base_url=base_url,
            api_version=None,
            secret_ref="env://TEST_KEY",
            enabled=True,
            supported_capabilities_json='["text"]',
            privacy_level="public_cloud",
            latency_budget_ms=15000,
            cost_policy_json="{}",
            extra_config_json=json.dumps(extra_config, ensure_ascii=False),
            updated_at=utc_now_iso(),
        )


if __name__ == "__main__":
    unittest.main()
