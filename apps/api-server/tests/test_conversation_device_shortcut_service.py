import unittest

from sqlalchemy import inspect
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.db.utils import dump_json, new_uuid
from app.modules.conversation.device_shortcut_service import (
    DeviceShortcutResolutionSource,
    DeviceShortcutStatus,
    DeviceShortcutUpsertPayload,
    mark_device_shortcut_status,
    match_device_shortcut,
    normalize_device_shortcut_text,
    touch_device_shortcut_hit,
    upsert_device_shortcut,
)
from app.modules.conversation.models import ConversationDeviceControlShortcut
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationDeviceShortcutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Shortcut Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        self.other_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Guest", role="adult"),
        )
        self.study_light_id = self._add_device_with_binding(
            name="书房主灯",
            entity_ids=["light.study_main"],
            device_type="light",
        )
        self.study_lamp_id = self._add_device_with_binding(
            name="书房壁灯",
            entity_ids=["light.study_lamp"],
            device_type="light",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_device_control_shortcut_table_exists_after_upgrade(self) -> None:
        assert self.engine is not None
        inspector = inspect(self.engine)
        self.assertTrue(inspector.has_table("device_control_shortcuts"))

    def test_upsert_and_match_member_shortcut(self) -> None:
        created = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="请打开书房主灯",
                device_id=self.study_light_id,
                entity_id="light.study_main",
                action="turn_on",
                params={},
                resolution_source=DeviceShortcutResolutionSource.TOOL_PLANNER,
                confidence=0.92,
            ),
        )
        self.db.commit()

        matched = match_device_shortcut(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            source_text="打开书房主灯",
        )

        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(created.id, matched.id)
        self.assertEqual("打开书房主灯", normalize_device_shortcut_text("打开书房主灯"))
        touched = touch_device_shortcut_hit(self.db, shortcut=matched)
        self.db.commit()
        self.assertEqual(2, touched.hit_count)

    def test_match_supports_semantic_alias_for_same_target(self) -> None:
        created = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房主灯",
                device_id=self.study_light_id,
                entity_id="light.study_main",
                action="turn_on",
                params={},
                confidence=0.93,
            ),
        )
        self.db.commit()

        matched = match_device_shortcut(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            source_text="开启书房主灯",
        )

        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(created.id, matched.id)

    def test_match_prefers_member_shortcut_over_household_shared(self) -> None:
        shared = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=None,
                source_text="打开书房灯",
                device_id=self.study_light_id,
                entity_id="light.study_main",
                action="turn_on",
                params={},
                confidence=0.6,
            ),
        )
        member_specific = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房灯",
                device_id=self.study_lamp_id,
                entity_id="light.study_lamp",
                action="turn_on",
                params={},
                confidence=0.95,
            ),
        )
        self.db.commit()

        matched = match_device_shortcut(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            source_text="请打开书房灯",
        )

        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(member_specific.id, matched.id)
        self.assertNotEqual(shared.id, matched.id)

    def test_semantic_match_returns_none_when_candidates_are_ambiguous(self) -> None:
        upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房主灯",
                device_id=self.study_light_id,
                entity_id="light.study_main",
                action="turn_on",
                params={},
                confidence=0.9,
            ),
        )
        upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房壁灯",
                device_id=self.study_lamp_id,
                entity_id="light.study_lamp",
                action="turn_on",
                params={},
                confidence=0.9,
            ),
        )
        self.db.commit()

        matched = match_device_shortcut(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            source_text="开启书房灯",
        )

        self.assertIsNone(matched)

    def test_invalid_shortcut_is_marked_stale_when_target_entity_disappears(self) -> None:
        stale_candidate = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房主灯",
                device_id=self.study_light_id,
                entity_id="light.missing_target",
                action="turn_on",
                params={},
            ),
        )
        self.db.commit()

        matched = match_device_shortcut(
            self.db,
            household_id=self.household.id,
            member_id=self.member.id,
            source_text="打开书房主灯",
        )
        self.db.refresh(stale_candidate)

        self.assertIsNone(matched)
        self.assertEqual(DeviceShortcutStatus.STALE.value, stale_candidate.status)

    def test_can_mark_shortcut_disabled(self) -> None:
        shortcut = upsert_device_shortcut(
            self.db,
            payload=DeviceShortcutUpsertPayload(
                household_id=self.household.id,
                member_id=self.member.id,
                source_text="打开书房主灯",
                device_id=self.study_light_id,
                entity_id="light.study_main",
                action="turn_on",
                params={},
            ),
        )

        mark_device_shortcut_status(self.db, shortcut=shortcut, status=DeviceShortcutStatus.DISABLED)
        self.db.commit()
        refreshed = self.db.get(ConversationDeviceControlShortcut, shortcut.id)

        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(DeviceShortcutStatus.DISABLED.value, refreshed.status)

    def _add_device_with_binding(self, *, name: str, entity_ids: list[str], device_type: str) -> str:
        device = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name=name,
            device_type=device_type,
            vendor="homeassistant",
            status="active",
            controllable=1,
        )
        binding = DeviceBinding(
            id=new_uuid(),
            device_id=device.id,
            integration_instance_id=None,
            platform="home_assistant",
            plugin_id="homeassistant",
            binding_version=1,
            external_entity_id=entity_ids[0],
            external_device_id=f"ext-{device.id}",
            capabilities=dump_json(
                {
                    "primary_entity_id": entity_ids[0],
                    "entity_ids": entity_ids,
                    "entities": [
                        {
                            "entity_id": entity_id,
                            "name": name,
                            "domain": entity_id.split(".", 1)[0],
                            "state": "off",
                            "state_display": "关闭",
                            "control": {
                                "kind": "toggle",
                                "value": False,
                                "action_on": "turn_on",
                                "action_off": "turn_off",
                            },
                        }
                        for entity_id in entity_ids
                    ],
                }
            ),
        )
        self.db.add(device)
        self.db.flush()
        binding.device_id = device.id
        self.db.add(binding)
        self.db.flush()
        return device.id


if __name__ == "__main__":
    unittest.main()
