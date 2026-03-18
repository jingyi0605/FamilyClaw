import asyncio
import unittest

from sqlalchemy.orm import Session

from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.schemas import IntegrationInstanceActionRequest, IntegrationInstanceCreateRequest
from app.modules.integration.service import (
    create_integration_instance,
    execute_integration_instance_action,
    list_integration_catalog,
    list_integration_instances,
)
from app.modules.plugin import PluginServiceError, set_household_plugin_enabled
from app.modules.plugin.schemas import PluginStateUpdateRequest
from tests.homeassistant_test_support import seed_homeassistant_integration_instance


class IntegrationPluginStateTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_catalog_hides_disabled_integration_plugin(self) -> None:
        household = self._create_household()
        self._disable_plugin(household.id, "homeassistant")

        catalog = list_integration_catalog(self.db, household_id=household.id)
        plugin_ids = {item.plugin_id for item in catalog.items}

        self.assertNotIn("homeassistant", plugin_ids)

    def test_create_integration_instance_rejects_disabled_plugin(self) -> None:
        household = self._create_household()
        self._disable_plugin(household.id, "homeassistant")

        with self.assertRaises(PluginServiceError) as ctx:
            create_integration_instance(
                self.db,
                payload=IntegrationInstanceCreateRequest(
                    household_id=household.id,
                    plugin_id="homeassistant",
                    display_name="Home Assistant",
                    config={},
                    clear_secret_fields=[],
                ),
                updated_by="test-suite",
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertEqual("plugin_disabled", ctx.exception.error_code)
        self.assertEqual("plugin_id", ctx.exception.field)

    def test_existing_instance_is_marked_disabled_and_sync_action_is_blocked(self) -> None:
        household = self._create_household()
        seed_homeassistant_integration_instance(self.db, household_id=household.id)
        self._disable_plugin(household.id, "homeassistant")

        result = list_integration_instances(self.db, household_id=household.id)

        self.assertEqual(1, len(result.items))
        item = result.items[0]
        self.assertEqual("disabled", item.status)
        self.assertIsNotNone(item.last_error)
        assert item.last_error is not None
        self.assertEqual("plugin_disabled", item.last_error.code)

        actions = {action.action: action for action in item.allowed_actions}
        self.assertIn("configure", actions)
        self.assertFalse(actions["configure"].disabled)
        self.assertIn("sync", actions)
        self.assertTrue(actions["sync"].disabled)
        self.assertEqual(item.last_error.message, actions["sync"].disabled_reason)
        self.assertIn("delete", actions)
        self.assertFalse(actions["delete"].disabled)

    def test_execute_sync_action_rejects_disabled_plugin(self) -> None:
        household = self._create_household()
        instance = seed_homeassistant_integration_instance(self.db, household_id=household.id)
        self._disable_plugin(household.id, "homeassistant")

        async def run_case() -> None:
            with self.assertRaises(PluginServiceError) as ctx:
                await execute_integration_instance_action(
                    self.db,
                    instance_id=instance.id,
                    payload=IntegrationInstanceActionRequest(
                        action="sync",
                        payload={"sync_scope": "device_candidates"},
                    ),
                    updated_by="test-suite",
                )

            self.assertEqual(409, ctx.exception.status_code)
            self.assertEqual("plugin_disabled", ctx.exception.error_code)
            self.assertEqual("plugin_id", ctx.exception.field)

        asyncio.run(run_case())

    def _create_household(self):
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Integration Plugin Home",
                city="Hangzhou",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.flush()
        return household

    def _disable_plugin(self, household_id: str, plugin_id: str) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=household_id,
            plugin_id=plugin_id,
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="test-suite",
        )
        self.db.flush()


if __name__ == "__main__":
    unittest.main()
