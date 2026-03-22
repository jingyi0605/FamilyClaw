import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.modules.plugin.service import PluginManifestValidationError, load_plugin_manifest
from app.modules.voice.speaker_schemas import (
    SpeakerAdapterCapability,
    SpeakerAudioSessionEnvelope,
    SpeakerRuntimeHeartbeat,
    SpeakerTextTurnRequest,
    SpeakerTextTurnResult,
)


class SpeakerManifestSchemaTests(unittest.TestCase):
    def _write_manifest(self, root: Path, payload: dict) -> Path:
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return manifest_path

    def _build_valid_manifest(self) -> dict:
        return {
            "id": "speaker-adapter-demo",
            "name": "Speaker Adapter Demo",
            "version": "0.1.0",
            "api_version": 1,
            "types": ["integration", "action"],
            "permissions": ["device.read", "device.control"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
                "action": "plugin.action.run",
                "speaker_adapter": "plugin.runtime.run",
            },
            "capabilities": {
                "integration": {
                    "domains": ["speaker"],
                    "instance_model": "multi_instance",
                    "refresh_mode": "manual",
                    "supports_discovery": True,
                    "supports_actions": True,
                    "supports_cards": False,
                    "entity_types": ["device.speaker"],
                },
                "speaker_adapter": {
                    "adapter_code": "speaker-adapter-demo",
                    "supported_modes": ["text_turn"],
                    "supported_domains": ["speaker"],
                    "requires_runtime_worker": True,
                    "supports_discovery": True,
                    "supports_commands": True,
                },
            },
        }

    def test_manifest_accepts_speaker_adapter_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(Path(tempdir), self._build_valid_manifest())

            manifest = load_plugin_manifest(manifest_path)

        assert manifest.capabilities.speaker_adapter is not None
        self.assertEqual("plugin.runtime.run", manifest.entrypoints.speaker_adapter)
        self.assertEqual(["text_turn"], manifest.capabilities.speaker_adapter.supported_modes)
        self.assertTrue(manifest.capabilities.speaker_adapter.supports_commands)

    def test_manifest_rejects_speaker_adapter_without_runtime_entrypoint(self) -> None:
        payload = self._build_valid_manifest()
        payload["entrypoints"].pop("speaker_adapter")

        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(Path(tempdir), payload)

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("entrypoints.speaker_adapter", str(context.exception))

    def test_manifest_rejects_text_turn_without_runtime_worker(self) -> None:
        payload = self._build_valid_manifest()
        payload["capabilities"]["speaker_adapter"]["requires_runtime_worker"] = False

        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(Path(tempdir), payload)

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("requires_runtime_worker", str(context.exception))

    def test_manifest_rejects_speaker_adapter_without_speaker_domain(self) -> None:
        payload = self._build_valid_manifest()
        payload["capabilities"]["speaker_adapter"]["supported_domains"] = ["voice_terminal"]

        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(Path(tempdir), payload)

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("supported_domains", str(context.exception))

    def test_manifest_rejects_speaker_commands_without_action_type(self) -> None:
        payload = self._build_valid_manifest()
        payload["types"] = ["integration"]
        payload["entrypoints"].pop("action")

        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._write_manifest(Path(tempdir), payload)

            with self.assertRaises(PluginManifestValidationError) as context:
                load_plugin_manifest(manifest_path)

        self.assertIn("supports_commands", str(context.exception))

    def test_open_xiaoai_manifest_declares_audio_session_only(self) -> None:
        manifest = load_plugin_manifest(
            Path(__file__).resolve().parents[1]
            / "app"
            / "plugins"
            / "builtin"
            / "open_xiaoai_speaker"
            / "manifest.json"
        )

        assert manifest.capabilities.speaker_adapter is not None
        self.assertEqual(["audio_session"], manifest.capabilities.speaker_adapter.supported_modes)
        self.assertEqual(
            "app.plugins.builtin.open_xiaoai_speaker.runtime.run_speaker_adapter",
            manifest.entrypoints.speaker_adapter,
        )


