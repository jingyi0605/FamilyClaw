import unittest

from pydantic import ValidationError

from app.modules.channel.schemas import ChannelAccountPluginArtifactRead
from app.modules.plugin.schemas import PluginConfigPreviewArtifactRead


class PluginArtifactSchemasTests(unittest.TestCase):
    def test_preview_artifact_accepts_long_image_data_url(self) -> None:
        data_url = "data:image/svg+xml;charset=utf-8," + ("a" * 5000)

        result = PluginConfigPreviewArtifactRead(
            key="login-qr",
            kind="image_url",
            url=data_url,
        )

        self.assertEqual(data_url, result.url)

    def test_channel_action_artifact_accepts_long_image_data_url(self) -> None:
        data_url = "data:image/svg+xml;charset=utf-8," + ("a" * 5000)

        result = ChannelAccountPluginArtifactRead(
            kind="image_url",
            url=data_url,
        )

        self.assertEqual(data_url, result.url)

    def test_external_url_rejects_data_url(self) -> None:
        with self.assertRaises(ValidationError):
            ChannelAccountPluginArtifactRead(
                kind="external_url",
                url="data:image/png;base64,abc",
            )


if __name__ == "__main__":
    unittest.main()
