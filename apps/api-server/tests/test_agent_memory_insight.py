import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import build_agent_memory_insight, create_agent
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import run_plugin_sync_pipeline


class AgentMemoryInsightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_build_agent_memory_insight_uses_plugin_observations(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Insight Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="绗ㄧ",
                agent_type="butler",
                self_identity="鎴戞槸绗ㄧ",
                role_summary="瀹跺涵 AI 绠″",
                created_by="test",
            ),
        )
        self.db.add(
            HouseholdHaConfig(
                household_id=household.id,
                base_url="http://ha.local:8123",
                access_token="demo-token",
                sync_rooms_enabled=True,
                updated_at=utc_now_iso(),
            )
        )
        self.db.commit()

        with patch.multiple(
            "app.modules.ha_integration.client.HomeAssistantClient",
            get_device_registry=lambda self: [{"id": "ha-device-light-1", "name": "瀹㈠巺涓荤伅", "area_id": "area-living-room"}],
            get_entity_registry=lambda self: [{"entity_id": "light.living_room_main", "device_id": "ha-device-light-1", "area_id": "area-living-room", "name": "瀹㈠巺涓荤伅", "disabled_by": None}],
            get_area_registry=lambda self: [{"area_id": "area-living-room", "name": "瀹㈠巺"}],
            get_states=lambda self: [
                {"entity_id": "light.living_room_main", "state": "on", "attributes": {"friendly_name": "瀹㈠巺涓荤伅", "area_name": "瀹㈠巺"}, "last_updated": "2026-03-15T12:00:00Z"},
                {"entity_id": "sensor.living_room_temperature", "state": "23.5", "attributes": {"unit_of_measurement": "掳C"}, "last_updated": "2026-03-15T12:00:00Z"},
            ],
        ):
            run_plugin_sync_pipeline(
                self.db,
                household_id=household.id,
                request=PluginExecutionRequest(
                    plugin_id="homeassistant",
                    plugin_type="connector",
                    payload={
                        "household_id": household.id,
                        "plugin_id": "homeassistant",
                        "sync_scope": "device_sync",
                        "selected_external_ids": [],
                        "options": {},
                        "_system_context": {"device_integration": {"database_url": settings.database_url}},
                    },
                ),
                root_dir=self.builtin_root,
            )
        run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        result = build_agent_memory_insight(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
        )

        self.assertEqual(agent.id, result.agent_id)
        self.assertIn("鎻掍欢鍐欏叆鐨勫搴蹇?, result.summary)
        self.assertIn("health-basic-reader", result.used_plugins)
        self.assertIn("homeassistant", result.used_plugins)
        self.assertTrue(any(item.category == "sleep_duration" for item in result.facts))
        self.assertTrue(any(item.category == "room_temperature" for item in result.facts))
        self.assertTrue(any("鐫＄湢" in item for item in result.suggestions))

    def test_build_agent_memory_insight_returns_empty_state_when_no_plugin_memory(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Empty Insight Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="闃跨",
                agent_type="butler",
                self_identity="鎴戞槸闃跨",
                role_summary="瀹跺涵 AI 绠″",
                created_by="test",
            ),
        )
        self.db.commit()

        result = build_agent_memory_insight(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
        )

        self.assertEqual([], result.used_plugins)
        self.assertEqual([], result.facts)
        self.assertIn("杩樻病鏈夊彲鐢ㄧ殑鎻掍欢璁板繂", result.summary)


if __name__ == "__main__":
    unittest.main()

