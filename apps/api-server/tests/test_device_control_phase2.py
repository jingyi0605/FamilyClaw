import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.device_actions import router as device_actions_router
from app.db.session import get_db
from app.db.utils import new_uuid
from app.core.config import settings
from app.modules.conversation import orchestrator as conversation_orchestrator
from app.modules.device.models import Device, DeviceBinding, DeviceEntity
from app.modules.device_action.schemas import DeviceActionExecuteRequest
from app.modules.device_action import service as device_action_service_module
from app.modules.device_control.schemas import DeviceControlRequest
from app.modules.device_control.service import DeviceControlServiceError, execute_device_control
from app.modules.device.service import list_device_entities
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.scene import service as scene_service
from app.modules.voice import fast_action_service as voice_fast_action_service_module
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClientError
from app.plugins.builtin.homeassistant_device_action.executor import run as run_homeassistant_device_action
from app.plugins.builtin.homeassistant_device_action.executor import run as run_homeassistant_door_lock_action
from tests.homeassistant_test_support import seed_homeassistant_integration_instance


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


class DeviceControlPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Phase2 Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            instance = seed_homeassistant_integration_instance(
                db,
                household_id=household.id,
                sync_rooms_enabled=False,
            )
            self.household_id = household.id
            self.integration_instance_id = instance.id

            self.light_device_id = self._add_device_with_binding(
                db,
                name="客厅灯",
                device_type="light",
                plugin_id="homeassistant",
                external_entity_id="light.living_room_main",
                external_device_id="ha-device-light-1",
            )
            self.lock_device_id = self._add_device_with_binding(
                db,
                name="入户门锁",
                device_type="lock",
                plugin_id="homeassistant",
                external_entity_id="lock.front_door",
                external_device_id="ha-device-lock-1",
            )
            db.commit()

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
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_homeassistant_action_plugin_maps_light_brightness_to_real_service_call(self) -> None:
        payload = self._build_plugin_payload(
            plugin_id="homeassistant",
            device_id=self.light_device_id,
            device_type="light",
            action="set_brightness",
            params={"brightness_pct": 81},
            external_entity_id="light.living_room_main",
            risk_level="low",
        )

        with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
            result = run_homeassistant_device_action(payload)

        self.assertTrue(result["success"])
        self.assertEqual("light", result["external_request"]["domain"])
        self.assertEqual("turn_on", result["external_request"]["service"])
        self.assertEqual(
            {"entity_id": "light.living_room_main", "brightness_pct": 81},
            result["external_request"]["service_data"],
        )
        self.assertEqual("active", result["normalized_state_patch"]["status"])
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.living_room_main", "brightness_pct": 81},
        )

    def test_homeassistant_door_lock_plugin_executes_unlock_service_call(self) -> None:
        payload = self._build_plugin_payload(
            plugin_id="homeassistant",
            device_id=self.lock_device_id,
            device_type="lock",
            action="unlock",
            params={},
            external_entity_id="lock.front_door",
            risk_level="high",
        )

        with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
            result = run_homeassistant_door_lock_action(payload)

        self.assertTrue(result["success"])
        self.assertEqual("lock", result["external_request"]["domain"])
        self.assertEqual("unlock", result["external_request"]["service"])
        self.assertEqual("active", result["normalized_state_patch"]["status"])
        mocked_call.assert_called_once_with(
            domain="lock",
            service="unlock",
            data={"entity_id": "lock.front_door"},
        )

    def test_high_risk_confirmation_stays_in_core_before_plugin_execution(self) -> None:
        with self.SessionLocal() as db:
            with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service") as mocked_call:
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
        mocked_call.assert_not_called()

    def test_execute_api_uses_real_plugin_executor_not_legacy_ha_service(self) -> None:
        with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
            response = self.client.post(
                f"{settings.api_v1_prefix}/device-actions/execute",
                json=DeviceActionExecuteRequest(
                    household_id=self.household_id,
                    device_id=self.light_device_id,
                    action="set_brightness",
                    params={"brightness": 80},
                    reason="api.integration.phase2",
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
        source = inspect.getsource(device_action_service_module)
        self.assertNotIn("execute_home_assistant_device_action", source)
        self.assertNotIn("async_execute_home_assistant_device_action", source)

    def test_execute_device_control_routes_to_binding_that_contains_requested_entity(self) -> None:
        with self.SessionLocal() as db:
            multi_binding_device_id = self._add_device_with_binding(
                db,
                name="书房灯",
                device_type="light",
                plugin_id="homeassistant",
                external_entity_id="sensor.study_light_power",
                external_device_id="ha-device-study-light",
            )
            weather_binding_id = new_uuid()
            db.add(
                DeviceBinding(
                    id=weather_binding_id,
                    device_id=multi_binding_device_id,
                    integration_instance_id=self.integration_instance_id,
                    platform="home_assistant",
                    plugin_id="homeassistant",
                    binding_version=1,
                    external_entity_id="light.study_main",
                    external_device_id="ha-device-study-light",
                    capabilities='{"primary_entity_id":"light.study_main","entity_ids":["light.study_main"]}',
                )
            )
            entity_row = DeviceEntity(
                id=new_uuid(),
                device_id=multi_binding_device_id,
                binding_id=weather_binding_id,
                integration_instance_id=self.integration_instance_id,
                entity_id="light.study_main",
                name="书房灯",
                domain="light",
                state="off",
                state_display="关闭",
                created_at="2026-03-18T03:00:00Z",
                updated_at="2026-03-18T03:00:00Z",
            )
            entity_row.control = {
                "kind": "toggle",
                "value": False,
                "action_on": "turn_on",
                "action_off": "turn_off",
            }
            entity_row.metadata_payload = {}
            db.add(entity_row)
            db.commit()
            with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=multi_binding_device_id,
                        entity_id="light.study_main",
                        action="turn_on",
                        params={},
                        reason="api.integration.phase2.multi-binding",
                    ),
                )

        self.assertEqual("light.study_main", result.resolved_entity_id)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def test_execute_device_control_accepts_legacy_primary_entity_binding(self) -> None:
        class _FakeHomeAssistantClient:
            def get_states(self) -> list[dict]:
                return [
                    {
                        "entity_id": "light.study_main",
                        "state": "on",
                        "last_updated": "2026-03-17T10:00:00Z",
                        "attributes": {},
                    }
                ]

        with self.SessionLocal() as db:
            device_id = self._add_device_with_binding(
                db,
                name="书房灯",
                device_type="light",
                plugin_id="homeassistant",
                external_entity_id="sensor.study_light_power",
                external_device_id="ha-device-study-light-legacy",
            )
            db.flush()
            legacy_binding = db.query(DeviceBinding).filter(DeviceBinding.device_id == device_id).one()
            legacy_binding.capabilities = (
                '{"state":"off","primary_entity_id":"light.study_main",'
                '"entity_ids":["light.study_main","sensor.study_light_power"]}'
            )
            db.add(legacy_binding)
            db.commit()

            with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=device_id,
                        entity_id="light.study_main",
                        action="turn_on",
                        params={},
                        reason="api.integration.phase2.legacy-binding",
                    ),
                )
            with patch(
                "app.plugins.builtin.homeassistant_device_action.runtime.build_home_assistant_client_for_instance",
                return_value=_FakeHomeAssistantClient(),
            ):
                entities = list_device_entities(db, device_id=device_id, view="all")

        self.assertEqual("light.study_main", result.resolved_entity_id)
        self.assertEqual("light.study_main", entities.items[0].entity_id)
        self.assertEqual("开启", entities.items[0].state_display)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def test_execute_device_control_uses_primary_entity_when_request_entity_is_missing(self) -> None:
        with self.SessionLocal() as db:
            device_id = self._add_device_with_binding(
                db,
                name="书房灯",
                device_type="light",
                plugin_id="homeassistant",
                external_entity_id="sensor.study_light_power",
                external_device_id="ha-device-study-light-primary",
            )
            db.flush()
            binding = db.query(DeviceBinding).filter(DeviceBinding.device_id == device_id).one()
            binding.capabilities = (
                '{"state":"off","primary_entity_id":"light.study_main","entity_ids":["light.study_main","sensor.study_light_power"],'
                '"entities":[{"entity_id":"light.study_main","name":"书房灯","domain":"light","state":"off","state_display":"关闭",'
                '"control":{"kind":"toggle","value":false,"action_on":"turn_on","action_off":"turn_off"}}]}'
            )
            db.add(binding)
            db.commit()

            with patch("app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service", return_value={"status": "ok"}) as mocked_call:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=device_id,
                        action="turn_on",
                        params={},
                        reason="api.integration.phase2.primary-entity-default",
                    ),
                )

        self.assertEqual("light.study_main", result.resolved_entity_id)
        mocked_call.assert_called_once_with(
            domain="light",
            service="turn_on",
            data={"entity_id": "light.study_main"},
        )

    def test_execute_device_control_reports_platform_unreachable_when_home_assistant_unreachable(self) -> None:
        with self.SessionLocal() as db:
            with patch(
                "app.plugins.builtin.homeassistant_device_action.client.HomeAssistantClient.call_service",
                side_effect=HomeAssistantClientError("home assistant connection failed: timeout"),
            ):
                with self.assertRaises(DeviceControlServiceError) as context:
                    execute_device_control(
                        db,
                        request=DeviceControlRequest(
                            household_id=self.household_id,
                            device_id=self.light_device_id,
                            action="turn_on",
                            params={},
                            reason="api.integration.phase2.offline",
                        ),
                    )

        self.assertEqual("platform_unreachable", context.exception.error_code)
        self.assertEqual(503, context.exception.status_code)
        self.assertEqual("device platform is unreachable", context.exception.message)

    def test_upstream_modules_do_not_directly_reference_legacy_ha_execute_functions(self) -> None:
        target_modules = (
            device_action_service_module,
            voice_fast_action_service_module,
            conversation_orchestrator,
            scene_service,
        )
        for module in target_modules:
            source = inspect.getsource(module)
            self.assertNotIn("execute_home_assistant_device_action", source)
            self.assertNotIn("async_execute_home_assistant_device_action", source)

    def _add_device_with_binding(
        self,
        db: Session,
        *,
        name: str,
        device_type: str,
        plugin_id: str,
        external_entity_id: str,
        external_device_id: str,
    ) -> str:
        device = Device(
            id=new_uuid(),
            household_id=self.household_id,
            room_id=None,
            name=name,
            device_type=device_type,
            vendor="ha",
            status="active",
            controllable=1,
        )
        db.add(device)
        db.flush()
        db.add(
            DeviceBinding(
                id=new_uuid(),
                device_id=device.id,
                integration_instance_id=self.integration_instance_id,
                platform="home_assistant",
                plugin_id=plugin_id,
                binding_version=1,
                external_entity_id=external_entity_id,
                external_device_id=external_device_id,
            )
        )
        return device.id

    def _build_plugin_payload(
        self,
        *,
        plugin_id: str,
        device_id: str,
        device_type: str,
        action: str,
        params: dict,
        external_entity_id: str,
        risk_level: str,
    ) -> dict:
        return {
            "request_id": new_uuid(),
            "household_id": self.household_id,
            "plugin_id": plugin_id,
                "binding": {
                    "binding_id": new_uuid(),
                    "integration_instance_id": self.integration_instance_id,
                    "platform": "home_assistant",
                    "plugin_id": plugin_id,
                    "external_device_id": f"external-{device_id}",
                "external_entity_id": external_entity_id,
                "capabilities": {"primary_entity_id": external_entity_id},
                "binding_version": 1,
            },
            "device_snapshot": {
                "id": device_id,
                "name": f"device-{device_id}",
                "device_type": device_type,
                "status": "active",
                "controllable": True,
                "room_id": None,
            },
            "action": action,
            "params": params,
            "timeout_seconds": 8,
            "reason": "phase2.test",
            "risk_level": risk_level,
            "_system_context": {
                "device_control": {
                    "database_url": settings.database_url,
                }
            },
        }


if __name__ == "__main__":
    unittest.main()

