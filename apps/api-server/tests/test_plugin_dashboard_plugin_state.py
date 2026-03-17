import unittest

from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin import PluginServiceError, set_household_plugin_enabled
from app.modules.plugin.dashboard_service import upsert_plugin_dashboard_card_snapshot
from app.modules.plugin.schemas import PluginDashboardCardSnapshotUpsert, PluginStateUpdateRequest


class PluginDashboardPluginStateTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_upsert_snapshot_rejects_disabled_plugin_with_unified_error_code(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Dashboard Plugin Home",
                city="Hangzhou",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.flush()

        set_household_plugin_enabled(
            self.db,
            household_id=household.id,
            plugin_id="health-basic-reader",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="test-suite",
        )
        self.db.flush()

        with self.assertRaises(PluginServiceError) as ctx:
            upsert_plugin_dashboard_card_snapshot(
                self.db,
                household_id=household.id,
                plugin_id="health-basic-reader",
                payload=PluginDashboardCardSnapshotUpsert(
                    card_key="daily-steps-summary",
                    payload={"value": 1024},
                ),
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual("plugin_disabled", ctx.exception.error_code)
        self.assertEqual("plugin_id", ctx.exception.field)


if __name__ == "__main__":
    unittest.main()
