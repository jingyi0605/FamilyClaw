import json
import sys
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
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class ChannelGatewayApiTests(unittest.TestCase):
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
    def test_channel_gateway_webhook_records_standardized_event_and_deduplicates(
        self,
        run_orchestrated_turn_mock,
    ) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="浣犲ソ锛屾垜宸茬粡鏀跺埌娑堟伅銆?,
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id="agent-placeholder",
            effective_agent_name="闃跨",
        )
        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Gateway Home", city="Ningbo", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            db.flush()
            member = create_member(
                db,
                MemberCreate(household_id=household.id, name="鐖哥埜", role="admin"),
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
            db.flush()
            run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
                intent=ConversationIntent.FREE_CHAT,
                text="浣犲ソ锛屾垜宸茬粡鏀跺埌娑堟伅銆?,
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

            plugin_root = self._create_gateway_channel_plugin(
                Path(self._tempdir.name),
                plugin_id="gateway-channel-plugin",
            )
            register_plugin_mount(
                db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            db.flush()

            account = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="gateway-channel-plugin",
                    account_code="gateway-main",
                    display_name="Gateway 涓昏处鍙?,
                    connection_mode="webhook",
                    config={},
                    status="active",
                ),
            )
            create_member_binding(
                db,
                member_id=member.id,
                payload=MemberChannelBindingCreate(
                    channel_account_id=account.id,
                    member_id=member.id,
                    external_user_id="tg-user-001",
                    external_chat_id="chat:12345",
                ),
            )
            db.commit()

            response = self.client.post(
                f"{settings.api_v1_prefix}/channel-gateways/accounts/{account.id}/webhook?source=test",
                headers={"X-Test-Signature": "sig-001"},
                json={"event_id": "evt-001", "text": "hello"},
            )
            self.assertEqual(200, response.status_code)
            payload = response.json()
            self.assertTrue(payload["accepted"])
            self.assertTrue(payload["event_recorded"])
            self.assertFalse(payload["duplicate"])
            self.assertEqual("evt-001", payload["external_event_id"])
            self.assertEqual("dispatched", payload["processing_status"])
            self.assertEqual(member.id, payload["member_id"])
            self.assertIsNotNone(payload["conversation_session_id"])
            self.assertIsNotNone(payload["assistant_message_id"])
            self.assertIn("鏀跺埌娑堟伅", payload["reply_text"])
            self.assertEqual("sent", payload["delivery_status"])
            self.assertIsNotNone(payload["delivery_id"])
            self.assertEqual("provider-delivery-001", payload["provider_message_ref"])

            with self.SessionLocal() as verify_db:
                deliveries = list_channel_delivery_records(verify_db, household_id=household.id)
                self.assertEqual(1, len(deliveries))
                self.assertEqual("sent", deliveries[0].status)
                self.assertEqual("provider-delivery-001", deliveries[0].provider_message_ref)

            duplicate_response = self.client.post(
                f"{settings.api_v1_prefix}/channel-gateways/accounts/{account.id}/webhook",
                json={"event_id": "evt-001", "text": "hello-again"},
            )
            self.assertEqual(200, duplicate_response.status_code)
            duplicate_payload = duplicate_response.json()
            self.assertTrue(duplicate_payload["accepted"])
            self.assertTrue(duplicate_payload["duplicate"])
            self.assertEqual(payload["inbound_event_id"], duplicate_payload["inbound_event_id"])
            self.assertEqual("dispatched", duplicate_payload["processing_status"])
            self.assertEqual(payload["conversation_session_id"], duplicate_payload["conversation_session_id"])
            self.assertIsNone(duplicate_payload["delivery_id"])

    def _create_gateway_channel_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "Gateway 閫氶亾鎻掍欢",
                    "version": "0.1.0",
                    "types": ["channel"],
                    "permissions": ["channel.receive"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"channel": "plugin.channel.handle"},
                    "capabilities": {
                        "channel": {
                            "platform_code": "telegram",
                            "inbound_modes": ["webhook"],
                            "delivery_modes": ["reply"],
                            "reserved": False,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "channel.py").write_text(
            "import json\n"
            "\n"
            "def handle(payload=None):\n"
            "    data = payload or {}\n"
            "    action = data.get('action')\n"
            "    if action == 'send':\n"
            "        delivery = data.get('delivery', {})\n"
            "        return {\n"
            "            'provider_message_ref': 'provider-delivery-001',\n"
            "            'target': delivery.get('external_conversation_key'),\n"
            "        }\n"
            "    request = data.get('request', {})\n"
            "    body_text = request.get('body_text', '{}')\n"
            "    body = json.loads(body_text or '{}')\n"
            "    return {\n"
            "        'message': 'accepted by plugin',\n"
            "        'event': {\n"
            "            'external_event_id': body.get('event_id', 'evt-missing'),\n"
            "            'event_type': 'message',\n"
            "            'external_user_id': 'tg-user-001',\n"
            "            'external_conversation_key': 'chat:12345',\n"
            "            'normalized_payload': {\n"
            "                'text': body.get('text', ''),\n"
            "                'chat_type': 'direct',\n"
            "                'headers': request.get('headers', {}),\n"
            "                'query_params': request.get('query_params', {}),\n"
            "            },\n"
            "            'status': 'received',\n"
            "        }\n"
            "    }\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()

