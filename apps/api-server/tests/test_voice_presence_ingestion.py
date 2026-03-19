import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.presence.models import MemberPresenceState, PresenceEvent
from app.modules.presence.service import record_member_home_presence_from_voice
from app.modules.room.service import create_room
from app.modules.voice.fast_action_service import VoiceRouteDecision
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.pipeline import voice_pipeline_service
from app.modules.voice.registry import voice_session_registry, voice_terminal_registry
from app.modules.voice.router import VoiceRoutingResult
from app.modules.voice.runtime_types import VoiceRuntimeTranscriptResult


def _iso_at(base_time: datetime, *, minutes: int = 0) -> str:
    return (base_time + timedelta(minutes=minutes)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class VoicePresenceIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        voice_terminal_registry.reset()
        voice_session_registry.reset()

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        household = create_household(
            self.db,
            HouseholdCreate(name="Voice Presence Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
        )
        self.living_room = create_room(
            self.db,
            household_id=household.id,
            name="客厅",
            room_type="living_room",
            privacy_level="public",
        )
        self.kitchen = create_room(
            self.db,
            household_id=household.id,
            name="厨房",
            room_type="kitchen",
            privacy_level="public",
        )
        self.db.flush()
        self.household_id = household.id

    def tearDown(self) -> None:
        voice_terminal_registry.reset()
        voice_session_registry.reset()
        self.db.close()
        self._db_helper.close()

    def test_voice_pipeline_records_home_snapshot_for_resolved_member(self) -> None:
        session, terminal = self._prepare_session(session_id="voice-session-1", room_id=self.living_room.id)

        with patch(
            "app.modules.voice.pipeline.voice_runtime_client.finalize_session",
            new=AsyncMock(
                return_value=VoiceRuntimeTranscriptResult(
                    ok=True,
                    transcript_text="打开客厅灯",
                    runtime_status="completed",
                    runtime_session_id="runtime-session-1",
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_router.route",
            new=AsyncMock(
                return_value=VoiceRoutingResult(
                    decision=VoiceRouteDecision(
                        route_type="device_action",
                        route_target="device-1:turn_on",
                        reason="命中设备",
                        response_text="好的，客厅灯已经打开。",
                    ),
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id=self.member.id,
                        primary_member_name=self.member.name,
                        primary_member_role=self.member.role,
                        confidence=0.91,
                        inferred_room_id=self.living_room.id,
                        inferred_room_name=self.living_room.name,
                        reason="终端房间和声纹结果一致。",
                    ),
                )
            ),
        ), patch(
            "app.modules.voice.pipeline.voice_fast_action_service.execute",
            new=AsyncMock(
                return_value=VoiceRouteDecision(
                    route_type="device_action",
                    route_target="device-1:turn_on",
                    reason="执行完成",
                    response_text="好的，客厅灯已经打开。",
                )
            ),
        ):
            commands = asyncio.run(
                voice_pipeline_service._handle_committed_audio(  # type: ignore[attr-defined]
                    self.db,
                    session=session,
                    terminal=terminal,
                    debug_transcript="打开客厅灯",
                )
            )

        snapshot = self.db.get(MemberPresenceState, self.member.id)
        voice_events = list(
            self.db.scalars(
                select(PresenceEvent).where(
                    PresenceEvent.household_id == self.household_id,
                    PresenceEvent.member_id == self.member.id,
                    PresenceEvent.source_type == "voice",
                )
            ).all()
        )

        self.assertEqual(["play.start"], [item.type for item in commands])
        self.assertIsNotNone(snapshot)
        self.assertEqual("home", snapshot.status)
        self.assertEqual(self.living_room.id, snapshot.current_room_id)
        self.assertEqual(1, len(voice_events))
        self.assertEqual("voice-session:voice-session-1", voice_events[0].source_ref)

    def test_voice_presence_helper_debounces_recent_home_snapshot_in_same_room(self) -> None:
        base_time = datetime.now(timezone.utc)

        first_written = record_member_home_presence_from_voice(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
            room_id=self.living_room.id,
            terminal_id="terminal-1",
            session_id="voice-session-1",
            transcript_text="我回来了",
            speaker_confidence=0.88,
            identity_status="resolved",
            occurred_at=_iso_at(base_time),
        )
        self.db.commit()

        second_written = record_member_home_presence_from_voice(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
            room_id=self.living_room.id,
            terminal_id="terminal-1",
            session_id="voice-session-2",
            transcript_text="打开客厅灯",
            speaker_confidence=0.92,
            identity_status="resolved",
            occurred_at=_iso_at(base_time, minutes=2),
        )
        self.db.commit()

        voice_events = list(
            self.db.scalars(
                select(PresenceEvent).where(
                    PresenceEvent.household_id == self.household_id,
                    PresenceEvent.member_id == self.member.id,
                    PresenceEvent.source_type == "voice",
                )
            ).all()
        )

        self.assertTrue(first_written)
        self.assertFalse(second_written)
        self.assertEqual(1, len(voice_events))

    def test_voice_presence_helper_updates_room_when_terminal_room_changes(self) -> None:
        base_time = datetime.now(timezone.utc)

        first_written = record_member_home_presence_from_voice(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
            room_id=self.living_room.id,
            terminal_id="terminal-1",
            session_id="voice-session-1",
            transcript_text="我回来了",
            speaker_confidence=0.88,
            identity_status="resolved",
            occurred_at=_iso_at(base_time),
        )
        self.db.commit()

        second_written = record_member_home_presence_from_voice(
            self.db,
            household_id=self.household_id,
            member_id=self.member.id,
            room_id=self.kitchen.id,
            terminal_id="terminal-2",
            session_id="voice-session-2",
            transcript_text="打开厨房灯",
            speaker_confidence=0.9,
            identity_status="resolved",
            occurred_at=_iso_at(base_time, minutes=2),
        )
        self.db.commit()

        snapshot = self.db.get(MemberPresenceState, self.member.id)
        voice_events = list(
            self.db.scalars(
                select(PresenceEvent).where(
                    PresenceEvent.household_id == self.household_id,
                    PresenceEvent.member_id == self.member.id,
                    PresenceEvent.source_type == "voice",
                )
            ).all()
        )

        self.assertTrue(first_written)
        self.assertTrue(second_written)
        self.assertIsNotNone(snapshot)
        self.assertEqual(self.kitchen.id, snapshot.current_room_id)
        self.assertEqual(2, len(voice_events))

    def _prepare_session(self, *, session_id: str, room_id: str):
        voice_terminal_registry.upsert_online(
            terminal_id="terminal-1",
            household_id=self.household_id,
            fingerprint="open_xiaoai:LX06:SN001",
            room_id=room_id,
            terminal_code="living-room-speaker",
            name="客厅小爱",
            adapter_type="open_xiaoai",
            transport_type="gateway_ws",
            capabilities=["audio_input", "audio_output"],
            adapter_meta={},
            connection_id="connection-1",
            remote_addr="127.0.0.1",
        )
        voice_session_registry.start_session(
            session_id=session_id,
            terminal_id="terminal-1",
            household_id=self.household_id,
            room_id=room_id,
            session_purpose="conversation",
            voiceprint_enrollment_id=None,
            inbound_seq=1,
        )
        session = voice_session_registry.commit_audio(session_id=session_id, inbound_seq=2)
        terminal = voice_terminal_registry.get("terminal-1")
        assert session is not None
        assert terminal is not None
        return session, terminal


if __name__ == "__main__":
    unittest.main()
