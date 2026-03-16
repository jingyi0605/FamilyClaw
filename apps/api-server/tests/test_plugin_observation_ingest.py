import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import utc_now_iso
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.memory.service import list_memory_cards
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    execute_plugin,
    ingest_plugin_raw_records_to_memory,
    save_plugin_raw_records,
)


class PluginObservationIngestTests(unittest.TestCase):
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

    def test_ingest_health_raw_records_to_observation_memory_cards(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Observation Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        self.db.flush()

        execution_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.assertTrue(execution_result.success)
        assert isinstance(execution_result.output, dict)

        save_plugin_raw_records(
            self.db,
            household_id=household.id,
            execution_result=execution_result,
            raw_records=execution_result.output.get("records", []),
        )
        self.db.flush()

        written_cards = ingest_plugin_raw_records_to_memory(
            self.db,
            household_id=household.id,
            plugin_id="health-basic-reader",
            run_id=execution_result.run_id,
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual(3, len(written_cards))
        cards, total = list_memory_cards(self.db, household_id=household.id, page=1, page_size=20, memory_type="observation")
        self.assertEqual(3, total)
        self.assertEqual({"health-basic-reader"}, {card.source_plugin_id for card in cards})
        self.assertTrue(all(card.source_raw_record_id for card in cards))
        self.assertEqual(
            {"daily_steps", "sleep_duration", "heart_rate"},
            {card.content["category"] for card in cards if isinstance(card.content, dict)},
        )

    def test_ingest_smart_home_raw_records_to_observation_memory_cards(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Smart Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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
                {"entity_id": "sensor.living_room_humidity", "state": "48", "attributes": {"unit_of_measurement": "%", "device_class": "humidity"}, "last_updated": "2026-03-15T12:00:00Z"},
            ],
        ):
            execution_result = execute_plugin(
                PluginExecutionRequest(
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
        self.assertTrue(execution_result.success)
        assert isinstance(execution_result.output, dict)

        save_plugin_raw_records(
            self.db,
            household_id=household.id,
            execution_result=execution_result,
            raw_records=execution_result.output.get("records", []),
        )
        self.db.flush()

        written_cards = ingest_plugin_raw_records_to_memory(
            self.db,
            household_id=household.id,
            plugin_id="homeassistant",
            run_id=execution_result.run_id,
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual(3, len(written_cards))
        cards, total = list_memory_cards(self.db, household_id=household.id, page=1, page_size=20, memory_type="observation")
        self.assertEqual(3, total)
        self.assertEqual({"homeassistant"}, {card.source_plugin_id for card in cards})
        self.assertTrue(all(card.source_raw_record_id for card in cards))
        self.assertEqual(
            {"device_power_state", "room_temperature", "room_humidity"},
            {card.content["category"] for card in cards if isinstance(card.content, dict)},
        )


if __name__ == "__main__":
    unittest.main()

