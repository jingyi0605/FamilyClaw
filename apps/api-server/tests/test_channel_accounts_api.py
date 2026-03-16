import json
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
from app.api.v1.endpoints.channel_accounts import router as channel_accounts_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.channel.schemas import ChannelDeliveryCreate, ChannelInboundEventCreate
from app.modules.channel.service import create_channel_delivery, record_channel_inbound_event
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled


class _MockHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class ChannelAccountsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

        app = FastAPI()
        app.include_router(channel_accounts_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_id="admin-account-001",
            account_type="member",
            account_status="active",
            username="admin",
            household_id=self.household_id if hasattr(self, "household_id") else None,
            member_id="member-admin-001",
            is_authenticated=True,
        )
        self.client = TestClient(app)

        with self.SessionLocal() as db:
            self.household = create_household(
                db,
                HouseholdCreate(name="Channel Admin Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            self.household_id = self.household.id
            db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    @patch("app.plugins.builtin.channel_telegram.channel.httpx.get")
    def test_channel_account_admin_endpoints_cover_probe_status_and_recent_records(self, telegram_http_get) -> None:
        telegram_http_get.return_value = _MockHttpResponse(
            {"ok": True, "result": {"id": 123456, "username": "familyclaw_bot"}}
        )

        create_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts",
            json={
                "plugin_id": "channel-telegram",
                "account_code": "telegram-main",
                "display_name": "Telegram 主账号",
                "connection_mode": "polling",
                "config": {
                    "bot_token": "telegram-token-001",
                },
                "status": "draft",
            },
        )
        self.assertEqual(201, create_response.status_code)
        account_payload = create_response.json()
        account_id = account_payload["id"]
        self.assertEqual("telegram", account_payload["platform_code"])

        list_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts"
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual(1, len(list_response.json()))

        update_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}",
            json={
                "display_name": "Telegram 正式账号",
                "status": "active",
            },
        )
        self.assertEqual(200, update_response.status_code)
        self.assertEqual("Telegram 正式账号", update_response.json()["display_name"])

        with self.SessionLocal() as db:
            record_channel_inbound_event(
                db,
                payload=ChannelInboundEventCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_event_id="evt-ok-001",
                    event_type="message",
                    external_user_id="tg-user-001",
                    external_conversation_key="chat:12345",
                    normalized_payload={"text": "hello", "chat_type": "direct"},
                    status="dispatched",
                ),
            )
            record_channel_inbound_event(
                db,
                payload=ChannelInboundEventCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_event_id="evt-fail-001",
                    event_type="message",
                    external_user_id="tg-user-002",
                    external_conversation_key="chat:54321",
                    normalized_payload={"text": "bad", "chat_type": "direct"},
                    status="failed",
                    error_code="channel_delivery_failed",
                    error_message="probe-failure",
                ),
            )
            create_channel_delivery(
                db,
                payload=ChannelDeliveryCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_conversation_key="chat:12345",
                    delivery_type="reply",
                    request_payload={"text": "ok"},
                    status="sent",
                    provider_message_ref="msg-ok-001",
                ),
            )
            create_channel_delivery(
                db,
                payload=ChannelDeliveryCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_conversation_key="chat:54321",
                    delivery_type="reply",
                    request_payload={"text": "fail"},
                    status="failed",
                    last_error_code="telegram_send_failed",
                    last_error_message="network-error",
                ),
            )
            db.commit()

        probe_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}/probe"
        )
        self.assertEqual(200, probe_response.status_code)
        probe_payload = probe_response.json()
        self.assertEqual("ok", probe_payload["account"]["last_probe_status"])
        self.assertEqual("active", probe_payload["account"]["status"])
        self.assertEqual(1, probe_payload["recent_failure_summary"]["recent_failure_count"])

        status_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}/status"
        )
        self.assertEqual(200, status_response.status_code)
        status_payload = status_response.json()
        self.assertEqual("failed", status_payload["latest_delivery"]["status"])
        self.assertEqual("network-error", status_payload["latest_delivery"]["last_error_message"])
        self.assertEqual("evt-fail-001", status_payload["latest_failed_inbound_event"]["external_event_id"])
        self.assertEqual(2, status_payload["recent_delivery_count"])
        self.assertEqual(2, status_payload["recent_inbound_count"])

        deliveries_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-deliveries",
            params={"channel_account_id": account_id, "status": "failed"},
        )
        self.assertEqual(200, deliveries_response.status_code)
        deliveries_payload = deliveries_response.json()
        self.assertEqual(1, len(deliveries_payload))
        self.assertEqual("failed", deliveries_payload[0]["status"])

        inbound_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-inbound-events",
            params={"channel_account_id": account_id, "status": "failed"},
        )
        self.assertEqual(200, inbound_response.status_code)
        inbound_payload = inbound_response.json()
        self.assertEqual(1, len(inbound_payload))
        self.assertEqual("evt-fail-001", inbound_payload[0]["external_event_id"])

    def test_create_channel_account_rejects_disabled_channel_plugin(self) -> None:
        with self.SessionLocal() as db:
            set_household_plugin_enabled(
                db,
                household_id=self.household_id,
                plugin_id="channel-dingtalk",
                payload=PluginStateUpdateRequest(enabled=False),
            )
            db.commit()

        response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts",
            json={
                "plugin_id": "channel-dingtalk",
                "account_code": "dingtalk-main",
                "display_name": "钉钉主账号",
                "connection_mode": "polling",
                "config": {
                    "app_key": "ding-app-key",
                },
                "status": "draft",
            },
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("channel plugin is disabled for current household", response.json()["detail"])

    def test_probe_channel_account_rejects_disabled_channel_plugin(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts",
            json={
                "plugin_id": "channel-telegram",
                "account_code": "telegram-main",
                "display_name": "Telegram 主账号",
                "connection_mode": "polling",
                "config": {
                    "bot_token": "telegram-token-001",
                },
                "status": "draft",
            },
        )
        self.assertEqual(201, create_response.status_code)
        account_id = create_response.json()["id"]

        with self.SessionLocal() as db:
            set_household_plugin_enabled(
                db,
                household_id=self.household_id,
                plugin_id="channel-telegram",
                payload=PluginStateUpdateRequest(enabled=False),
            )
            db.commit()

        probe_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}/probe"
        )
        self.assertEqual(400, probe_response.status_code)
        self.assertEqual("channel plugin is disabled for current household", probe_response.json()["detail"])

    def test_update_channel_account_rejects_disabled_channel_plugin(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts",
            json={
                "plugin_id": "channel-telegram",
                "account_code": "telegram-main",
                "display_name": "Telegram 主账号",
                "connection_mode": "polling",
                "config": {
                    "bot_token": "telegram-token-001",
                },
                "status": "draft",
            },
        )
        self.assertEqual(201, create_response.status_code)
        account_id = create_response.json()["id"]

        with self.SessionLocal() as db:
            set_household_plugin_enabled(
                db,
                household_id=self.household_id,
                plugin_id="channel-telegram",
                payload=PluginStateUpdateRequest(enabled=False),
            )
            db.commit()

        update_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}",
            json={"status": "active"},
        )
        self.assertEqual(404, update_response.status_code)
        self.assertEqual("channel plugin is disabled for current household", update_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
