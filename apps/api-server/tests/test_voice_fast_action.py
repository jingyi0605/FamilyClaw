import asyncio
import unittest
from unittest.mock import patch

from app.modules.context.schemas import (
    ContextOverviewActiveMember,
    ContextOverviewDeviceSummary,
    ContextOverviewRead,
    ContextOverviewRoomOccupancy,
    ContextOverviewRoomOccupant,
)
from app.modules.device.models import Device
from app.modules.scene.schemas import SceneTemplateRead
from app.modules.voice.fast_action_service import voice_fast_action_service
from app.modules.voice.identity_service import VoiceIdentityResolution
from app.modules.voice.registry import VoiceTerminalState


class VoiceFastActionTests(unittest.TestCase):
    def test_room_device_action_contracts_to_single_device(self) -> None:
        context = _build_context()
        devices = [
            _build_device(device_id="device-living-light", name="客厅主灯", device_type="light", room_id="room-living"),
            _build_device(device_id="device-bedroom-light", name="卧室主灯", device_type="light", room_id="room-bedroom"),
        ]

        with patch("app.modules.voice.fast_action_service.list_devices", return_value=(devices, len(devices))), patch(
            "app.modules.voice.fast_action_service.list_templates",
            return_value=[],
        ):
            decision = asyncio.run(
                voice_fast_action_service.resolve(
                    _FakeDbSession(),
                    household_id="household-1",
                    transcript_text="打开客厅灯",
                    context_overview=context,
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-1",
                        household_id="household-1",
                        room_id="room-living",
                        name="客厅小爱",
                        status="online",
                    ),
                    identity=VoiceIdentityResolution(
                        status="resolved",
                        primary_member_id="member-1",
                        primary_member_name="妈妈",
                        primary_member_role="adult",
                        confidence=0.8,
                        inferred_room_id="room-living",
                        inferred_room_name="客厅",
                        reason="终端房间和活跃成员一致。",
                    ),
                )
            )

        self.assertEqual("device_action", decision.route_type)
        self.assertEqual("device-living-light:turn_on", decision.route_target)

    def test_multiple_devices_without_room_fall_back_with_ambiguity(self) -> None:
        context = _build_context()
        devices = [
            _build_device(device_id="device-living-light", name="客厅灯", device_type="light", room_id="room-living"),
            _build_device(device_id="device-bedroom-light", name="卧室灯", device_type="light", room_id="room-bedroom"),
        ]

        with patch("app.modules.voice.fast_action_service.list_devices", return_value=(devices, len(devices))), patch(
            "app.modules.voice.fast_action_service.list_templates",
            return_value=[],
        ):
            decision = asyncio.run(
                voice_fast_action_service.resolve(
                    _FakeDbSession(),
                    household_id="household-1",
                    transcript_text="打开灯",
                    context_overview=context.model_copy(
                        update={
                            "active_member": None,
                            "room_occupancy": [
                                room.model_copy(update={"occupant_count": 0, "occupants": []}) for room in context.room_occupancy
                            ],
                        }
                    ),
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-1",
                        household_id="household-1",
                        room_id=None,
                        name="走廊小爱",
                        status="online",
                    ),
                )
            )

        self.assertEqual("conversation", decision.route_type)
        self.assertEqual("fast_action_device_ambiguous", decision.error_code)

    def test_quiet_hours_blocks_speaker_action(self) -> None:
        context = _build_context()
        devices = [_build_device(device_id="device-speaker", name="客厅音箱", device_type="speaker", room_id="room-living")]

        with patch("app.modules.voice.fast_action_service.list_devices", return_value=(devices, 1)), patch(
            "app.modules.voice.fast_action_service.list_templates",
            return_value=[],
        ), patch.object(voice_fast_action_service, "_is_quiet_hours_active", return_value=True):
            decision = asyncio.run(
                voice_fast_action_service.resolve(
                    _FakeDbSession(),
                    household_id="household-1",
                    transcript_text="打开客厅音箱",
                    context_overview=context,
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-1",
                        household_id="household-1",
                        room_id="room-living",
                        name="客厅小爱",
                        status="online",
                    ),
                )
            )

        self.assertEqual("quiet_hours_blocked", decision.error_code)

    def test_child_protection_blocks_scene(self) -> None:
        context = _build_context().model_copy(
            update={
                "quiet_hours_enabled": False,
            }
        )
        template = SceneTemplateRead(
            id="scene-1",
            household_id="household-1",
            template_code="child_bedtime",
            name="儿童睡前",
            description=None,
            enabled=True,
            priority=1,
            cooldown_seconds=60,
            trigger={},
            conditions=[],
            guards=[],
            actions=[{"type": "broadcast", "target_ref": "speaker", "message": "该睡觉了"}],
            rollout_policy={},
            version=1,
            updated_by=None,
            updated_at="2026-03-15T00:00:00+08:00",
        )

        with patch("app.modules.voice.fast_action_service.list_templates", return_value=[template]), patch(
            "app.modules.voice.fast_action_service.list_devices",
            return_value=([], 0),
        ):
            decision = asyncio.run(
                voice_fast_action_service.resolve(
                    _FakeDbSession(),
                    household_id="household-1",
                    transcript_text="执行睡前模式",
                    context_overview=context,
                )
            )

        self.assertEqual("child_protection_blocked", decision.error_code)

    def test_high_risk_unlock_is_blocked(self) -> None:
        context = _build_context()
        devices = [_build_device(device_id="device-lock", name="入户门锁", device_type="lock", room_id="room-living")]

        with patch("app.modules.voice.fast_action_service.list_devices", return_value=(devices, 1)), patch(
            "app.modules.voice.fast_action_service.list_templates",
            return_value=[],
        ):
            decision = asyncio.run(
                voice_fast_action_service.resolve(
                    _FakeDbSession(),
                    household_id="household-1",
                    transcript_text="解锁门锁",
                    context_overview=context,
                    terminal=VoiceTerminalState(
                        terminal_id="terminal-1",
                        household_id="household-1",
                        room_id="room-living",
                        name="客厅小爱",
                        status="online",
                    ),
                )
            )

        self.assertEqual("high_risk_action_blocked", decision.error_code)


