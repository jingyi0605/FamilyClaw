import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid
from app.modules.device.models import Device
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.room.service import create_room
from app.modules.voiceprint.models import MemberVoiceprintProfile, MemberVoiceprintSample, VoiceprintEnrollment
from app.modules.voiceprint.provider import VoiceprintEmbedding, VoiceprintProvider, VoiceprintProviderError
from app.modules.voiceprint.service import (
    process_voiceprint_enrollment_sample,
    search_voiceprint_profiles_in_household,
    verify_member_voiceprint,
)


class FakeVoiceprintProvider(VoiceprintProvider):
    provider_code = "sherpa_onnx_wespeaker_resnet34"

    def __init__(self, vectors_by_path: dict[str, list[float]], *, failure_paths: set[str] | None = None) -> None:
        self._vectors_by_path = {str(Path(path).resolve()): value for path, value in vectors_by_path.items()}
        self._failure_paths = {str(Path(path).resolve()) for path in (failure_paths or set())}

    def extract_embedding(self, audio_path: str) -> VoiceprintEmbedding:
        resolved_path = str(Path(audio_path).resolve())
        if resolved_path in self._failure_paths:
            raise VoiceprintProviderError("voiceprint_provider_unavailable", "provider mocked unavailable")
        vector = self._vectors_by_path.get(resolved_path)
        if vector is None:
            raise VoiceprintProviderError("voiceprint_embedding_missing", f"missing fake embedding: {resolved_path}")
        return VoiceprintEmbedding(
            provider=self.provider_code,
            vector=vector,
            dimension=len(vector),
            audio_path=resolved_path,
            metadata={"source": "test-double"},
        )


class VoiceprintServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

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
            db.add(device)
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
            db.add(enrollment)
            db.commit()

            self.household_id = household.id
            self.member_id = member.id
            self.terminal_id = device.id
            self.enrollment_id = enrollment.id

    def tearDown(self) -> None:
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_process_samples_builds_profile_and_supports_household_search_verify(self) -> None:
        sample_paths = [self._create_artifact(f"sample-{index}.wav") for index in range(1, 4)]
        query_path = self._create_artifact("query.wav")
        provider = FakeVoiceprintProvider(
            {
                sample_paths[0]: [1.0, 0.0, 0.0],
                sample_paths[1]: [0.98, 0.05, 0.0],
                sample_paths[2]: [0.96, 0.09, 0.0],
                query_path: [0.99, 0.03, 0.0],
            }
        )

        with self.SessionLocal() as db:
            for index, sample_path in enumerate(sample_paths, start=1):
                result = process_voiceprint_enrollment_sample(
                    db,
                    enrollment_id=self.enrollment_id,
                    transcript_text="我是妈妈",
                    artifact_id=f"artifact-{index}",
                    artifact_path=sample_path,
                    artifact_sha256=f"sha-{index}",
                    sample_rate=16000,
                    channels=1,
                    sample_width=2,
                    duration_ms=2200,
                    provider=provider,
                )
                db.commit()
                expected_outcome = "completed" if index == 3 else "recorded"
                self.assertEqual(expected_outcome, result.outcome)

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
            self.assertEqual(3, profile.sample_count)
            self.assertEqual(3, len(samples))
            self.assertTrue(all(item.status == "accepted" for item in samples))
            self.assertTrue(all(item.profile_id == profile.id for item in samples))

            search_result = search_voiceprint_profiles_in_household(
                db,
                household_id=self.household_id,
                artifact_path=query_path,
                provider=provider,
            )
            verify_result = verify_member_voiceprint(
                db,
                household_id=self.household_id,
                member_id=self.member_id,
                artifact_path=query_path,
                provider=provider,
            )

        self.assertEqual("matched", search_result.status)
        self.assertEqual(self.member_id, search_result.member_id)
        self.assertIsNotNone(search_result.score)
        self.assertEqual("matched", verify_result.status)
        self.assertTrue(verify_result.matched)
        self.assertIsNotNone(verify_result.score)

    def test_process_sample_marks_failed_when_provider_unavailable(self) -> None:
        sample_path = self._create_artifact("failed.wav")
        provider = FakeVoiceprintProvider({sample_path: [1.0, 0.0, 0.0]}, failure_paths={sample_path})

        with self.SessionLocal() as db:
            result = process_voiceprint_enrollment_sample(
                db,
                enrollment_id=self.enrollment_id,
                transcript_text="我是妈妈",
                artifact_id="artifact-failed",
                artifact_path=sample_path,
                artifact_sha256="sha-failed",
                sample_rate=16000,
                channels=1,
                sample_width=2,
                duration_ms=2200,
                provider=provider,
            )
            db.commit()
            enrollment = db.get(VoiceprintEnrollment, self.enrollment_id)
            samples = list(
                db.scalars(
                    select(MemberVoiceprintSample).where(
                        MemberVoiceprintSample.enrollment_id == self.enrollment_id
                    )
                ).all()
            )

        self.assertEqual("failed", result.outcome)
        self.assertIsNotNone(enrollment)
        assert enrollment is not None
        self.assertEqual("failed", enrollment.status)
        self.assertEqual("voiceprint_provider_unavailable", enrollment.error_code)
        self.assertEqual(0, enrollment.sample_count)
        self.assertEqual(1, len(samples))
        self.assertEqual("rejected", samples[0].status)

    def test_process_sample_rejects_phrase_mismatch_without_breaking_enrollment(self) -> None:
        sample_path = self._create_artifact("mismatch.wav")
        provider = FakeVoiceprintProvider({sample_path: [1.0, 0.0, 0.0]})

        with self.SessionLocal() as db:
            result = process_voiceprint_enrollment_sample(
                db,
                enrollment_id=self.enrollment_id,
                transcript_text="我不是妈妈",
                artifact_id="artifact-mismatch",
                artifact_path=sample_path,
                artifact_sha256="sha-mismatch",
                sample_rate=16000,
                channels=1,
                sample_width=2,
                duration_ms=2200,
                provider=provider,
            )
            db.commit()
            enrollment = db.get(VoiceprintEnrollment, self.enrollment_id)
            samples = list(
                db.scalars(
                    select(MemberVoiceprintSample).where(
                        MemberVoiceprintSample.enrollment_id == self.enrollment_id
                    )
                ).all()
            )

        self.assertEqual("rejected", result.outcome)
        self.assertIsNotNone(enrollment)
        assert enrollment is not None
        self.assertEqual("pending", enrollment.status)
        self.assertEqual("voiceprint_sample_invalid", enrollment.error_code)
        self.assertEqual(0, enrollment.sample_count)
        self.assertEqual(1, len(samples))
        self.assertEqual("rejected", samples[0].status)

    def _create_artifact(self, name: str) -> str:
        path = Path(self._tempdir.name) / name
        path.write_bytes(b"fake-wave")
        return str(path.resolve())


if __name__ == "__main__":
    unittest.main()
