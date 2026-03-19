import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.db.utils import new_uuid, utc_now_iso
from app.modules.ai_gateway.models import AiProviderProfile
from app.plugins.builtin.ai_provider_glm.driver import _prepare_request as prepare_glm_request
from app.plugins.builtin.ai_provider_lmstudio.driver import build_driver as build_lmstudio_driver
from app.plugins.builtin.ai_provider_localai.driver import build_driver as build_localai_driver
from app.plugins.builtin.ai_provider_ollama.driver import build_driver as build_ollama_driver
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

    def test_glm_driver_applies_fast_task_defaults_for_glm5(self) -> None:
        profile = self._build_profile(
            provider_code="family-glm-main",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            extra_config={
                "adapter_code": "glm-coding-plan",
                "model_name": "glm-5",
                "temperature": 0.2,
                "max_tokens": 512,
            },
        )

        prepared_profile, prepared_payload = prepare_glm_request(
            profile,
            "text",
            {
                "task_type": "conversation_intent_detection",
                "temperature": 0.1,
                "max_tokens": 768,
            },
        )
        prepared_extra_config = json.loads(prepared_profile.extra_config_json or "{}")

        self.assertEqual(
            {
                "task_type": "conversation_intent_detection",
                "temperature": 0.1,
                "max_tokens": 768,
            },
            prepared_payload,
        )
        self.assertEqual(0.1, prepared_extra_config["temperature"])
        self.assertEqual(256, prepared_extra_config["max_tokens"])
        self.assertEqual({"type": "disabled"}, prepared_extra_config["default_request_body"]["thinking"])

    def test_glm_driver_syncs_task_level_sampling_for_non_fast_task(self) -> None:
        profile = self._build_profile(
            provider_code="family-glm-main",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            extra_config={
                "adapter_code": "glm",
                "model_name": "glm-4-flash",
                "temperature": 0.2,
                "max_tokens": 512,
            },
        )

        prepared_profile, _prepared_payload = prepare_glm_request(
            profile,
            "text",
            {
                "task_type": "free_chat",
                "temperature": 0.7,
                "max_tokens": 768,
            },
        )
        prepared_extra_config = json.loads(prepared_profile.extra_config_json or "{}")

        self.assertEqual(0.7, prepared_extra_config["temperature"])
        self.assertEqual(768, prepared_extra_config["max_tokens"])
        self.assertNotIn("default_request_body", prepared_extra_config)

    def test_glm_driver_keeps_stream_payload_without_task_type_untouched(self) -> None:
        profile = self._build_profile(
            provider_code="family-glm-main",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4",
            extra_config={
                "adapter_code": "glm-coding-plan",
                "model_name": "glm-5",
                "temperature": 0.2,
                "max_tokens": 512,
            },
        )

        prepared_profile, prepared_payload = prepare_glm_request(
            profile,
            "text",
            {
                "temperature": 0.7,
                "max_tokens": 768,
            },
        )

        self.assertIs(profile, prepared_profile)
        self.assertEqual(
            {
                "temperature": 0.7,
                "max_tokens": 768,
            },
            prepared_payload,
        )

    def test_ollama_driver_discovers_models_from_native_tags_endpoint(self) -> None:
        driver = build_ollama_driver()

        with patch("app.plugins._local_openai_provider_helpers.httpx.get") as mock_get:
            mock_get.return_value = SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"models": [{"name": "qwen3:8b"}, {"name": "llama3.2:latest"}]},
            )
            models = driver.discover_models(values={"base_url": "http://127.0.0.1:11434/v1", "secret_ref": ""})

        self.assertEqual(["qwen3:8b", "llama3.2:latest"], models)
        self.assertEqual("http://127.0.0.1:11434/api/tags", mock_get.call_args.args[0])

    def test_lmstudio_driver_discovers_models_from_openai_models_endpoint(self) -> None:
        driver = build_lmstudio_driver()

        with patch("app.plugins._local_openai_provider_helpers.httpx.get") as mock_get:
            mock_get.return_value = SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"data": [{"id": "qwen2.5-7b-instruct"}, {"id": "phi-4-mini"}]},
            )
            models = driver.discover_models(values={"base_url": "http://127.0.0.1:1234/v1", "secret_ref": ""})

        self.assertEqual(["qwen2.5-7b-instruct", "phi-4-mini"], models)
        self.assertEqual("http://127.0.0.1:1234/v1/models", mock_get.call_args.args[0])

    def test_localai_driver_discovers_models_from_openai_models_endpoint(self) -> None:
        driver = build_localai_driver()

        with patch("app.plugins._local_openai_provider_helpers.httpx.get") as mock_get:
            mock_get.return_value = SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"data": [{"id": "localai-model"}]},
            )
            models = driver.discover_models(values={"base_url": "http://127.0.0.1:8080/v1", "secret_ref": ""})

        self.assertEqual(["localai-model"], models)
        self.assertEqual("http://127.0.0.1:8080/v1/models", mock_get.call_args.args[0])

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
