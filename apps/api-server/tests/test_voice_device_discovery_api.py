import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor, require_bound_member_actor
from app.api.v1.endpoints.device_actions import router as device_actions_router
from app.api.v1.endpoints.integrations import router as integrations_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.device.models import DeviceBinding
from app.modules.device_control.schemas import DeviceControlRequest
from app.modules.device_control.service import execute_device_control
from app.modules.device_integration import service as device_integration_service_module
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


class VoiceDeviceDiscoveryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="XiaoAI Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
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
        app.include_router(device_actions_router, prefix=settings.api_v1_prefix)

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

    def test_open_xiaoai_plugin_can_be_created_as_formal_instance(self) -> None:
        catalog = self.client.get(
            f"{settings.api_v1_prefix}/integrations/catalog",
            params={"household_id": self.household_id},
        )

        self.assertEqual(200, catalog.status_code)
        catalog_items = catalog.json()["items"]
        plugin_ids = {item["plugin_id"] for item in catalog_items}
        self.assertIn("open-xiaoai-speaker", plugin_ids)
        open_xiaoai_item = next(item for item in catalog_items if item["plugin_id"] == "open-xiaoai-speaker")
        self.assertEqual(
            "例如：小爱音箱网关",
            open_xiaoai_item["instance_display_name_placeholder"],
        )

        response = self._create_instance(gateway_id="gateway-living-room")
        self.assertEqual(201, response.status_code)
        self.assertEqual("open-xiaoai-speaker", response.json()["plugin_id"])

    def test_unbound_gateway_discovery_is_visible_in_page_view(self) -> None:
        self._report_discovery(gateway_id="gateway-unbound", fingerprint="open_xiaoai:LX06:SN100", sn="SN100")

        response = self.client.get(
            f"{settings.api_v1_prefix}/integrations/page-view",
            params={"household_id": self.household_id},
        )

        self.assertEqual(200, response.status_code)
        discoveries = response.json()["discoveries"]
        self.assertEqual(1, len(discoveries))
        self.assertIsNone(discoveries[0]["integration_instance_id"])
        self.assertIsNone(discoveries[0]["household_id"])
        self.assertEqual("gateway-unbound", discoveries[0]["metadata"]["gateway_id"])

    def test_open_xiaoai_instance_can_auto_select_single_discovered_gateway(self) -> None:
        self._report_discovery(gateway_id="gateway-auto", fingerprint="open_xiaoai:LX06:SN101", sn="SN101")

        response = self._create_instance(gateway_id=None)
        self.assertEqual(201, response.status_code)
        instance_id = response.json()["id"]

        with self.SessionLocal() as db:
            discovery = db.scalar(
                select(IntegrationDiscovery).where(
                    IntegrationDiscovery.plugin_id == "open-xiaoai-speaker",
                    IntegrationDiscovery.discovery_key == "open_xiaoai:LX06:SN101",
                )
            )
            self.assertIsNotNone(discovery)
            assert discovery is not None
            self.assertEqual(instance_id, discovery.integration_instance_id)
            self.assertEqual(self.household_id, discovery.household_id)
            self.assertEqual("gateway-auto", discovery.gateway_id)

        candidates_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
            json={"action": "sync", "payload": {"sync_scope": "device_candidates"}},
        )
        self.assertEqual(200, candidates_response.status_code)
        items = candidates_response.json()["output"]["items"]
        self.assertEqual(["SN101"], [item["external_device_id"] for item in items])

    def test_open_xiaoai_instance_lists_candidates_and_syncs_multiple_speakers(self) -> None:
        response = self._create_instance(gateway_id="gateway-living-room")
        instance_id = response.json()["id"]

        self._report_discovery(gateway_id="gateway-living-room", fingerprint="open_xiaoai:LX06:SN001", sn="SN001")
        self._report_discovery(gateway_id="gateway-living-room", fingerprint="open_xiaoai:LX06:SN002", sn="SN002")

        candidates_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
            json={"action": "sync", "payload": {"sync_scope": "device_candidates"}},
        )
        self.assertEqual(200, candidates_response.status_code)
        items = candidates_response.json()["output"]["items"]
        self.assertEqual(2, len(items))
        self.assertEqual({"SN001", "SN002"}, {item["external_device_id"] for item in items})

        sync_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
            json={
                "action": "sync",
                "payload": {
                    "sync_scope": "device_sync",
                    "selected_external_ids": ["SN001", "SN002"],
                },
            },
        )
        self.assertEqual(200, sync_response.status_code)
        summary = sync_response.json()["output"]["summary"]
        self.assertEqual(2, summary["created_devices"])
        self.assertEqual(2, summary["created_bindings"])

        with self.SessionLocal() as db:
            bindings = list(
                db.scalars(
                    select(DeviceBinding).where(DeviceBinding.integration_instance_id == instance_id)
                ).all()
            )
        self.assertEqual(2, len(bindings))
        self.assertEqual({"open-xiaoai-speaker"}, {item.plugin_id for item in bindings})
        self.assertEqual({"open_xiaoai"}, {item.platform for item in bindings})

    def test_open_xiaoai_sync_payload_includes_database_runtime_context(self) -> None:
        response = self._create_instance(gateway_id="gateway-runtime-context")
        instance_id = response.json()["id"]

        with self.SessionLocal() as db:
            instance = db.scalar(
                select(IntegrationInstance).where(IntegrationInstance.id == instance_id)
            )
            self.assertIsNotNone(instance)
            assert instance is not None
            payload = device_integration_service_module._build_payload(
                db,
                instance=instance,
                sync_scope="device_sync",
                selected_external_ids=["SN900"],
                options={},
            )

        self.assertEqual(
            {
                "device_integration": {
                    "database_url": self.database_url,
                }
            },
            payload.system_context,
        )

    def test_discovery_report_returns_claimed_binding_after_sync(self) -> None:
        response = self._create_instance(gateway_id="gateway-study")
        instance_id = response.json()["id"]
        fingerprint = "open_xiaoai:LX06:SN003"
        self._report_discovery(gateway_id="gateway-study", fingerprint=fingerprint, sn="SN003")

        self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
            json={
                "action": "sync",
                "payload": {
                    "sync_scope": "device_sync",
                    "selected_external_ids": ["SN003"],
                },
            },
        )

        claimed_response = self._report_discovery(gateway_id="gateway-study", fingerprint=fingerprint, sn="SN003")
        self.assertTrue(claimed_response.json()["claimed"])
        self.assertTrue(claimed_response.json()["binding"]["terminal_id"])

    def test_open_xiaoai_device_control_uses_formal_plugin_route(self) -> None:
        device_id = self._sync_single_speaker(gateway_id="gateway-bedroom", sn="SN004")

        with patch(
            "app.modules.voice.realtime_service.voice_realtime_service.connection_manager.send_event",
            new=AsyncMock(),
        ) as mocked_send:
            with self.SessionLocal() as db:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=device_id,
                        action="play_pause",
                        params={},
                        reason="test.open_xiaoai.play_pause",
                    ),
                )

        self.assertEqual("open-xiaoai-speaker", result.plugin_id)
        self.assertEqual("open_xiaoai", result.platform)
        mocked_send.assert_awaited()
        event = mocked_send.await_args.kwargs["event"]
        self.assertEqual("play.stop", event.type)
        self.assertEqual("device_control", event.payload.reason)

    def test_open_xiaoai_device_control_turn_on_uses_formal_voice_command(self) -> None:
        device_id = self._sync_single_speaker(gateway_id="gateway-kitchen", sn="SN005")

        with patch(
            "app.modules.voice.realtime_service.voice_realtime_service.connection_manager.send_event",
            new=AsyncMock(),
        ) as mocked_send:
            with self.SessionLocal() as db:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=device_id,
                        action="turn_on",
                        params={},
                        reason="test.open_xiaoai.turn_on",
                    ),
                )

        self.assertEqual("open-xiaoai-speaker", result.plugin_id)
        self.assertEqual("speaker.turn_on", result.external_request["command"])
        event = mocked_send.await_args.kwargs["event"]
        self.assertEqual("speaker.turn_on", event.type)
        self.assertEqual("device_control", event.payload.reason)

    def test_open_xiaoai_device_control_set_volume_uses_formal_voice_command(self) -> None:
        device_id = self._sync_single_speaker(gateway_id="gateway-study", sn="SN006")

        with patch(
            "app.modules.voice.realtime_service.voice_realtime_service.connection_manager.send_event",
            new=AsyncMock(),
        ) as mocked_send:
            with self.SessionLocal() as db:
                result = execute_device_control(
                    db,
                    request=DeviceControlRequest(
                        household_id=self.household_id,
                        device_id=device_id,
                        action="set_volume",
                        params={"volume_pct": 35},
                        reason="test.open_xiaoai.set_volume",
                    ),
                )

        self.assertEqual("open-xiaoai-speaker", result.plugin_id)
        self.assertEqual("speaker.set_volume", result.external_request["command"])
        self.assertEqual(35, result.external_request["payload"]["volume_pct"])
        event = mocked_send.await_args.kwargs["event"]
        self.assertEqual("speaker.set_volume", event.type)
        self.assertEqual(35, event.payload.volume_pct)
        self.assertEqual("device_control", event.payload.reason)

    def _create_instance(self, *, gateway_id: str | None):
        config = {"gateway_id": gateway_id} if gateway_id is not None else {}
        return self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances",
            json={
                "household_id": self.household_id,
                "plugin_id": "open-xiaoai-speaker",
                "display_name": "客厅小爱网关",
                "config": config,
                "clear_secret_fields": [],
            },
        )

    def _report_discovery(self, *, gateway_id: str, fingerprint: str, sn: str, model: str = "LX06"):
        return self.client.post(
            f"{settings.api_v1_prefix}/integrations/discoveries/report",
            headers={"x-voice-gateway-token": settings.voice_gateway_token},
            json={
                "plugin_id": "open-xiaoai-speaker",
                "gateway_id": gateway_id,
                "fingerprint": fingerprint,
                "model": model,
                "sn": sn,
                "runtime_version": "1.0.0",
                "capabilities": ["audio_input", "audio_output", "playback_stop"],
                "remote_addr": "192.168.1.50",
                "connection_status": "online",
            },
        )

    def _sync_single_speaker(self, *, gateway_id: str, sn: str) -> str:
        response = self._create_instance(gateway_id=gateway_id)
        instance_id = response.json()["id"]
        fingerprint = f"open_xiaoai:LX06:{sn}"
        self._report_discovery(gateway_id=gateway_id, fingerprint=fingerprint, sn=sn)
        sync_response = self.client.post(
            f"{settings.api_v1_prefix}/integrations/instances/{instance_id}/actions",
            json={
                "action": "sync",
                "payload": {
                    "sync_scope": "device_sync",
                    "selected_external_ids": [sn],
                },
            },
        )
        self.assertEqual(200, sync_response.status_code)

        with self.SessionLocal() as db:
            binding = db.scalar(
                select(DeviceBinding).where(
                    DeviceBinding.integration_instance_id == instance_id,
                    DeviceBinding.external_device_id == sn,
                )
            )
            self.assertIsNotNone(binding)
            assert binding is not None
            return binding.device_id


if __name__ == "__main__":
    unittest.main()
