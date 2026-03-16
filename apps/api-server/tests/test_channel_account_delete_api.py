import tempfile
import unittest
from pathlib import Path

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
from app.modules.channel import repository as channel_repository
from app.modules.channel.binding_service import create_channel_account_binding
from app.modules.channel.schemas import ChannelDeliveryCreate, ChannelInboundEventCreate, MemberChannelBindingCreate
from app.modules.channel.service import create_channel_delivery, record_channel_inbound_event
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ChannelAccountDeleteApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

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
                HouseholdCreate(name="Delete Account Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            self.household_id = self.household.id
            db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_delete_channel_account_removes_related_channel_records(self) -> None:
        create_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts",
            json={
                "plugin_id": "channel-telegram",
                "display_name": "瀹跺涵 Telegram 鍔╂墜",
                "connection_mode": "polling",
                "config": {
                    "bot_token": "telegram-token-001",
                },
                "status": "active",
            },
        )
        self.assertEqual(201, create_response.status_code)
        account_id = create_response.json()["id"]

        with self.SessionLocal() as db:
            member = create_member(
                db,
                MemberCreate(
                    household_id=self.household_id,
                    name="娴嬭瘯鎴愬憳",
                    role="adult",
                    age_group="adult",
                ),
            )
            db.flush()
            binding = create_channel_account_binding(
                db,
                household_id=self.household_id,
                payload=MemberChannelBindingCreate(
                    channel_account_id=account_id,
                    member_id=member.id,
                    external_user_id="tg-user-001",
                    external_chat_id="chat-001",
                    display_hint="娴嬭瘯鐢ㄦ埛",
                ),
            )
            inbound_event, _ = record_channel_inbound_event(
                db,
                payload=ChannelInboundEventCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_event_id="evt-delete-001",
                    event_type="message",
                    external_user_id="tg-user-001",
                    external_conversation_key="chat:001",
                    normalized_payload={"text": "hello"},
                    status="ignored",
                    error_code="channel_member_binding_not_found",
                ),
            )
            delivery = create_channel_delivery(
                db,
                payload=ChannelDeliveryCreate(
                    household_id=self.household_id,
                    channel_account_id=account_id,
                    external_conversation_key="chat:001",
                    delivery_type="reply",
                    request_payload={"text": "ok"},
                    status="sent",
                ),
            )
            self.binding_id = binding.id
            self.inbound_event_id = inbound_event.id
            self.delivery_id = delivery.id
            db.commit()

        delete_response = self.client.delete(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts/{account_id}"
        )
        self.assertEqual(204, delete_response.status_code)

        list_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-accounts"
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual([], list_response.json())

        deliveries_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-deliveries",
            params={"channel_account_id": account_id},
        )
        self.assertEqual(200, deliveries_response.status_code)
        self.assertEqual([], deliveries_response.json())

        inbound_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/channel-inbound-events",
            params={"channel_account_id": account_id},
        )
        self.assertEqual(200, inbound_response.status_code)
        self.assertEqual([], inbound_response.json())

        with self.SessionLocal() as db:
            self.assertIsNone(channel_repository.get_channel_plugin_account(db, account_id))
            self.assertIsNone(channel_repository.get_member_channel_binding(db, self.binding_id))
            self.assertIsNone(channel_repository.get_channel_inbound_event(db, self.inbound_event_id))
            self.assertIsNone(channel_repository.get_channel_delivery(db, self.delivery_id))


if __name__ == "__main__":
    unittest.main()

