import unittest
from pathlib import Path


class AiProviderProtocolBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_core_provider_driver_no_longer_contains_protocol_builder_helpers(self) -> None:
        content = (self.project_root / "app" / "modules" / "ai_gateway" / "provider_driver.py").read_text(encoding="utf-8")
        self.assertNotIn("build_openai_compatible_driver", content)
        self.assertNotIn("build_anthropic_messages_driver", content)
        self.assertNotIn("build_gemini_generate_content_driver", content)

    def test_core_provider_runtime_no_longer_contains_provider_protocol_branches(self) -> None:
        content = (self.project_root / "app" / "modules" / "ai_gateway" / "provider_runtime.py").read_text(encoding="utf-8")
        banned_fragments = [
            "openai_chat_completions",
            "anthropic_messages",
            "gemini_generate_content",
            "stream_provider_invoke",
            "_invoke_openai_compatible",
            "_stream_openai_compatible",
            "_invoke_anthropic_messages",
            "_stream_anthropic_messages",
            "_invoke_gemini_generate_content",
            "_stream_gemini_generate_content",
            "_build_messages",
        ]
        for fragment in banned_fragments:
            self.assertNotIn(fragment, content)

    def test_ai_provider_manifests_do_not_point_back_to_core_protocol_builder(self) -> None:
        builtin_root = self.project_root / "app" / "plugins" / "builtin"
        official_root = self.project_root / "data" / "plugins" / "official"
        manifest_paths = sorted(builtin_root.glob("ai_provider_*/manifest.json")) + sorted(
            official_root.glob("ai_provider_*/manifest.json")
        )
        self.assertTrue(manifest_paths)

        for manifest_path in manifest_paths:
            content = manifest_path.read_text(encoding="utf-8")
            self.assertNotIn("app.modules.ai_gateway.provider_driver.", content)
            self.assertNotIn('"ai_provider": "driver.build_driver"', content)


if __name__ == "__main__":
    unittest.main()
