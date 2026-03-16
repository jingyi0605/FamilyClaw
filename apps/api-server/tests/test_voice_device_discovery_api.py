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
from app.api.v1.endpoints.devices import router as devices_router
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import new_uuid
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.room.service import create_room
from app.modules.voice.discovery_registry import voice_terminal_discovery_registry
from app.modules.voiceprint.models import VoiceprintEnrollment


class VoiceDeviceDiscoveryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        voice_terminal_discovery_registry.reset()

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Voice Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            room = create_room(
                db,
                household_id=household.id,
                name="瀹㈠巺",
                room_type="living_room",
                privacy_level="public",
            )
            db.commit()
            self.household_id = household.id
            self.room_id = room.id

        app = FastAPI()
        app.include_router(devices_router, prefix=settings.api_v1_prefix)

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
        self._db_helper.close()
        voice_terminal_discovery_registry.reset()
        self._tempdir.cleanup()

    def test_gateway_can_report_pending_voice_terminal(self) -> None:
        response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/report",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
            json={
                "adapter_type": "open_xiaoai",
                "fingerprint": "open_xiaoai:LX06:SN001",
                "model": "LX06",
                "sn": "SN001",
                "runtime_version": "1.0.0",
                "capabilities": ["audio_input", "audio_output", "playback_stop"],
                "remote_addr": "192.168.1.22",
                "connection_status": "online",
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertFalse(payload["claimed"])
        self.assertEqual("open_xiaoai:LX06:SN001", payload["fingerprint"])

    def test_member_can_list_pending_voice_terminals(self) -> None:
        self._report_terminal("open_xiaoai:LX06:SN001", "LX06", "SN001")

        response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries",
            params={"household_id": self.household_id},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(self.household_id, payload["household_id"])
        self.assertEqual(1, len(payload["items"]))
        self.assertEqual("LX06", payload["items"][0]["model"])

    def test_claim_creates_device_and_binding_and_gateway_can_query_result(self) -> None:
        fingerprint = "open_xiaoai:LX06:SN001"
        self._report_terminal(fingerprint, "LX06", "SN001")

        claim_response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "瀹㈠巺闊崇",
            },
        )

        self.assertEqual(200, claim_response.status_code)
        self.assertEqual("瀹㈠巺闊崇", claim_response.json()["terminal_name"])

        binding_response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/binding",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
        )
        self.assertEqual(200, binding_response.status_code)
        binding_payload = binding_response.json()
        self.assertTrue(binding_payload["claimed"])
        self.assertEqual(self.household_id, binding_payload["binding"]["household_id"])
        self.assertFalse(binding_payload["binding"]["voice_auto_takeover_enabled"])
        self.assertEqual(["璇?], binding_payload["binding"]["voice_takeover_prefixes"])

        with self.SessionLocal() as db:
            device = db.scalar(select(Device).where(Device.id == binding_payload["binding"]["terminal_id"]))
            binding = db.scalar(
                select(DeviceBinding).where(
                    DeviceBinding.platform == "open_xiaoai",
                    DeviceBinding.external_entity_id == fingerprint,
                )
            )
            self.assertIsNotNone(device)
            self.assertIsNotNone(binding)
            assert device is not None
            self.assertEqual("speaker", device.device_type)
            self.assertEqual("xiaomi", device.vendor)
            self.assertEqual(self.room_id, device.room_id)
            self.assertEqual(0, device.voice_auto_takeover_enabled)
            self.assertEqual(["璇?], device.voice_takeover_prefixes)

    def test_device_takeover_settings_update_flow_back_to_binding_snapshot(self) -> None:
        fingerprint = "open_xiaoai:LX06:SN002"
        self._report_terminal(fingerprint, "LX06", "SN002")

        claim_response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "椁愬巺闊崇",
            },
        )
        self.assertEqual(200, claim_response.status_code)
        device_id = claim_response.json()["terminal_id"]

        update_response = self.client.patch(
            f"{settings.api_v1_prefix}/devices/{device_id}",
            json={
                "voice_auto_takeover_enabled": True,
                "voiceprint_identity_enabled": True,
                "voice_takeover_prefixes": ["璇?, "甯垜"],
            },
        )
        self.assertEqual(200, update_response.status_code)
        updated_payload = update_response.json()
        self.assertTrue(updated_payload["voice_auto_takeover_enabled"])
        self.assertTrue(updated_payload["voiceprint_identity_enabled"])
        self.assertEqual(["璇?, "甯垜"], updated_payload["voice_takeover_prefixes"])

        binding_response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/binding",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
        )
        self.assertEqual(200, binding_response.status_code)
        binding_payload = binding_response.json()
        self.assertTrue(binding_payload["binding"]["voice_auto_takeover_enabled"])
        self.assertEqual(["璇?, "甯垜"], binding_payload["binding"]["voice_takeover_prefixes"])

    def test_binding_query_returns_pending_voiceprint_enrollment(self) -> None:
        fingerprint = "open_xiaoai:LX06:SN003"
        self._report_terminal(fingerprint, "LX06", "SN003")

        claim_response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "涓诲崸闊崇",
            },
        )
        self.assertEqual(200, claim_response.status_code)
        terminal_id = claim_response.json()["terminal_id"]

        with self.SessionLocal() as db:
            member = create_member(
                db,
                MemberCreate(
                    household_id=self.household_id,
                    name="濡堝",
                    role="adult",
                ),
            )
            db.flush()
            db.add(
                VoiceprintEnrollment(
                    id=new_uuid(),
                    household_id=self.household_id,
                    member_id=member.id,
                    terminal_id=terminal_id,
                    status="pending",
                    expected_phrase="鎴戞槸濡堝",
                    sample_goal=3,
                    sample_count=1,
                    expires_at="2026-03-16T12:00:00+08:00",
                )
            )
            db.commit()

        binding_response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/binding",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
        )
        self.assertEqual(200, binding_response.status_code)
        binding_payload = binding_response.json()
        pending = binding_payload["binding"]["pending_voiceprint_enrollment"]
        self.assertIsNotNone(pending)
        self.assertEqual("鎴戞槸濡堝", pending["expected_phrase"])
        self.assertEqual(3, pending["sample_goal"])
        self.assertEqual(1, pending["sample_count"])

    def test_claim_still_succeeds_when_registry_temporarily_loses_discovery(self) -> None:
        fingerprint = "open_xiaoai:LX06:SN001"
        self._report_terminal(fingerprint, "LX06", "SN001")
        voice_terminal_discovery_registry.reset()

        claim_response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "涔︽埧闊崇",
                "model": "LX06",
                "sn": "SN001",
                "connection_status": "online",
            },
        )

        self.assertEqual(200, claim_response.status_code)
        self.assertEqual("涔︽埧闊崇", claim_response.json()["terminal_name"])

        with self.SessionLocal() as db:
            binding = db.scalar(
                select(DeviceBinding).where(
                    DeviceBinding.platform == "open_xiaoai",
                    DeviceBinding.external_entity_id == fingerprint,
                )
            )
            self.assertIsNotNone(binding)

    def test_claim_missing_discovery_returns_404(self) -> None:
        response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/open_xiaoai%3ALX06%3AMISSING/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "瀹㈠巺闊崇",
            },
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("voice discovery not found", response.json()["detail"])

    def test_binding_query_for_unknown_discovery_returns_404(self) -> None:
        response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/open_xiaoai%3ALX06%3AUNKNOWN/binding",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("voice discovery not found", response.json()["detail"])

    def test_claim_and_binding_support_fingerprint_with_slash(self) -> None:
        fingerprint = "open_xiaoai:LX06:23948/C4QX00829"
        self._report_terminal(fingerprint, "LX06", "23948/C4QX00829")

        claim_response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/claim",
            json={
                "household_id": self.household_id,
                "room_id": self.room_id,
                "terminal_name": "涔︽埧灏忕埍闊崇",
            },
        )
        self.assertEqual(200, claim_response.status_code)

        binding_response = self.client.get(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/{fingerprint}/binding",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
        )
        self.assertEqual(200, binding_response.status_code)
        binding_payload = binding_response.json()
        self.assertTrue(binding_payload["claimed"])
        self.assertEqual(fingerprint, binding_payload["fingerprint"])

    def _report_terminal(self, fingerprint: str, model: str, sn: str) -> None:
        response = self.client.post(
            f"{settings.api_v1_prefix}/devices/voice-terminals/discoveries/report",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
            json={
                "adapter_type": "open_xiaoai",
                "fingerprint": fingerprint,
                "model": model,
                "sn": sn,
                "runtime_version": "1.0.0",
                "capabilities": ["audio_input", "audio_output", "playback_stop", "playback_abort", "heartbeat"],
                "remote_addr": "192.168.1.22",
                "connection_status": "online",
            },
        )
        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()

