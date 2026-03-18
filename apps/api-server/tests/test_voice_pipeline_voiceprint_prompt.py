import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.registry import voice_session_registry
from app.modules.voiceprint.prompt_types import VoiceprintPromptEnrollmentSnapshot
from app.modules.voiceprint.service import VoiceprintEnrollmentProcessResult


class VoicePipelineVoiceprintPromptTests(unittest.TestCase):
    def tearDown(self) -> None:
        voice_session_registry.reset()

    def test_recorded_enrollment_uses_snapshot_for_refresh_without_touching_detached_orm(self) -> None:
        class _DetachedEnrollmentStub:
            id = "enrollment-detached"

            @property
            def terminal_id(self) -> str:
                raise AssertionError("不应该再从脱会话 enrollment 读取 terminal_id")

            @property
            def sample_count(self) -> int:
                raise AssertionError("不应该再从脱会话 enrollment 读取 sample_count")

            @property
            def sample_goal(self) -> int:
                raise AssertionError("不应该再从脱会话 enrollment 读取 sample_goal")

        class _DetachedSampleStub:
            @property
            def id(self) -> str:
                raise AssertionError("不应该再从脱会话 sample 读取 id")

        voice_session_registry.start_session(
            session_id="session-recorded-1",
            terminal_id="terminal-1",
            household_id="household-1",
            room_id="room-1",
            session_purpose="voiceprint_enrollment",
            voiceprint_enrollment_id="enrollment-1",
            inbound_seq=1,
        )
        voice_session_registry.record_audio_artifact(
            session_id="session-recorded-1",
            artifact_id="artifact-1",
            file_path="C:/tmp/artifact-1.wav",
            sample_rate=16000,
            channels=1,
            sample_width=2,
            duration_ms=2200,
            sha256="sha-1",
        )
        session = voice_session_registry.get("session-recorded-1")
        self.assertIsNotNone(session)
        assert session is not None

        result = VoiceprintEnrollmentProcessResult(
            outcome="recorded",
            enrollment=_DetachedEnrollmentStub(),  # type: ignore[arg-type]
            prompt_enrollment=VoiceprintPromptEnrollmentSnapshot(
                id="enrollment-1",
                terminal_id="terminal-1",
                status="recording",
                sample_goal=3,
                sample_count=1,
            ),
            sample=_DetachedSampleStub(),  # type: ignore[arg-type]
            sample_id="sample-1",
        )

        with patch(
            "app.modules.voice.pipeline.async_process_voiceprint_enrollment_sample",
            new=AsyncMock(return_value=result),
        ), patch.object(
            voice_pipeline_service,
            "_refresh_voiceprint_terminal_binding",
            new=AsyncMock(),
        ) as refresh_mock, patch.object(
            voice_pipeline_service,
            "_send_voiceprint_round_prompt",
            new=AsyncMock(),
        ) as prompt_mock:
            commands = asyncio.run(
                voice_pipeline_service._handle_voiceprint_enrollment_commit(  # type: ignore[attr-defined]
                    object(),
                    session=session,
                    transcript_text="我是妈妈",
                )
            )

        self.assertEqual([], commands)
        refresh_mock.assert_awaited_once_with(
            terminal_id="terminal-1",
            reason="voiceprint_enrollment_progressed",
        )
        prompt_mock.assert_not_awaited()
        updated_session = voice_session_registry.get("session-recorded-1")
        self.assertIsNotNone(updated_session)
        assert updated_session is not None
        self.assertEqual("voiceprint_enrollment", updated_session.route_type)
        self.assertEqual("sample-1", updated_session.route_target)


if __name__ == "__main__":
    unittest.main()
