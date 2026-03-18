import unittest
from unittest.mock import patch

import app.db.models  # noqa: F401
from app.db.utils import dump_json, new_uuid
from app.modules.conversation.device_control_toolkit import (
    ConversationDeviceExecutionPlan,
    device_control_tool_registry,
    execute_planned_device_action,
    get_device_entity_profile,
    search_controllable_entities,
)
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from tests.homeassistant_test_support import seed_homeassistant_integration_instance


class ConversationDeviceControlToolkitTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self.db = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Toolkit Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        instance = seed_homeassistant_integration_instance(
            self.db,
            household_id=self.household.id,
            sync_rooms_enabled=False,
        )
        self.integration_instance_id = instance.id
        self.study_light_id = self._add_device_with_binding(
            name="书房主灯",
            device_type="light",
            entity_payloads=[
                {
                    "entity_id": "light.study_main",
                    "name": "书房主灯",
                    "domain": "light",
                    "state": "off",
                    "state_display": "关闭",
                    "control": {
                        "kind": "toggle",
                        "value": False,
                        "action_on": "turn_on",
                        "action_off": "turn_off",
                    },
                },
                {
                    "entity_id": "sensor.study_power",
                    "name": "书房主灯功率",
                    "domain": "sensor",
                    "state": "15",
                    "state_display": "15",
                    "control": {"kind": "none", "value": None},
                },
            ],
            primary_entity_id="light.study_main",
        )
        self.bedroom_light_id = self._add_device_with_binding(
            name="卧室壁灯",
            device_type="light",
            entity_payloads=[
                {
                    "entity_id": "light.bedroom_lamp",
                    "name": "卧室壁灯",
                    "domain": "light",
                    "state": "on",
                    "state_display": "开启",
                    "control": {
                        "kind": "toggle",
                        "value": True,
                        "action_on": "turn_on",
                        "action_off": "turn_off",
                    },
                }
            ],
            primary_entity_id="light.bedroom_lamp",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_tool_registry_exposes_expected_whitelist_tools(self) -> None:
        tool_names = [tool.name for tool in device_control_tool_registry.list_tools()]

        self.assertEqual(
            [
                "search_controllable_entities",
                "get_device_entity_profile",
                "execute_planned_device_action",
            ],
            tool_names,
        )

    def test_search_controllable_entities_returns_structured_candidates(self) -> None:
        result = search_controllable_entities(
            self.db,
            household_id=self.household.id,
            query="书房灯",
            limit=5,
        )

        self.assertEqual("search_controllable_entities", result.tool_name)
        self.assertGreaterEqual(len(result.items), 1)
        first = result.items[0]
        self.assertEqual(self.study_light_id, first["device_id"])
        self.assertEqual("light.study_main", first["entity_id"])
        self.assertTrue(any(item["action"] == "turn_on" for item in first["action_candidates"]))
        self.assertTrue(first["supports_control"])
        self.assertFalse(first["currently_available"])
        self.assertEqual(["light.study_main"], [item["entity_id"] for item in result.items])

    def test_get_device_entity_profile_returns_entities_and_capabilities(self) -> None:
        result = get_device_entity_profile(
            self.db,
            household_id=self.household.id,
            device_id=self.study_light_id,
        )

        self.assertEqual("get_device_entity_profile", result.tool_name)
        self.assertEqual(1, len(result.items))
        profile = result.items[0]
        self.assertEqual(self.study_light_id, profile["device_id"])
        self.assertTrue(any(item["action"] == "turn_on" for item in profile["supported_actions"]))
        self.assertEqual(2, len(profile["entities"]))
        self.assertEqual("light.study_main", profile["entities"][0]["entity_id"])

    def test_execute_planned_device_action_uses_unified_chain(self) -> None:
        with patch(
            "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
            return_value={"status": "ok"},
        ) as mocked_call:
            response = execute_planned_device_action(
                self.db,
                household_id=self.household.id,
                plan=ConversationDeviceExecutionPlan(
                    device_id=self.study_light_id,
                    entity_id="light.study_main",
                    action="turn_on",
                    params={},
                    reason="conversation.tool_planner",
                    resolution_trace={"source": "toolkit"},
                ),
            )

        self.assertEqual("turn_on", response.action)
        self.assertEqual("light.study_main", response.entity_id)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def _add_device_with_binding(
        self,
        *,
        name: str,
        device_type: str,
        entity_payloads: list[dict],
        primary_entity_id: str,
    ) -> str:
        device = Device(
            id=new_uuid(),
            household_id=self.household.id,
            room_id=None,
            name=name,
            device_type=device_type,
            vendor="ha",
            status="active",
            controllable=1,
        )
        self.db.add(device)
        self.db.flush()
        binding = DeviceBinding(
            id=new_uuid(),
            device_id=device.id,
            integration_instance_id=self.integration_instance_id,
            platform="home_assistant",
            plugin_id="homeassistant",
            binding_version=1,
            external_entity_id=primary_entity_id,
            external_device_id=f"ext-{device.id}",
            capabilities=dump_json(
                {
                    "primary_entity_id": primary_entity_id,
                    "entity_ids": [item["entity_id"] for item in entity_payloads],
                    "entities": entity_payloads,
                }
            ),
        )
        self.db.add(binding)
        self.db.flush()
        return device.id


if __name__ == "__main__":
    unittest.main()
