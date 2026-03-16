import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.v1.endpoints.channel_gateways import router as channel_gateways_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.channel.schemas import ChannelAccountCreate, MemberChannelBindingCreate
from app.modules.channel.service import (
    create_channel_account,
    create_member_binding,
    list_channel_delivery_records,
)
from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class _MockHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class ChannelGatewayBuiltinDeferredTests(unittest.TestCase):
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
        app.include_router(channel_gateways_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    @patch("app.plugins.builtin.channel_discord.channel.httpx.post")
    def test_discord_builtin_webhook_returns_deferred_response_and_processes_in_background(
        self,
        http_post_mock,
        run_orchestrated_turn_mock,
    ) -> None:
        http_post_mock.return_value = _MockHttpResponse({"id": "discord-msg-001"})

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Discord Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            member = create_member(
                db,
                MemberCreate(household_id=household.id, name="濡堝", role="admin"),
            )
            agent = create_agent(
                db,
                household_id=household.id,
                payload=AgentCreate(
                    display_name="闃跨",
                    agent_type="butler",
                    self_identity="鎴戞槸瀹跺涵绠″",
                    role_summary="璐熻矗瀹跺涵闂瓟",
                    personality_traits=["缁嗗績"],
                    service_focus=["鑱婂ぉ"],
                    default_entry=True,
                ),
            )
            run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
                intent=ConversationIntent.FREE_CHAT,
                text="浣犲ソ锛孌iscord 宸叉敹鍒般€?,
                degraded=False,
                facts=[],
                suggestions=[],
                memory_candidate_payloads=[],
                config_suggestion=None,
                action_payloads=[],
                ai_trace_id=None,
                ai_provider_code="mock-provider",
                effective_agent_id=agent.id,
                effective_agent_name=agent.display_name,
            )

            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            ).hex()

            account = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-discord",
                    account_code="discord-main",
                    display_name="Discord 涓昏处鍙?,
                    connection_mode="webhook",
                    config={
                        "bot_token": "discord-bot-token",
                        "application_public_key": public_key,
                    },
                    status="active",
                ),
            )
            create_member_binding(
                db,
                member_id=member.id,
                payload=MemberChannelBindingCreate(
                    channel_account_id=account.id,
                    member_id=member.id,
                    external_user_id="discord-user-001",
                    external_chat_id="channel-009",
                ),
            )
            db.commit()

            body_text = json.dumps(
                {
                    "type": 2,
                    "id": "interaction-001",
                    "application_id": "app-001",
                    "token": "interaction-token",
                    "channel_id": "channel-009",
                    "guild_id": "guild-001",
                    "member": {
                        "user": {
                            "id": "discord-user-001",
                            "username": "discord-alice",
                        }
                    },
                    "data": {
                        "name": "familyclaw",
                        "options": [{"name": "text", "type": 3, "value": "浣犲ソ"}],
                    },
                }
            )
            timestamp = "1710400000"
            signature = private_key.sign((timestamp + body_text).encode("utf-8")).hex()

            response = self.client.post(
                f"{settings.api_v1_prefix}/channel-gateways/accounts/{account.id}/webhook",
                headers={
                    "X-Signature-Ed25519": signature,
                    "X-Signature-Timestamp": timestamp,
                },
                content=body_text,
            )

            self.assertEqual(200, response.status_code)
            self.assertEqual({"type": 5}, response.json())

            with self.SessionLocal() as verify_db:
                deliveries = list_channel_delivery_records(verify_db, household_id=household.id)
                self.assertEqual(1, len(deliveries))
                self.assertEqual("sent", deliveries[0].status)
                self.assertEqual("discord-msg-001", deliveries[0].provider_message_ref)


if __name__ == "__main__":
    unittest.main()

