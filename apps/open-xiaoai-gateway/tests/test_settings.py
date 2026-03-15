import unittest

from pydantic import ValidationError

from open_xiaoai_gateway.settings import Settings


class GatewaySettingsTests(unittest.TestCase):
    def test_native_first_requires_takeover_prefixes(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(invocation_mode="native_first", takeover_prefixes=[])

    def test_takeover_prefixes_support_csv_and_dedup(self) -> None:
        settings = Settings(
            invocation_mode="native_first",
            takeover_prefixes="帮我, 请帮我 ,帮我,请",
        )

        self.assertEqual(["帮我", "请帮我", "请"], settings.takeover_prefixes)
        self.assertTrue(settings.strip_takeover_prefix)
        self.assertTrue(settings.pause_on_takeover)


if __name__ == "__main__":
    unittest.main()
