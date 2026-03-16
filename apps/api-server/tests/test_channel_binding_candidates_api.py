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
from app.api.v1.endpoints.channel_gateways import router as channel_gateways_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.channel import repository as channel_repository
from app.modules.channel.polling_service import poll_channel_account
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.channel.schemas import ChannelAccountCreate
from app.modules.channel.service import create_channel_account
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


class ChannelBindingCandidatesApiTests(unittest.TestCase):
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
        app.include_router(channel_gateways_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _override_admin_actor() -> ActorContext:
            return ActorContext(
                role="admin",
                actor_type="admin",
                actor_id="test-admin",
                account_type="system",
                account_status="active",
                username="test-admin",
                is_authenticated=True,
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = _override_admin_actor
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def _poll_account(self, household_id: str, account_id: str) -> None:
        with self.SessionLocal() as db:
            poll_channel_account(
                db,
                household_id=household_id,
                account_id=account_id,
            )
            db.commit()

    @patch("app.plugins.builtin.channel_telegram.channel.httpx.post")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_candidate_endpoint_and_binding_closure(
        self,
        run_orchestrated_turn_mock,
        http_post_mock,
    ) -> None:
        poll_batches = [
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1001,
                        "message": {
                            "message_id": 2001,
                            "text": "鍏堟潵鎵撲釜鎷涘懠",
                            "chat": {"id": 3001, "type": "private"},
                            "from": {
                                "id": 4001,
                                "username": "candidate_a",
                                "first_name": "Alice",
                            },
                        },
                    },
                    {
                        "update_id": 1002,
                        "message": {
                            "message_id": 2002,
                            "text": "杩欐槸鏇存柊鐨勪竴鏉℃秷鎭?,
                            "chat": {"id": 3001, "type": "private"},
                            "from": {
                                "id": 4001,
                                "username": "candidate_a_latest",
                                "first_name": "Alice",
                                "last_name": "Wong",
                            },
                        },
                    },
                ],
            },
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1003,
                        "message": {
                            "message_id": 2003,
                            "text": "鍙︿竴涓?bot 鐨勬秷鎭?,
                            "chat": {"id": 3002, "type": "private"},
                            "from": {
                                "id": 4001,
                                "username": "candidate_b",
                                "first_name": "Bob",
                            },
                        },
                    }
                ],
            },
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 1004,
                        "message": {
                            "message_id": 2004,
                            "text": "缁戝畾鍚庡啀鍙戜竴鏉?,
                            "chat": {"id": 3001, "type": "private"},
                            "from": {
                                "id": 4001,
                                "username": "candidate_a_latest",
                                "first_name": "Alice",
                                "last_name": "Wong",
                            },
                        },
                    }
                ],
            },
        ]

        def telegram_post_side_effect(url, **kwargs):
            if url.endswith("/getUpdates"):
                if poll_batches:
                    return _MockHttpResponse(poll_batches.pop(0))
                return _MockHttpResponse({"ok": True, "result": []})
            if url.endswith("/sendMessage"):
                return _MockHttpResponse({"ok": True, "result": {"message_id": 6001}})
            if url.endswith("/deleteWebhook"):
                return _MockHttpResponse({"ok": True, "result": True})
            raise AssertionError(f"unexpected telegram api url: {url}")

        http_post_mock.side_effect = telegram_post_side_effect

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="鍊欓€夌粦瀹氬搴?, city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            member_x = create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 X", role="adult"),
            )
            create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 Y", role="adult"),
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
                text="鎴戝凡缁忔敹鍒板苟澶勭悊浜嗘秷鎭€?,
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

            account_a = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-a",
                    display_name="Telegram Bot A",
                    connection_mode="polling",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            account_b = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-b",
                    display_name="Telegram Bot B",
                    connection_mode="polling",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            db.commit()

            household_id = household.id
            member_x_id = member_x.id
            account_a_id = account_a.id
            account_b_id = account_b.id

        self._poll_account(household_id, account_a_id)
        self._poll_account(household_id, account_b_id)

        candidates_a_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/binding-candidates",
        )
        self.assertEqual(200, candidates_a_response.status_code)
        candidates_a = candidates_a_response.json()
        self.assertEqual(1, len(candidates_a))
        self.assertEqual("4001", candidates_a[0]["external_user_id"])
        self.assertEqual("3001", candidates_a[0]["external_chat_id"])
        self.assertEqual("Alice Wong", candidates_a[0]["sender_display_name"])
        self.assertEqual("candidate_a_latest", candidates_a[0]["username"])
        self.assertEqual("杩欐槸鏇存柊鐨勪竴鏉℃秷鎭?, candidates_a[0]["last_message_text"])
        self.assertEqual(account_a_id, candidates_a[0]["channel_account_id"])
        self.assertEqual("telegram", candidates_a[0]["platform_code"])

        candidates_b_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_b_id}/binding-candidates",
        )
        self.assertEqual(200, candidates_b_response.status_code)
        candidates_b = candidates_b_response.json()
        self.assertEqual(1, len(candidates_b))
        self.assertEqual("鍙︿竴涓?bot 鐨勬秷鎭?, candidates_b[0]["last_message_text"])

        create_binding_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/bindings",
            json={
                "channel_account_id": account_a_id,
                "member_id": member_x_id,
                "external_user_id": "4001",
                "external_chat_id": "3001",
                "display_hint": "浠庡€欓€夐濉?,
                "binding_status": "active",
            },
        )
        self.assertEqual(201, create_binding_response.status_code)

        empty_candidates_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/binding-candidates",
        )
        self.assertEqual(200, empty_candidates_response.status_code)
        self.assertEqual([], empty_candidates_response.json())

        self._poll_account(household_id, account_a_id)

        with self.SessionLocal() as db:
            account_a = db.get(app.db.models.ChannelPluginAccount, account_a_id)
            assert account_a is not None
            self.assertIsNotNone(account_a.last_inbound_at)
            inbound_events = channel_repository.list_channel_inbound_events(db, household_id=household_id)
            self.assertTrue(
                any(
                    item.channel_account_id == account_a_id
                    and item.external_event_id == "1004"
                    and item.status == "dispatched"
                    for item in inbound_events
                )
            )

        run_orchestrated_turn_mock.assert_called()
        send_urls = [call.args[0] for call in http_post_mock.call_args_list if call.args and call.args[0].endswith("/sendMessage")]
        self.assertGreaterEqual(len(send_urls), 1)

    @patch("app.plugins.builtin.channel_telegram.channel.httpx.post")
    def test_delete_binding_endpoint_removes_binding(
        self,
        http_post_mock,
    ) -> None:
        http_post_mock.return_value = _MockHttpResponse({"ok": True, "result": []})

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Delete Binding Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            member = create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 X", role="adult"),
            )
            account = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-delete",
                    display_name="Telegram Delete",
                    connection_mode="polling",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            db.commit()

            household_id = household.id
            member_id = member.id
            account_id = account.id

        create_binding_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings",
            json={
                "channel_account_id": account_id,
                "member_id": member_id,
                "external_user_id": "5001",
                "external_chat_id": "7001",
                "binding_status": "active",
            },
        )
        self.assertEqual(201, create_binding_response.status_code)
        binding_id = create_binding_response.json()["id"]

        delete_response = self.client.delete(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings/{binding_id}",
        )
        self.assertEqual(204, delete_response.status_code)
        self.assertEqual(b"", delete_response.content)

        list_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings",
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual([], list_response.json())

    @patch("app.plugins.builtin.channel_telegram.channel.httpx.post")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def _legacy_test_candidate_endpoint_and_binding_closure(
        self,
        run_orchestrated_turn_mock,
        http_post_mock,
    ) -> None:
        http_post_mock.return_value = _MockHttpResponse({"ok": True, "result": {"message_id": 6001}})

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="鍊欓€夌粦瀹氬搴?, city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            member_x = create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 X", role="adult"),
            )
            create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 Y", role="adult"),
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
                text="鎴戝凡缁忔敹鍒板苟澶勭悊浜嗘秷鎭€?,
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

            account_a = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-a",
                    display_name="Telegram Bot A",
                    connection_mode="webhook",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            account_b = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-b",
                    display_name="Telegram Bot B",
                    connection_mode="webhook",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            db.commit()

            household_id = household.id
            member_x_id = member_x.id
            account_a_id = account_a.id
            account_b_id = account_b.id

        first_response = self.client.post(
            f"{settings.api_v1_prefix}/channel-gateways/accounts/{account_a_id}/webhook",
            json={
                "update_id": 1001,
                "message": {
                    "message_id": 2001,
                    "text": "鍏堟潵鎵撲釜鎷涘懠",
                    "chat": {"id": 3001, "type": "private"},
                    "from": {
                        "id": 4001,
                        "username": "candidate_a",
                        "first_name": "Alice",
                    },
                },
            },
        )
        self.assertEqual(200, first_response.status_code)
        self.assertEqual("ignored", first_response.json()["processing_status"])

        second_response = self.client.post(
            f"{settings.api_v1_prefix}/channel-gateways/accounts/{account_a_id}/webhook",
            json={
                "update_id": 1002,
                "message": {
                    "message_id": 2002,
                    "text": "杩欐槸鏇存柊鐨勪竴鏉℃秷鎭?,
                    "chat": {"id": 3001, "type": "private"},
                    "from": {
                        "id": 4001,
                        "username": "candidate_a_latest",
                        "first_name": "Alice",
                        "last_name": "Wong",
                    },
                },
            },
        )
        self.assertEqual(200, second_response.status_code)
        self.assertEqual("ignored", second_response.json()["processing_status"])

        third_response = self.client.post(
            f"{settings.api_v1_prefix}/channel-gateways/accounts/{account_b_id}/webhook",
            json={
                "update_id": 1003,
                "message": {
                    "message_id": 2003,
                    "text": "鍙︿竴涓?bot 鐨勬秷鎭?,
                    "chat": {"id": 3002, "type": "private"},
                    "from": {
                        "id": 4001,
                        "username": "candidate_b",
                        "first_name": "Bob",
                    },
                },
            },
        )
        self.assertEqual(200, third_response.status_code)

        candidates_a_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/binding-candidates",
        )
        self.assertEqual(200, candidates_a_response.status_code)
        candidates_a = candidates_a_response.json()
        self.assertEqual(1, len(candidates_a))
        self.assertEqual("4001", candidates_a[0]["external_user_id"])
        self.assertEqual("3001", candidates_a[0]["external_chat_id"])
        self.assertEqual("Alice Wong", candidates_a[0]["sender_display_name"])
        self.assertEqual("candidate_a_latest", candidates_a[0]["username"])
        self.assertEqual("杩欐槸鏇存柊鐨勪竴鏉℃秷鎭?, candidates_a[0]["last_message_text"])
        self.assertEqual(account_a_id, candidates_a[0]["channel_account_id"])
        self.assertEqual("telegram", candidates_a[0]["platform_code"])

        candidates_b_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_b_id}/binding-candidates",
        )
        self.assertEqual(200, candidates_b_response.status_code)
        candidates_b = candidates_b_response.json()
        self.assertEqual(1, len(candidates_b))
        self.assertEqual("鍙︿竴涓?bot 鐨勬秷鎭?, candidates_b[0]["last_message_text"])

        create_binding_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/bindings",
            json={
                "channel_account_id": account_a_id,
                "member_id": member_x_id,
                "external_user_id": "4001",
                "external_chat_id": "3001",
                "display_hint": "浠庡€欓€夐濉?,
                "binding_status": "active",
            },
        )
        self.assertEqual(201, create_binding_response.status_code)

        empty_candidates_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_a_id}/binding-candidates",
        )
        self.assertEqual(200, empty_candidates_response.status_code)
        self.assertEqual([], empty_candidates_response.json())

        bound_response = self.client.post(
            f"{settings.api_v1_prefix}/channel-gateways/accounts/{account_a_id}/webhook",
            json={
                "update_id": 1004,
                "message": {
                    "message_id": 2004,
                    "text": "缁戝畾鍚庡啀鍙戜竴鏉?,
                    "chat": {"id": 3001, "type": "private"},
                    "from": {
                        "id": 4001,
                        "username": "candidate_a_latest",
                        "first_name": "Alice",
                        "last_name": "Wong",
                    },
                },
            },
        )
        self.assertEqual(200, bound_response.status_code)
        payload = bound_response.json()
        self.assertEqual("dispatched", payload["processing_status"])
        self.assertEqual(member_x_id, payload["member_id"])
        self.assertIsNotNone(payload["conversation_session_id"])
        self.assertEqual("sent", payload["delivery_status"])

    @patch("app.plugins.builtin.channel_telegram.channel.httpx.post")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def _legacy_test_delete_binding_endpoint_removes_binding(
        self,
        run_orchestrated_turn_mock,
        http_post_mock,
    ) -> None:
        http_post_mock.return_value = _MockHttpResponse({"ok": True, "result": {"message_id": 6002}})
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="ok",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id="agent-id",
            effective_agent_name="agent-name",
        )

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="Delete Binding Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            member = create_member(
                db,
                MemberCreate(household_id=household.id, name="鎴愬憳 X", role="adult"),
            )
            account = create_channel_account(
                db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-delete",
                    display_name="Telegram Delete",
                    connection_mode="webhook",
                    config={"bot_token": "telegram-token"},
                    status="active",
                ),
            )
            db.commit()

            household_id = household.id
            member_id = member.id
            account_id = account.id

        create_binding_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings",
            json={
                "channel_account_id": account_id,
                "member_id": member_id,
                "external_user_id": "5001",
                "external_chat_id": "7001",
                "binding_status": "active",
            },
        )
        self.assertEqual(201, create_binding_response.status_code)
        binding_id = create_binding_response.json()["id"]

        delete_response = self.client.delete(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings/{binding_id}",
        )
        self.assertEqual(204, delete_response.status_code)
        self.assertEqual(b"", delete_response.content)

        list_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{household_id}/channel-accounts/{account_id}/bindings",
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual([], list_response.json())


if __name__ == "__main__":
    unittest.main()

