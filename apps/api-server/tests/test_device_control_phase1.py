import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.device_actions import router as device_actions_router
from app.core.config import settings
from app.db.session import get_db
from app.db.utils import new_uuid, utc_now_iso
from app.modules.device.models import Device, DeviceBinding
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_control.protocol import device_control_protocol_registry
from app.modules.device_control.router import route_device_plugin
from app.modules.device_control.service import DeviceControlServiceError, execute_device_control
from app.modules.device_control.schemas import DeviceControlRequest
from app.modules.ha_integration.models import HouseholdHaConfig
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


class DeviceControlProtocolTests(unittest.TestCase):
    def test_protocol_registry_normalizes_legacy_and_canonical_params(self) -> None:
        _, brightness_params = device_control_protocol_registry.validate_action_for_device(
            device_type="light",
            action="set_brightness",
            params={"brightness": 55},
        )
        _, volume_params = device_control_protocol_registry.validate_action_for_device(
            device_type="speaker",
            action="set_volume",
            params={"volume": 0.7},
        )
        self.assertEqual({"brightness_pct": 55}, brightness_params)
        self.assertEqual({"volume_pct": 70}, volume_params)

    def test_protocol_registry_rejects_invalid_hvac_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "hvac_mode"):
            device_control_protocol_registry.validate_action_for_device(
                device_type="ac",
                action="set_hvac_mode",
                params={"hvac_mode": "turbo"},
            )

    def test_unlock_is_marked_high_risk(self) -> None:
        definition = device_control_protocol_registry.get_definition("unlock")
        self.assertEqual("high", definition.risk_level)


class DeviceControlPhase1Tests(unittest.TestCase):
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
                HouseholdCreate(name="Control Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            db.add(
                HouseholdHaConfig(
                    household_id=household.id,
                    base_url="http://ha.local:8123",
                    access_token="demo-token",
                    sync_rooms_enabled=False,
                    updated_at=utc_now_iso(),
                )
            )
            self.light_device = Device(
                id=new_uuid(),
                household_id=household.id,
                room_id=None,
                name="客厅灯",
                device_type="light",
                vendor="ha",
                status="inactive",
                controllable=1,
            )
            self.lock_device = Device(
                id=new_uuid(),
                household_id=household.id,
                room_id=None,
                name="大门锁",
                device_type="lock",
                vendor="ha",
                status="inactive",
                controllable=1,
            )
            db.add_all([self.light_device, self.lock_device])
            db.flush()
            self.light_device_id = self.light_device.id
            self.lock_device_id = self.lock_device.id
            db.add_all(
                [
                    DeviceBinding(
                        id=new_uuid(),
                        device_id=self.light_device_id,
                        platform="home_assistant",
                        plugin_id="homeassistant",
                        binding_version=1,
                        external_entity_id="light.living_room_main",
                        external_device_id="ha-device-light-1",
                    ),
                    DeviceBinding(
                        id=new_uuid(),
                        device_id=self.lock_device_id,
                        platform="home_assistant",
                        plugin_id="homeassistant",
                        binding_version=1,
                        external_entity_id="lock.front_door",
                        external_device_id="ha-device-lock-1",
                    ),
                ]
            )
            db.commit()
            self.household_id = household.id

        app = FastAPI()
        app.include_router(device_actions_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

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
        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: actor
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_router_uses_formal_plugin_binding(self) -> None:
        with self.SessionLocal() as db:
            device = db.get(Device, self.light_device_id)
            assert device is not None
            route = route_device_plugin(db, device=device)
            self.assertEqual("homeassistant", route.plugin_id)

    def test_high_risk_action_requires_confirmation_before_plugin_execution(self) -> None:
        with self.SessionLocal() as db:
            with self.assertRaises(DeviceControlServiceError) as context:
                execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=self.lock_device_id,
                        action="unlock",
                        params={},
                        reason="test.unlock",
                        confirm_high_risk=False,
                    ),
                )
        self.assertEqual("high_risk_confirmation_required", context.exception.error_code)

    def test_execute_api_uses_unified_control_chain_and_plugin_runtime(self) -> None:
        with patch("app.modules.ha_integration.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
            response = self.client.post(
                f"{settings.api_v1_prefix}/device-actions/execute",
                json=DeviceActionExecuteRequest(
                    household_id=self.household_id,
                    device_id=self.light_device_id,
                    action="set_brightness",
                    params={"brightness": 80},
                    reason="api.integration",
                ).model_dump(mode="json"),
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("home_assistant", payload["platform"])
        self.assertEqual("light", payload["service_domain"])
        self.assertEqual("turn_on", payload["service_name"])
        self.assertEqual("light.living_room_main", payload["entity_id"])
        self.assertEqual({"brightness_pct": 80}, payload["params"])
        mocked_call.assert_called_once()


class DeviceBindingMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self._tempdir.name) / 'migration.db'}"
        self._previous_database_url = settings.database_url
        settings.database_url = self.database_url
        self.alembic_config = _build_alembic_config(self.database_url)

    def tearDown(self) -> None:
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_upgrade_backfills_home_assistant_plugin_id_for_existing_bindings(self) -> None:
        command.upgrade(self.alembic_config, "20260315_0033")
        engine = create_engine(self.database_url, future=True, connect_args={"check_same_thread": False})
        try:
            with engine.begin() as conn:
                household_id = new_uuid()
                device_id = new_uuid()
                binding_id = new_uuid()
                now = utc_now_iso()
                conn.execute(
                    text(
                        """
                        INSERT INTO households (id, name, city, timezone, locale, status, setup_status, created_at, updated_at)
                        VALUES (:id, :name, :city, :timezone, :locale, :status, :setup_status, :created_at, :updated_at)
                        """
                    ),
                    {
                        "id": household_id,
                        "name": "Migration Home",
                        "city": "Shanghai",
                        "timezone": "Asia/Shanghai",
                        "locale": "zh-CN",
                        "status": "active",
                        "setup_status": "pending",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO devices (id, household_id, room_id, name, device_type, vendor, status, controllable, created_at, updated_at)
                        VALUES (:id, :household_id, NULL, :name, :device_type, :vendor, :status, :controllable, :created_at, :updated_at)
                        """
                    ),
                    {
                        "id": device_id,
                        "household_id": household_id,
                        "name": "Front Door",
                        "device_type": "lock",
                        "vendor": "ha",
                        "status": "inactive",
                        "controllable": 1,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO device_bindings (id, device_id, platform, external_entity_id, external_device_id, capabilities, last_sync_at)
                        VALUES (:id, :device_id, :platform, :external_entity_id, :external_device_id, :capabilities, :last_sync_at)
                        """
                    ),
                    {
                        "id": binding_id,
                        "device_id": device_id,
                        "platform": "home_assistant",
                        "external_entity_id": "lock.front_door",
                        "external_device_id": "ha-lock-1",
                        "capabilities": "{}",
                        "last_sync_at": now,
                    },
                )

            command.upgrade(self.alembic_config, "head")

            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT plugin_id, binding_version FROM device_bindings WHERE id = :id"),
                    {"id": binding_id},
                ).mappings().one()
            self.assertEqual("homeassistant", row["plugin_id"])
            self.assertEqual(1, row["binding_version"])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
