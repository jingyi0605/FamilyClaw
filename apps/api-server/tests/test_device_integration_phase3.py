import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.devices import router as devices_router
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import utc_now_iso
from app.modules.device.models import DeviceBinding
from app.modules.ha_integration import service as ha_integration_service_module
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.ha_integration.schemas import HomeAssistantSyncRequest
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


class DeviceIntegrationPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"
        command.upgrade(_build_alembic_config(settings.database_url), "head")

        self.engine = create_engine(settings.database_url, future=True, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="HA Plugin Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            db.add(
                HouseholdHaConfig(
                    household_id=household.id,
                    base_url="http://ha.local:8123",
                    access_token="demo-token",
                    sync_rooms_enabled=True,
                    updated_at=utc_now_iso(),
                )
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
        app.include_router(devices_router, prefix=settings.api_v1_prefix)

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
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_candidate_endpoint_uses_unified_homeassistant_plugin(self) -> None:
        with self._mock_homeassistant_registry_payloads():
            response = self.client.get(f"{settings.api_v1_prefix}/devices/ha-candidates/{self.household_id}")

        self.assertEqual(200, response.status_code)
        items = response.json()["items"]
        self.assertEqual(1, len(items))
        self.assertEqual("ha-device-light-1", items[0]["external_device_id"])
        self.assertEqual("客厅主灯", items[0]["name"])
        self.assertEqual("客厅", items[0]["room_name"])
        self.assertEqual("light", items[0]["device_type"])
        source = inspect.getsource(ha_integration_service_module)
        self.assertNotIn("async_list_home_assistant_device_candidates", source)
        self.assertNotIn("list_home_assistant_device_candidates(", source)

    def test_sync_endpoint_creates_binding_with_single_homeassistant_plugin_id(self) -> None:
        with self._mock_homeassistant_registry_payloads():
            response = self.client.post(
                f"{settings.api_v1_prefix}/devices/sync/ha",
                json=HomeAssistantSyncRequest(
                    household_id=self.household_id,
                    external_device_ids=["ha-device-light-1"],
                ).model_dump(mode="json"),
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(1, payload["created_devices"])
        self.assertEqual(1, payload["created_bindings"])
        self.assertEqual(1, payload["created_rooms"])
        source = inspect.getsource(ha_integration_service_module)
        self.assertNotIn("async_sync_home_assistant_devices", source)
        self.assertNotIn("sync_home_assistant_devices(", source)

        with self.SessionLocal() as db:
            bindings = db.scalars(select(DeviceBinding)).all()
            self.assertEqual(1, len(bindings))
            self.assertEqual("homeassistant", bindings[0].plugin_id)
            self.assertEqual("light.living_room_main", bindings[0].external_entity_id)

    def _mock_homeassistant_registry_payloads(self):
        return patch.multiple(
            "app.modules.ha_integration.client.HomeAssistantClient",
            get_device_registry=lambda self: [
                {
                    "id": "ha-device-light-1",
                    "name": "客厅主灯",
                    "name_by_user": None,
                    "manufacturer": "Philips",
                    "model": "Hue",
                    "area_id": "area-living-room",
                }
            ],
            get_entity_registry=lambda self: [
                {
                    "entity_id": "light.living_room_main",
                    "device_id": "ha-device-light-1",
                    "area_id": "area-living-room",
                    "name": "客厅主灯",
                    "original_name": "Living Room Main",
                    "disabled_by": None,
                }
            ],
            get_area_registry=lambda self: [{"area_id": "area-living-room", "name": "客厅"}],
            get_states=lambda self: [
                {
                    "entity_id": "light.living_room_main",
                    "state": "on",
                    "attributes": {"friendly_name": "客厅主灯", "area_name": "客厅"},
                    "last_updated": "2026-03-15T12:00:00Z",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
