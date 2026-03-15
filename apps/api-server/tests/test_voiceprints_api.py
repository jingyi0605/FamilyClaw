import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.voiceprints import router as voiceprints_router
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import new_uuid
from app.modules.device.models import Device
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.room.service import create_room
from app.modules.voiceprint.models import MemberVoiceprintProfile, MemberVoiceprintSample, VoiceprintEnrollment


class VoiceprintsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
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
            db.commit()
            self.household_id = household.id
            self.room_id = room.id
            self.member_id = member.id
            self.terminal_id = device.id

        app = FastAPI()
        app.include_router(voiceprints_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id="member-admin-1",
            account_id="account-admin-1",
            account_type="member",
            account_status="active",
            username="admin",
            household_id=self.household_id,
            member_id="member-admin-1",
            member_role="admin",
            is_authenticated=True,
        )
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: actor
        app.dependency_overrides[require_bound_member_actor] = lambda: actor
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_create_enrollment_uses_default_three_samples(self) -> None:
        response = self.client.post(
            f"{settings.api_v1_prefix}/voiceprints/enrollments",
            json={
                "household_id": self.household_id,
                "member_id": self.member_id,
                "terminal_id": self.terminal_id,
                "expected_phrase": "我是妈妈",
            },
        )

        self.assertEqual(201, response.status_code)
        payload = response.json()
        self.assertEqual("pending", payload["status"])
        self.assertEqual(3, payload["sample_goal"])
        self.assertEqual(0, payload["sample_count"])
        self.assertEqual("我是妈妈", payload["expected_phrase"])
        self.assertIsNotNone(payload["expires_at"])

    def test_create_enrollment_rejects_terminal_conflict(self) -> None:
        with self.SessionLocal() as db:
            db.add(
                VoiceprintEnrollment(
                    id=new_uuid(),
                    household_id=self.household_id,
                    member_id=self.member_id,
                    terminal_id=self.terminal_id,
                    status="pending",
                    sample_goal=3,
                    sample_count=0,
                )
            )
            db.commit()

        response = self.client.post(
            f"{settings.api_v1_prefix}/voiceprints/enrollments",
            json={
                "household_id": self.household_id,
                "member_id": self.member_id,
                "terminal_id": self.terminal_id,
                "expected_phrase": "我是妈妈",
            },
        )

        self.assertEqual(409, response.status_code)
        self.assertEqual("voiceprint enrollment conflict", response.json()["detail"])

    def test_list_and_cancel_enrollment(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/voiceprints/enrollments",
            json={
                "household_id": self.household_id,
                "member_id": self.member_id,
                "terminal_id": self.terminal_id,
                "expected_phrase": "我是妈妈",
                "sample_goal": 3,
            },
        )
        enrollment_id = create_response.json()["id"]

        list_response = self.client.get(
            f"{settings.api_v1_prefix}/voiceprints/enrollments",
            params={"household_id": self.household_id},
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual(1, list_response.json()["total"])

        cancel_response = self.client.post(
            f"{settings.api_v1_prefix}/voiceprints/enrollments/{enrollment_id}/cancel"
        )
        self.assertEqual(200, cancel_response.status_code)
        self.assertEqual("cancelled", cancel_response.json()["status"])

    def test_member_voiceprint_detail_and_delete(self) -> None:
        profile_id = new_uuid()
        enrollment_id = new_uuid()
        sample_id = new_uuid()
        with self.SessionLocal() as db:
            db.add(
                VoiceprintEnrollment(
                    id=enrollment_id,
                    household_id=self.household_id,
                    member_id=self.member_id,
                    terminal_id=self.terminal_id,
                    status="pending",
                    expected_phrase="我是妈妈",
                    sample_goal=3,
                    sample_count=1,
                )
            )
            db.add(
                MemberVoiceprintProfile(
                    id=profile_id,
                    household_id=self.household_id,
                    member_id=self.member_id,
                    provider="sherpa_onnx_wespeaker_resnet34",
                    status="active",
                    sample_count=1,
                    version=1,
                )
            )
            db.add(
                MemberVoiceprintSample(
                    id=sample_id,
                    profile_id=profile_id,
                    enrollment_id=enrollment_id,
                    household_id=self.household_id,
                    member_id=self.member_id,
                    terminal_id=self.terminal_id,
                    artifact_id="artifact-1",
                    artifact_path="C:/tmp/artifact-1.wav",
                    artifact_sha256="abc123",
                    sample_rate=16000,
                    channels=1,
                    sample_width=2,
                    duration_ms=1200,
                    transcript_text="我是妈妈",
                    status="accepted",
                )
            )
            db.commit()

        detail_response = self.client.get(f"{settings.api_v1_prefix}/voiceprints/members/{self.member_id}")
        self.assertEqual(200, detail_response.status_code)
        payload = detail_response.json()
        self.assertEqual(profile_id, payload["active_profile"]["id"])
        self.assertEqual(1, len(payload["samples"]))
        self.assertEqual(1, len(payload["pending_enrollments"]))

        delete_response = self.client.delete(f"{settings.api_v1_prefix}/voiceprints/members/{self.member_id}")
        self.assertEqual(200, delete_response.status_code)
        self.assertEqual(1, delete_response.json()["deleted_profile_count"])
        self.assertEqual(1, delete_response.json()["cancelled_enrollment_count"])

        with self.SessionLocal() as db:
            profile = db.scalar(select(MemberVoiceprintProfile).where(MemberVoiceprintProfile.id == profile_id))
            enrollment = db.scalar(select(VoiceprintEnrollment).where(VoiceprintEnrollment.id == enrollment_id))
            self.assertIsNotNone(profile)
            self.assertIsNotNone(enrollment)
            assert profile is not None
            assert enrollment is not None
            self.assertEqual("deleted", profile.status)
            self.assertEqual("cancelled", enrollment.status)


if __name__ == "__main__":
    unittest.main()
