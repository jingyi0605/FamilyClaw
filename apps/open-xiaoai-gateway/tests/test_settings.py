import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from open_xiaoai_gateway.settings import Settings


class GatewaySettingsTests(unittest.TestCase):
    def test_native_first_requires_takeover_prefixes(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, invocation_mode="native_first", takeover_prefixes=[])

    def test_takeover_prefixes_support_csv_and_dedup(self) -> None:
        settings = Settings(
            _env_file=None,
            invocation_mode="native_first",
            takeover_prefixes="帮我，请帮我,帮我,请",
        )

        self.assertEqual(["帮我", "请帮我", "请"], settings.takeover_prefixes)
        self.assertTrue(settings.strip_takeover_prefix)
        self.assertTrue(settings.pause_on_takeover)

    def test_takeover_prefixes_support_json_array_string(self) -> None:
        settings = Settings(
            _env_file=None,
            invocation_mode="native_first",
            takeover_prefixes='["请", "帮我", "请"]',
        )

        self.assertEqual(["请", "帮我"], settings.takeover_prefixes)

    def test_takeover_prefixes_support_plain_env_value(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "FAMILYCLAW_OPEN_XIAOAI_GATEWAY_INVOCATION_MODE=native_first",
                        "FAMILYCLAW_OPEN_XIAOAI_GATEWAY_TAKEOVER_PREFIXES=请",
                    ]
                ),
                encoding="utf-8",
            )

            settings = Settings(_env_file=env_path)

        self.assertEqual(["请"], settings.takeover_prefixes)


if __name__ == "__main__":
    unittest.main()
