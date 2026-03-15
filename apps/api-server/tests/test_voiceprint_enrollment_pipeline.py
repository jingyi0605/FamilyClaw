import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid
from app.modules.device.models import Device
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.room.service import create_room
from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.protocol import VoiceGatewayEvent
from app.modules.voice.registry import voice_gateway_connection_registry, voice_session_registry, voice_terminal_registry
from app.modules.voice.runtime_client import VoiceRuntimeAudioArtifact, VoiceRuntimeTranscriptResult
from app.modules.voiceprint.models import MemberVoiceprintProfile, MemberVoiceprintSample, VoiceprintEnrollment
from app.modules.voiceprint.provider import VoiceprintEmbedding, VoiceprintProvider, VoiceprintProviderError


class FakeVoiceprintProvider(VoiceprintProvider):
    provider_code = "sherpa_onnx_wespeaker_resnet34"

    def __init__(self, vectors_by_path: dict[str, list[float]]) -> None:
        self._vectors_by_path = {str(Path(path).resolve()): value for path, value in vectors_by_path.items()}

    def extract_embedding(self, audio_path: str) -> VoiceprintEmbedding:
        resolved_path = str(Path(audio_path).resolve())
        vector = self._vectors_by_path.get(resolved_path)
        if vector is None:
            raise VoiceprintProviderError("voiceprint_embedding_missing", f"missing fake embedding: {resolved_path}")
        return VoiceprintEmbedding(
            provider=self.provider_code,
            vector=vector,
            dimension=len(vector),
            audio_path=resolved_path,
            metadata={"source": "pipeline-test"},
        )


class VoiceprintEnrollmentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        settings.database_url = f"sqlite:///{Path(self._tempdir.name) / 'test.db'}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

        voice_gateway_connection_registry.reset()
        voice_terminal_registry.reset()
        voice_session_registry.reset()

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Voice Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            room = create_room(
                db,
                household_id=household.id,
                name="客厅",
                room_type="living_room",
                privacy_level="public",
            )
            member = create_member(
                db,
                MemberCreate(
                    household_id=household.id,
                    name="妈妈",
                    role="adult",
                ),
            )
            device = Device(
                id=new_uuid(),
                household_id=household.id,
                room_id=room.id,
                name="客厅小爱",
                device_type="speaker",
                vendor="xiaomi",
                status="active",
                controllable=0,
                voice_auto_takeover_enabled=0,
            )
            enrollment = VoiceprintEnrollment(
                id=new_uuid(),
                household_id=household.id,
                member_id=member.id,
                terminal_id=device.id,
                status="pending",
                expected_phrase="我是妈妈",
                sample_goal=3,
                sample_count=0,
            )
            db.add(device)
            db.add(enrollment)
            db.commit()

            self.household_id = household.id
            self.room_id = room.id
            self.member_id = member.id
            self.terminal_id = device.id
            self.enrollment_id = enrollment.id

        voice_terminal_registry.upsert_online(
            terminal_id=self.terminal_id,
            household_id=self.household_id,
            fingerprint="open_xiaoai:LX06:SN001",
            room_id=self.room_id,
            terminal_code=self.terminal_id,
            name="客厅小爱",
            adapter_type="open_xiaoai",
            transport_type="gateway_ws",
            capabilities=["audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat"],
            adapter_meta={},
            connection_id="connection-1",
            remote_addr="127.0.0.1",
        )

    def tearDown(self) -> None:
        voice_gateway_connection_registry.reset()
        voice_terminal_registry.reset()
        voice_session_registry.reset()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_voiceprint_enrollment_commit_chain_builds_profile(self) -> None:
        artifact_paths = [self._create_artifact(f"sample-{index}.wav") for index in range(1, 4)]
        provider = FakeVoiceprintProvider(
            {
                artifact_paths[0]: [1.0, 0.0, 0.0],
                artifact_paths[1]: [0.99, 0.04, 0.0],
                artifact_paths[2]: [0.97, 0.08, 0.0],
            }
        )

        with self.SessionLocal() as db, patch(
            "app.modules.voiceprint.service.get_voiceprint_provider",
            return_value=provider,
        ):
            for index, artifact_path in enumerate(artifact_paths, start=1):
                session_id = f"session-{index}"
                voice_session_registry.start_session(
                    session_id=session_id,
                    terminal_id=self.terminal_id,
                    household_id=self.household_id,
                    room_id=self.room_id,
                    session_purpose="voiceprint_enrollment",
                    voiceprint_enrollment_id=self.enrollment_id,
                    inbound_seq=1,
                )
                voice_session_registry.mark_ready(session_id=session_id)
                event = VoiceGatewayEvent.model_validate(
                    {
                        "type": "audio.commit",
                        "terminal_id": self.terminal_id,
                        "session_id": session_id,
                        "seq": 2,
                        "payload": {
                            "duration_ms": 2200,
                            "reason": "speech_recognizer_final",
                            "debug_transcript": "我是妈妈",
                            "session_purpose": "voiceprint_enrollment",
                            "enrollment_id": self.enrollment_id,
                        },
                        "ts": "2026-03-15T00:00:00+08:00",
                    }
                )
                transcript_result = VoiceRuntimeTranscriptResult(
                    ok=True,
                    transcript_text="我是妈妈",
                    runtime_status="transcribed",
                    runtime_session_id=f"runtime-{index}",
                    audio_artifact=VoiceRuntimeAudioArtifact(
                        artifact_id=f"artifact-{index}",
                        file_path=artifact_path,
                        sample_rate=16000,
                        channels=1,
                        sample_width=2,
                        duration_ms=2200,
                        sha256=f"sha-{index}",
                    ),
                )
                with patch(
                    "app.modules.voice.pipeline.voice_runtime_client.finalize_session",
                    new=AsyncMock(return_value=transcript_result),
                ):
                    commands = asyncio.run(voice_pipeline_service.handle_inbound_event(db, event))
                self.assertEqual([], commands)
                session = voice_session_registry.get(session_id)
                self.assertIsNotNone(session)
                assert session is not None
                self.assertEqual("voiceprint_enrollment", session.lane)
                self.assertEqual("voiceprint_enrollment", session.route_type)

            enrollment = db.get(VoiceprintEnrollment, self.enrollment_id)
            profile = db.scalar(
                select(MemberVoiceprintProfile).where(
                    MemberVoiceprintProfile.household_id == self.household_id,
                    MemberVoiceprintProfile.member_id == self.member_id,
                    MemberVoiceprintProfile.status == "active",
                )
            )
            samples = list(
                db.scalars(
                    select(MemberVoiceprintSample).where(
                        MemberVoiceprintSample.enrollment_id == self.enrollment_id
                    )
                ).all()
            )

        self.assertIsNotNone(enrollment)
        self.assertIsNotNone(profile)
        assert enrollment is not None
        assert profile is not None
        self.assertEqual("completed", enrollment.status)
        self.assertEqual(3, enrollment.sample_count)
        self.assertEqual(3, len(samples))
        self.assertTrue(all(item.status == "accepted" for item in samples))
        self.assertTrue(all(item.profile_id == profile.id for item in samples))
        self.assertEqual(1, profile.version)
        self.assertEqual(3, profile.sample_count)

    def _create_artifact(self, name: str) -> str:
        path = Path(self._tempdir.name) / name
        path.write_bytes(b"fake-wave")
        return str(path.resolve())


if __name__ == "__main__":
    unittest.main()
