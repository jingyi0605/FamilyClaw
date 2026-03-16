import inspect
import tempfile
import json
import asyncio
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.integrations import router as integrations_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.device_control import service as device_control_service_module
from app.modules.device_integration import service as device_integration_service_module
from app.modules.device_integration.schemas import DeviceIntegrationPluginResult
from app.modules.device_integration.service import DeviceIntegrationServiceError
from app.modules.device.models import DeviceBinding
from app.modules.integration.models import IntegrationInstance
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.plugins.builtin.homeassistant_device_action.client import HomeAssistantClient
from tests.homeassistant_test_support import (
    mock_homeassistant_registry_payloads,
    seed_homeassistant_integration_instance,
)


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


class DeviceIntegrationPhase3Tests(unittest.TestCase):
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
                HouseholdCreate(name="HA Plugin Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            instance = seed_homeassistant_integration_instance(
                db,
                household_id=household.id,
            )
            db.commit()
            self.household_id = household.id
            self.integration_instance_id = instance.id

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

    def test_candidate_endpoint_uses_unified_homeassistant_plugin(self) -> None:
        with mock_homeassistant_registry_payloads():
            response = self.client.post(
                f"{settings.api_v1_prefix}/integrations/instances/{self.integration_instance_id}/actions",
                json={
                    "action": "sync",
                    "payload": {"sync_scope": "device_candidates"},
                },
            )

        self.assertEqual(200, response.status_code)
        items = response.json()["output"]["items"]
        self.assertEqual(1, len(items))
        self.assertEqual("ha-device-light-1", items[0]["external_device_id"])
        self.assertEqual("瀹㈠巺涓荤伅", items[0]["name"])
        self.assertEqual("瀹㈠巺", items[0]["room_name"])
        self.assertEqual("light", items[0]["device_type"])
        source = inspect.getsource(device_integration_service_module)
        self.assertNotIn("async_list_home_assistant_device_candidates", source)
        self.assertNotIn("list_home_assistant_device_candidates(", source)

    def test_sync_endpoint_creates_binding_with_single_homeassistant_plugin_id(self) -> None:
        with mock_homeassistant_registry_payloads():
            response = self.client.post(
                f"{settings.api_v1_prefix}/integrations/instances/{self.integration_instance_id}/actions",
                json={
                    "action": "sync",
                    "payload": {
                        "sync_scope": "device_sync",
                        "selected_external_ids": ["ha-device-light-1"],
                    },
                },
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()["output"]["summary"]
        self.assertEqual(1, payload["created_devices"])
        self.assertEqual(1, payload["created_bindings"])
        self.assertEqual(1, payload["created_rooms"])
        source = inspect.getsource(device_integration_service_module)
        self.assertNotIn("async_sync_home_assistant_devices", source)
        self.assertNotIn("sync_home_assistant_devices(", source)

        with self.SessionLocal() as db:
            bindings = db.scalars(select(DeviceBinding)).all()
            self.assertEqual(1, len(bindings))
            self.assertEqual("homeassistant", bindings[0].plugin_id)
            self.assertEqual("light.living_room_main", bindings[0].external_entity_id)
            self.assertEqual(self.integration_instance_id, bindings[0].integration_instance_id)

    def test_build_database_url_keeps_password_for_plugin_runtime(self) -> None:
        engine = create_engine(
            URL.create(
                "postgresql+psycopg",
                username="postgres",
                password="secret-pass",
                host="127.0.0.1",
                port=5432,
                database="familyclaw",
            )
        )
        SessionLocal = sessionmaker(bind=engine)

        with SessionLocal() as db:
            integration_database_url = device_integration_service_module._build_database_url(db)
            control_database_url = device_control_service_module._build_database_url(db)

        self.assertIsNotNone(integration_database_url)
        self.assertIsNotNone(control_database_url)
        self.assertIn("secret-pass", integration_database_url or "")
        self.assertIn("secret-pass", control_database_url or "")
        self.assertNotIn("***", integration_database_url or "")
        self.assertNotIn("***", control_database_url or "")
        engine.dispose()

    def test_candidate_endpoint_returns_structured_error_and_marks_instance_degraded(self) -> None:
        with patch(
            "app.modules.integration.service.async_list_home_assistant_device_candidates_via_plugin",
            side_effect=DeviceIntegrationServiceError(
                "connector db failed",
                error_code="plugin_execution_failed",
                status_code=502,
            ),
        ):
            response = self.client.post(
                f"{settings.api_v1_prefix}/integrations/instances/{self.integration_instance_id}/actions",
                json={
                    "action": "sync",
                    "payload": {"sync_scope": "device_candidates"},
                },
            )

        self.assertEqual(502, response.status_code)
        detail = response.json()["detail"]
        self.assertEqual("plugin_execution_failed", detail["error_code"])
        self.assertEqual("connector db failed", detail["detail"])

        with self.SessionLocal() as db:
            instance = db.scalar(
                select(IntegrationInstance).where(IntegrationInstance.id == self.integration_instance_id)
            )
            self.assertIsNotNone(instance)
            self.assertEqual("degraded", instance.status)
            self.assertEqual("plugin_execution_failed", instance.last_error_code)
            self.assertEqual("connector db failed", instance.last_error_message)

    def test_candidate_endpoint_surfaces_plugin_failure_instead_of_empty_list(self) -> None:
        async def _run() -> None:
            with self.SessionLocal() as db, patch(
                "app.modules.device_integration.service._aexecute_connector_plugin",
                return_value=DeviceIntegrationPluginResult(
                    plugin_id="homeassistant",
                    platform="home_assistant",
                    failures=[{"external_ref": None, "reason": "registry fetch exploded"}],
                ),
            ):
                with self.assertRaises(DeviceIntegrationServiceError) as caught:
                    await device_integration_service_module.async_list_home_assistant_device_candidates_via_plugin(
                        db,
                        household_id=self.household_id,
                        integration_instance_id=self.integration_instance_id,
                    )

                self.assertEqual("plugin_execution_failed", caught.exception.error_code)
                self.assertIn("registry fetch exploded", caught.exception.message)

        asyncio.run(_run())

    def test_homeassistant_client_disables_websocket_message_size_limit(self) -> None:
        websocket = MagicMock()
        websocket.recv.side_effect = [
            json.dumps({"type": "auth_required"}),
            json.dumps({"type": "auth_ok"}),
            json.dumps({"type": "result", "success": True, "result": []}),
        ]
        connection = MagicMock()
        connection.__enter__.return_value = websocket
        connection.__exit__.return_value = False

        with patch("websockets.sync.client.connect", return_value=connection) as mocked_connect:
            client = HomeAssistantClient(base_url="http://ha.local:8123", token="demo-token", timeout_seconds=5)
            result = client.get_device_registry()

        self.assertEqual([], result)
        self.assertTrue(mocked_connect.called)
        self.assertIsNone(mocked_connect.call_args.kwargs["max_size"])


if __name__ == "__main__":
    unittest.main()