class SpeakerDtoSchemaTests(unittest.TestCase):
    def test_speaker_adapter_capability_accepts_formal_snapshot(self) -> None:
        capability = SpeakerAdapterCapability.model_validate(
            {
                "plugin_id": "speaker-text-demo",
                "adapter_code": "speaker_text_demo",
                "supported_modes": ["text_turn"],
                "supported_domains": ["speaker"],
                "requires_runtime_worker": True,
                "supports_discovery": False,
                "supports_commands": False,
                "runtime_entrypoint": "plugin.runtime.run",
            }
        )

        self.assertEqual("speaker_text_demo", capability.adapter_code)
        self.assertEqual(["text_turn"], capability.supported_modes)

    def test_text_turn_request_accepts_valid_payload(self) -> None:
        request = SpeakerTextTurnRequest.model_validate(
            {
                "household_id": "household-001",
                "plugin_id": "speaker-text-demo",
                "integration_instance_id": "instance-001",
                "binding_id": "binding-001",
                "device_id": "device-001",
                "external_device_id": "speaker-001",
                "conversation_id": "conversation-001",
                "turn_id": "turn-001",
                "input_text": "今天天气怎么样",
                "occurred_at": "2026-03-22T12:00:00Z",
                "context": {"source": "polling"},
            }
        )

        self.assertEqual("binding-001", request.binding_id)
        self.assertEqual("今天天气怎么样", request.input_text)

    def test_text_turn_request_rejects_invalid_timestamp(self) -> None:
        with self.assertRaises(ValidationError) as context:
            SpeakerTextTurnRequest.model_validate(
                {
                    "household_id": "household-001",
                    "plugin_id": "speaker-text-demo",
                    "integration_instance_id": "instance-001",
                    "binding_id": "binding-001",
                    "external_device_id": "speaker-001",
                    "conversation_id": "conversation-001",
                    "turn_id": "turn-001",
                    "input_text": "今天天气怎么样",
                    "occurred_at": "not-a-time",
                }
            )

        self.assertIn("occurred_at", str(context.exception))

    def test_text_turn_result_requires_payload_by_result_type(self) -> None:
        with self.assertRaises(ValidationError) as context:
            SpeakerTextTurnResult.model_validate(
                {
                    "accepted": True,
                    "result_type": "text",
                }
            )

        self.assertIn("reply_text", str(context.exception))

    def test_audio_session_append_requires_audio_ref(self) -> None:
        with self.assertRaises(ValidationError) as context:
            SpeakerAudioSessionEnvelope.model_validate(
                {
                    "household_id": "household-001",
                    "plugin_id": "speaker-audio-demo",
                    "integration_instance_id": "instance-001",
                    "binding_id": "binding-001",
                    "external_device_id": "speaker-001",
                    "conversation_id": "conversation-001",
                    "session_id": "session-001",
                    "stage": "append",
                    "occurred_at": "2026-03-22T12:00:00Z",
                }
            )

        self.assertIn("audio_ref", str(context.exception))

    def test_runtime_heartbeat_accepts_health_snapshot(self) -> None:
        heartbeat = SpeakerRuntimeHeartbeat.model_validate(
            {
                "household_id": "household-001",
                "plugin_id": "speaker-text-demo",
                "integration_instance_id": "instance-001",
                "state": "degraded",
                "consecutive_failures": 2,
                "reported_at": "2026-03-22T12:00:00Z",
                "last_succeeded_at": "2026-03-22T11:59:00Z",
                "last_failed_at": "2026-03-22T12:00:00Z",
                "last_error_summary": "polling timeout",
            }
        )

        self.assertEqual("degraded", heartbeat.state)
        self.assertEqual(2, heartbeat.consecutive_failures)


if __name__ == "__main__":
    unittest.main()
