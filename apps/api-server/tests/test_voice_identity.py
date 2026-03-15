import asyncio
import unittest

from app.modules.context.schemas import (
    ContextOverviewActiveMember,
    ContextOverviewDeviceSummary,
    ContextOverviewMemberState,
    ContextOverviewRead,
    ContextOverviewRoomOccupancy,
)
from app.modules.voice.identity_service import voice_identity_service
from app.modules.voice.registry import VoiceSessionState, VoiceTerminalState


class VoiceIdentityTests(unittest.TestCase):
    def test_identity_prefers_active_member_in_terminal_room(self) -> None:
        overview = _build_overview()
        result = asyncio.run(
            voice_identity_service.resolve(
                _FakeDbSession(),
                household_id="household-1",
                session=VoiceSessionState(
                    session_id="session-1",
                    terminal_id="terminal-1",
                    household_id="household-1",
                    room_id="room-living",
                ),
                terminal=VoiceTerminalState(
                    terminal_id="terminal-1",
                    household_id="household-1",
                    room_id="room-living",
                    name="客厅小爱",
                    status="online",
                ),
                transcript_text="打开客厅灯",
                context_overview=overview,
            )
        )

        self.assertEqual("resolved", result.status)
        self.assertEqual("member-1", result.primary_member_id)
        self.assertEqual("room-living", result.inferred_room_id)

    def test_identity_marks_conflict_when_two_members_same_score(self) -> None:
        overview = _build_overview().model_copy(
            update={
                "active_member": None,
                "member_states": [
                    ContextOverviewMemberState(
                        member_id="member-1",
                        name="妈妈",
                        role="adult",
                        presence="home",
                        activity="active",
                        current_room_id="room-living",
                        current_room_name="客厅",
                        confidence=90,
                        last_seen_minutes=1,
                        highlight="",
                        source="snapshot",
                        source_summary=None,
                        updated_at="2026-03-15T00:00:00+08:00",
                    ),
                    ContextOverviewMemberState(
                        member_id="member-2",
                        name="爸爸",
                        role="adult",
                        presence="home",
                        activity="active",
                        current_room_id="room-living",
                        current_room_name="客厅",
                        confidence=90,
                        last_seen_minutes=1,
                        highlight="",
                        source="snapshot",
                        source_summary=None,
                        updated_at="2026-03-15T00:00:00+08:00",
                    ),
                ],
            }
        )

        result = asyncio.run(
            voice_identity_service.resolve(
                _FakeDbSession(),
                household_id="household-1",
                session=VoiceSessionState(
                    session_id="session-1",
                    terminal_id="terminal-1",
                    household_id="household-1",
                    room_id="room-living",
                ),
                terminal=VoiceTerminalState(
                    terminal_id="terminal-1",
                    household_id="household-1",
                    room_id="room-living",
                    name="客厅小爱",
                    status="online",
                ),
                transcript_text="打开灯",
                context_overview=overview,
            )
        )

        self.assertEqual("conflict", result.status)
        self.assertGreaterEqual(len(result.candidates), 2)


class _FakeDbSession:
    pass


def _build_overview() -> ContextOverviewRead:
    return ContextOverviewRead(
        household_id="household-1",
        household_name="测试家庭",
        home_mode="home",
        privacy_mode="balanced",
        automation_level="assisted",
        home_assistant_status="healthy",
        voice_fast_path_enabled=True,
        guest_mode_enabled=False,
        child_protection_enabled=True,
        elder_care_watch_enabled=True,
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        active_member=ContextOverviewActiveMember(
            member_id="member-1",
            name="妈妈",
            role="adult",
            presence="home",
            activity="active",
            current_room_id="room-living",
            current_room_name="客厅",
            confidence=95,
            source="snapshot",
        ),
        member_states=[
            ContextOverviewMemberState(
                member_id="member-1",
                name="妈妈",
                role="adult",
                presence="home",
                activity="active",
                current_room_id="room-living",
                current_room_name="客厅",
                confidence=95,
                last_seen_minutes=1,
                highlight="",
                source="snapshot",
                source_summary=None,
                updated_at="2026-03-15T00:00:00+08:00",
            ),
            ContextOverviewMemberState(
                member_id="member-2",
                name="爸爸",
                role="adult",
                presence="home",
                activity="focused",
                current_room_id="room-study",
                current_room_name="书房",
                confidence=88,
                last_seen_minutes=2,
                highlight="",
                source="snapshot",
                source_summary=None,
                updated_at="2026-03-15T00:00:00+08:00",
            ),
        ],
        room_occupancy=[
            ContextOverviewRoomOccupancy(
                room_id="room-living",
                name="客厅",
                room_type="living_room",
                privacy_level="public",
                occupant_count=1,
                occupants=[],
                device_count=2,
                online_device_count=2,
                scene_preset="welcome",
                climate_policy="follow_room",
                privacy_guard_enabled=False,
                announcement_enabled=True,
            )
        ],
        device_summary=ContextOverviewDeviceSummary(
            total=2,
            active=2,
            offline=0,
            inactive=0,
            controllable=2,
            controllable_active=2,
            controllable_offline=0,
        ),
        insights=[],
        degraded=False,
        generated_at="2026-03-15T00:00:00+08:00",
    )


if __name__ == "__main__":
    unittest.main()