class _FakeDbSession:
    pass


def _build_device(*, device_id: str, name: str, device_type: str, room_id: str) -> Device:
    return Device(
        id=device_id,
        household_id="household-1",
        room_id=room_id,
        name=name,
        device_type=device_type,
        vendor="ha",
        status="active",
        controllable=1,
    )


def _build_context() -> ContextOverviewRead:
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
            confidence=92,
            source="snapshot",
        ),
        member_states=[],
        room_occupancy=[
            ContextOverviewRoomOccupancy(
                room_id="room-living",
                name="客厅",
                room_type="living_room",
                privacy_level="public",
                occupant_count=1,
                occupants=[
                    ContextOverviewRoomOccupant(
                        member_id="member-1",
                        name="妈妈",
                        role="adult",
                        presence="home",
                        activity="active",
                    )
                ],
                device_count=3,
                online_device_count=3,
                scene_preset="welcome",
                climate_policy="follow_room",
                privacy_guard_enabled=False,
                announcement_enabled=True,
            ),
            ContextOverviewRoomOccupancy(
                room_id="room-bedroom",
                name="卧室",
                room_type="bedroom",
                privacy_level="private",
                occupant_count=0,
                occupants=[],
                device_count=2,
                online_device_count=2,
                scene_preset="rest",
                climate_policy="follow_member",
                privacy_guard_enabled=True,
                announcement_enabled=False,
            ),
        ],
        device_summary=ContextOverviewDeviceSummary(
            total=5,
            active=5,
            offline=0,
            inactive=0,
            controllable=5,
            controllable_active=5,
            controllable_offline=0,
        ),
        insights=[],
        degraded=False,
        generated_at="2026-03-15T00:00:00+08:00",
    )


if __name__ == "__main__":
    unittest.main()
