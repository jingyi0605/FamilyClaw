import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.integrations import router as integrations_router
from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.db.session import get_db
from app.modules.device.models import Device, DeviceBinding
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance
from app.modules.plugin.config_service import get_integration_instance_plugin_config_form
from app.modules.plugin.repository import get_plugin_config_instance_for_integration_instance
from tests.homeassistant_test_support import HOME_ASSISTANT_PLUGIN_ID, seed_homeassistant_integration_instance


class IntegrationInstanceManagementApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.SessionLocal = self._db_helper.SessionLocal

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Integration Manage Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            db.commit()
            self.household_id = household.id

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

        app = FastAPI()
        app.include_router(integrations_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: actor
        app.dependency_overrides[require_bound_member_actor] = lambda: actor
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_update_instance_updates_display_name_and_config_without_clearing_secret(self) -> None:
        with self.SessionLocal() as db:
            instance = seed_homeassistant_integration_instance(
                db,
                household_id=self.household_id,
                display_name="客厅 HA",
                base_url="http://ha.local:8123",
                access_token="secret-token-before",
                sync_rooms_enabled=True,
            )
            db.commit()
            instance_id = instance.id

        response = self.client.put(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}",
            json={
                "display_name": "书房 HA",
                "config": {
                    "base_url": "http://ha.study:8123",
                    "sync_rooms_enabled": False,
                },
                "clear_secret_fields": [],
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual("书房 HA", response.json()["display_name"])

        with self.SessionLocal() as db:
            instance = db.get(IntegrationInstance, instance_id)
            self.assertIsNotNone(instance)
            assert instance is not None
            self.assertEqual("书房 HA", instance.display_name)

            config_form = get_integration_instance_plugin_config_form(
                db,
                household_id=self.household_id,
                plugin_id=HOME_ASSISTANT_PLUGIN_ID,
                integration_instance_id=instance_id,
            )
            self.assertEqual("http://ha.study:8123", config_form.view.values["base_url"])
            self.assertEqual(False, config_form.view.values["sync_rooms_enabled"])
            self.assertTrue(config_form.view.secret_fields["access_token"].has_value)

    def test_delete_instance_removes_synced_devices_related_records_and_config(self) -> None:
        with self.SessionLocal() as db:
            instance = seed_homeassistant_integration_instance(db, household_id=self.household_id, display_name="待删除 HA")
            device_id = self._create_bound_device(
                db,
                household_id=self.household_id,
                integration_instance_id=instance.id,
                name="客厅主灯",
                external_entity_id="light.living_room_main",
                external_device_id="ha-device-light-1",
            )
            discovery_id = self._create_discovery(
                db,
                household_id=self.household_id,
                integration_instance_id=instance.id,
                external_device_id="ha-device-light-1",
                external_entity_id="light.living_room_main",
                claimed_device_id=device_id,
            )
            db.commit()
            instance_id = instance.id

        response = self.client.delete(f"{settings.api_v1_prefix}/integrations/instances/{instance_id}")

        self.assertEqual(204, response.status_code)
        self.assertEqual(b"", response.content)

        with self.SessionLocal() as db:
            self.assertIsNone(db.get(IntegrationInstance, instance_id))
            self.assertIsNone(db.get(Device, device_id))
            self.assertIsNone(db.get(IntegrationDiscovery, discovery_id))
            self.assertEqual(
                [],
                list(db.scalars(select(DeviceBinding).where(DeviceBinding.integration_instance_id == instance_id)).all()),
            )
            self.assertIsNone(
                get_plugin_config_instance_for_integration_instance(
                    db,
                    integration_instance_id=instance_id,
                    plugin_id=HOME_ASSISTANT_PLUGIN_ID,
                    scope_type="plugin",
                )
            )

    def test_delete_instance_keeps_device_if_other_instance_still_uses_it(self) -> None:
        with self.SessionLocal() as db:
            first_instance = seed_homeassistant_integration_instance(db, household_id=self.household_id, display_name="HA 1")
            second_instance = seed_homeassistant_integration_instance(db, household_id=self.household_id, display_name="HA 2")
            device_id = self._create_shared_device_with_bindings(
                db,
                household_id=self.household_id,
                first_instance_id=first_instance.id,
                second_instance_id=second_instance.id,
            )
            db.commit()
            first_instance_id = first_instance.id
            second_instance_id = second_instance.id

        response = self.client.delete(f"{settings.api_v1_prefix}/integrations/instances/{first_instance_id}")

        self.assertEqual(204, response.status_code)

        with self.SessionLocal() as db:
            self.assertIsNone(db.get(IntegrationInstance, first_instance_id))
            self.assertIsNotNone(db.get(IntegrationInstance, second_instance_id))
            self.assertIsNotNone(db.get(Device, device_id))
            remaining_bindings = list(db.scalars(select(DeviceBinding).where(DeviceBinding.device_id == device_id)).all())
            self.assertEqual(1, len(remaining_bindings))
            self.assertEqual(second_instance_id, remaining_bindings[0].integration_instance_id)

    def _create_bound_device(
        self,
        db: Session,
        *,
        household_id: str,
        integration_instance_id: str,
        name: str,
        external_entity_id: str,
        external_device_id: str,
    ) -> str:
        now = utc_now_iso()
        device = Device(
            id=new_uuid(),
            household_id=household_id,
            room_id=None,
            name=name,
            device_type="light",
            vendor="ha",
            status="active",
            controllable=1,
            created_at=now,
            updated_at=now,
        )
        db.add(device)
        db.flush()
        binding = DeviceBinding(
            id=new_uuid(),
            device_id=device.id,
            integration_instance_id=integration_instance_id,
            platform="home_assistant",
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            binding_version=1,
            external_entity_id=external_entity_id,
            external_device_id=external_device_id,
            capabilities=dump_json({"domain": "light"}),
            last_sync_at=now,
        )
        db.add(binding)
        db.flush()
        return device.id

    def _create_discovery(
        self,
        db: Session,
        *,
        household_id: str,
        integration_instance_id: str,
        external_device_id: str,
        external_entity_id: str,
        claimed_device_id: str,
    ) -> str:
        now = utc_now_iso()
        discovery = IntegrationDiscovery(
            id=new_uuid(),
            household_id=household_id,
            integration_instance_id=integration_instance_id,
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            gateway_id=None,
            discovery_key=f"discovery:{external_entity_id}",
            discovery_type="device",
            resource_type="device",
            status="claimed",
            title="已同步设备",
            subtitle=None,
            external_device_id=external_device_id,
            external_entity_id=external_entity_id,
            adapter_type="home_assistant",
            capability_tags_json="[]",
            metadata_json="{}",
            payload_json="{}",
            claimed_device_id=claimed_device_id,
            discovered_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(discovery)
        db.flush()
        return discovery.id

    def _create_shared_device_with_bindings(
        self,
        db: Session,
        *,
        household_id: str,
        first_instance_id: str,
        second_instance_id: str,
    ) -> str:
        device_id = self._create_bound_device(
            db,
            household_id=household_id,
            integration_instance_id=first_instance_id,
            name="共享灯",
            external_entity_id="light.shared_one",
            external_device_id="shared-device",
        )
        second_binding = DeviceBinding(
            id=new_uuid(),
            device_id=device_id,
            integration_instance_id=second_instance_id,
            platform="home_assistant",
            plugin_id=HOME_ASSISTANT_PLUGIN_ID,
            binding_version=1,
            external_entity_id="light.shared_two",
            external_device_id="shared-device-two",
            capabilities=dump_json({"domain": "light"}),
            last_sync_at=utc_now_iso(),
        )
        db.add(second_binding)
        db.flush()
        return device_id


if __name__ == "__main__":
    unittest.main()
