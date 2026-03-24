import sys
import unittest
from pathlib import Path
import asyncio

from app.modules.voice.speaker_schemas import SpeakerTextTurnResult


PLUGIN_DEV_ROOT = Path(__file__).resolve().parents[1] / "plugins-dev"
if str(PLUGIN_DEV_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DEV_ROOT))

from migpt_xiaoai_speaker.config import MiGPTXiaoAiSpeakerConfig  # noqa: E402
from migpt_xiaoai_speaker.runtime_worker import MiGPTSpeakerRuntimeWorker, RuntimeBoundDevice  # noqa: E402


class MiGPTSpeakerRuntimeWorkerTests(unittest.TestCase):
    def test_play_audio_reply_uses_play_url_when_mode_is_custom_audio_url(self) -> None:
        worker = MiGPTSpeakerRuntimeWorker(integration_instance_id="integration-audio")
        mina_client = _FakeMiNAClient()
        device = _build_device()
        result = SpeakerTextTurnResult(
            accepted=True,
            conversation_session_id="session-1",
            turn_id="turn-1",
            result_type="audio_url",
            audio_url="https://media.example.com/reply.mp3",
            reply_text="这是回退文本",
        )
        config = MiGPTXiaoAiSpeakerConfig(
            xiaomi_user_id="user-1",
            password_secret_ref="secret",
            tts_mode="custom_audio_url",
        )

        succeeded = worker._play_audio_reply(
            mina_client=mina_client,
            device=device,
            result=result,
            config=config,
        )

        self.assertTrue(succeeded)
        self.assertEqual(["https://media.example.com/reply.mp3"], mina_client.played_urls)
        self.assertEqual([], mina_client.tts_texts)

    def test_play_reply_falls_back_to_tts_when_mode_is_xiaoai(self) -> None:
        worker = MiGPTSpeakerRuntimeWorker(integration_instance_id="integration-xiaoai")
        mina_client = _FakeMiNAClient()
        device = _build_device()
        result = SpeakerTextTurnResult(
            accepted=True,
            conversation_session_id="session-1",
            turn_id="turn-1",
            result_type="audio_url",
            audio_url="https://media.example.com/reply.mp3",
            reply_text="请改走小爱 TTS",
        )
        config = MiGPTXiaoAiSpeakerConfig(
            xiaomi_user_id="user-1",
            password_secret_ref="secret",
            tts_mode="xiaoai",
        )

        succeeded = asyncio.run(
            worker._play_reply(
                mina_client=mina_client,
                device=device,
                result=result,
                config=config,
            )
        )

        self.assertTrue(succeeded)
        self.assertEqual([], mina_client.played_urls)
        self.assertEqual(["请改走小爱 TTS"], mina_client.tts_texts)

    def test_play_reply_uses_audio_url_when_only_audio_is_available(self) -> None:
        worker = MiGPTSpeakerRuntimeWorker(integration_instance_id="integration-audio-only")
        mina_client = _FakeMiNAClient()
        device = _build_device()
        result = SpeakerTextTurnResult(
            accepted=True,
            conversation_session_id="session-1",
            turn_id="turn-1",
            result_type="audio_url",
            audio_url="https://media.example.com/reply.mp3",
            reply_text=None,
        )
        config = MiGPTXiaoAiSpeakerConfig(
            xiaomi_user_id="user-1",
            password_secret_ref="secret",
            tts_mode="xiaoai",
        )

        succeeded = asyncio.run(
            worker._play_reply(
                mina_client=mina_client,
                device=device,
                result=result,
                config=config,
            )
        )

        self.assertTrue(succeeded)
        self.assertEqual(["https://media.example.com/reply.mp3"], mina_client.played_urls)
        self.assertEqual([], mina_client.tts_texts)


class _FakeMiNAClient:
    def __init__(self) -> None:
        self.played_urls: list[str] = []
        self.tts_texts: list[str] = []

    def play_url(self, device, *, url: str) -> bool:
        _ = device
        self.played_urls.append(url)
        return True

    def tts(self, device, *, text: str) -> bool:
        _ = device
        self.tts_texts.append(text)
        return True


def _build_device(*, miot_model: str = "xiaomi.wifispeaker.lx05") -> RuntimeBoundDevice:
    return RuntimeBoundDevice(
        device_id="device-1",
        external_device_id="external-1",
        name="客厅小爱",
        mina_device_id="mina-1",
        miot_did="miot-1",
        hardware="LX05",
        miot_model=miot_model,
        serial_number="serial-1",
        device_sn_profile="profile-1",
    )


if __name__ == "__main__":
    unittest.main()
