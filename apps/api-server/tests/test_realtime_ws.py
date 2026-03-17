import asyncio
import re
import tempfile
import time
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import httpx
from fastapi import HTTPException, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, QueryParams

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.account.schemas import BootstrapAccountCompleteRequest
from app.modules.account.service import (
    authenticate_account,
    complete_bootstrap_account,
    create_account_session,
    ensure_pending_household_bootstrap_accounts,
)
from app.modules.agent import repository as agent_repository
from app.modules.agent.models import FamilyAgentBootstrapMessage, FamilyAgentBootstrapSession
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import create_conversation_session
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.invoke import LlmResult, LlmStreamEvent
from app.modules.llm_task.output_models import ButlerBootstrapOutput, ProposalBatchExtractionOutput, ProposalExtractionItemOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.memory.schemas import MemoryCardManualCreate
from app.modules.memory.service import create_manual_memory_card
from app.modules.realtime.connection_manager import realtime_connection_manager
from tests.test_db_support import PostgresTestDatabase


class _FakeWebSocket:
    def __init__(self, *, household_id: str, session_id: str, cookie: str | None = None, inbound_messages: list[dict] | None = None):
        self.query_params = QueryParams({"household_id": household_id, "session_id": session_id})
        self.headers = Headers({"cookie": cookie} if cookie else {})
        self.client = SimpleNamespace(host="test-client", port=12345)
        self._inbound_messages = list(inbound_messages or [])
        self.accepted = False
        self.sent_messages: list[dict] = []
        self.close_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.sent_messages.append(payload)

    async def receive_json(self) -> dict:
        if self._inbound_messages:
            return self._inbound_messages.pop(0)
        raise WebSocketDisconnect(code=1000)

    async def close(self, code: int = 1000) -> None:
        self.close_code = code


class _BrokenWebSocket(_FakeWebSocket):
    async def send_json(self, payload: dict) -> None:
        raise RuntimeError("broken websocket")


class RealtimeWsTests(unittest.TestCase):
    @staticmethod
    async def _async_iter_events(events: list[object]):
        for event in events:
            yield event

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_session_local = db_session_module.SessionLocal

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal

        import app.api.v1.endpoints.realtime as realtime_endpoint_module

        self._realtime_endpoint_module = realtime_endpoint_module
        self._previous_realtime_session_local = realtime_endpoint_module.SessionLocal
        realtime_endpoint_module.SessionLocal = self.SessionLocal

        self.db: Session = self.SessionLocal()
        ensure_pending_household_bootstrap_accounts(self.db)

        household = create_household(
            self.db,
            HouseholdCreate(name="Realtime Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )
        self.db.flush()

        bootstrap = authenticate_account(self.db, "user", "user")
        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=household.id,
                member_id=member.id,
                username="owner",
                password="owner123",
            ),
        )
        _, token = create_account_session(self.db, account.id)

        session = FamilyAgentBootstrapSession(
            id=new_uuid(),
            household_id=household.id,
            status="collecting",
            pending_field="display_name",
            draft_json=(
                '{"household_id": "%s", "display_name": "", "speaking_style": "", "personality_traits": []}'
                % household.id
            ),
            transcript_json="[]",
            current_request_id=None,
            last_event_seq=0,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        agent_repository.add_bootstrap_session(self.db, session)
        self.db.flush()
        agent_repository.add_bootstrap_message(
            self.db,
            FamilyAgentBootstrapMessage(
                id=new_uuid(),
                session_id=session.id,
                request_id=None,
                role="assistant",
                content="你好，先告诉我你想让我叫什么。",
                seq=1,
                created_at=utc_now_iso(),
            ),
        )
        self.db.commit()

        self.household_id = household.id
        self.session_id = session.id
        self.cookie_header = f"{settings.auth_session_cookie_name}={token}"
        self.member_id = member.id

        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="小管家",
                agent_type="butler",
                self_identity="我是家庭小助手。",
                role_summary="负责家庭问答",
                personality_traits=["细心", "稳重"],
                service_focus=["家庭问答"],
                default_entry=True,
            ),
        )
        self.db.flush()

        from app.api.dependencies import ActorContext

        self.member_actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id=member.id,
            account_id=account.id,
            account_type="household",
            account_status="active",
            username="owner",
            household_id=household.id,
            member_id=member.id,
            member_role="admin",
            is_authenticated=True,
        )
        conversation_session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=household.id,
                active_agent_id=agent.id,
            ),
            actor=self.member_actor,
        )
        self.db.commit()
        self.conversation_session_id = conversation_session.id

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        db_session_module.SessionLocal = self._previous_session_local
        self._realtime_endpoint_module.SessionLocal = self._previous_realtime_session_local
        self._tempdir.cleanup()

    def test_agent_bootstrap_connect_and_ping(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "ping", "session_id": self.session_id, "payload": {"nonce": "abc"}}],
        )
        asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))
        self.assertEqual(["session.ready", "session.snapshot", "pong"], [item["type"] for item in websocket.sent_messages])

    def test_agent_bootstrap_success_persists_request(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.session_id, "request_id": "request-1", "payload": {"text": "我想叫阿福。"}}],
        )

        from app.modules.agent import bootstrap_service as bootstrap_service_module

        with patch.object(bootstrap_service_module, "_ensure_bootstrap_allowed", return_value=None), patch.object(
            bootstrap_service_module,
            "stream_llm",
            return_value=self._async_iter_events(
                [
                    LlmStreamEvent("chunk", content="你好，我先记下这个名字。"),
                    LlmStreamEvent("done", result=LlmResult(raw_text="你好，我先记下这个名字。", display_text="你好，我先记下这个名字。")),
                ]
            ),
        ), patch.object(
            bootstrap_service_module,
            "ainvoke_llm",
            return_value=LlmResult(
                raw_text='{"display_name":"阿福","speaking_style":"温和直接","personality_traits":["细心","稳重"],"is_complete":true}',
                display_text="",
                parsed=ButlerBootstrapOutput(display_name="阿福", speaking_style="温和直接", personality_traits=["细心", "稳重"], is_complete=True),
            ),
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=self.session_id)
        self.assertEqual(1, len(request_rows))
        self.assertEqual("succeeded", request_rows[0].status)
        self.assertEqual("阿福", websocket.sent_messages[4]["payload"]["display_name"])

    def test_agent_bootstrap_failure_marks_request_failed(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.session_id, "request_id": "request-failed", "payload": {"text": "再试一次。"}}],
        )

        from app.modules.agent import bootstrap_service as bootstrap_service_module

        with patch.object(bootstrap_service_module, "_ensure_bootstrap_allowed", return_value=None), patch.object(
            bootstrap_service_module,
            "stream_llm",
            side_effect=HTTPException(status_code=409, detail="上一轮还没结束，请稍后再试"),
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=self.session_id)
        self.assertEqual("failed", request_rows[0].status)
        self.assertEqual("request_conflict", request_rows[0].error_code)

    def test_agent_bootstrap_stream_failure_keeps_partial_text(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.session_id, "request_id": "request-partial", "payload": {"text": "I want a gentler butler"}}],
        )

        from app.modules.ai_gateway.provider_runtime import ProviderRuntimeError
        from app.modules.agent import bootstrap_service as bootstrap_service_module

        async def _fake_stream_llm(_db, **kwargs):
            _ = kwargs
            yield LlmStreamEvent("chunk", content="Let me note ")
            yield LlmStreamEvent("chunk", content="that gentle direction.")
            raise ProviderRuntimeError("timeout", "provider request timeout")

        with patch.object(bootstrap_service_module, "_ensure_bootstrap_allowed", return_value=None), patch.object(
            bootstrap_service_module,
            "stream_llm",
            side_effect=_fake_stream_llm,
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=self.session_id)
        self.assertEqual("failed", request_rows[0].status)
        self.assertEqual("provider_stream_failed", request_rows[0].error_code)
        self.assertEqual("session.snapshot", websocket.sent_messages[-1]["type"])
        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual("collecting", final_snapshot["status"])
        self.assertTrue(any("gentle direction" in item["content"] for item in final_snapshot["messages"] if item["role"] == "assistant"))

    def test_conversation_successful_turn_persists_reply(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-1", "payload": {"text": "hello"}}],
        )

        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("chunk", "你好，")
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="你好，我是小管家。", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-conversation", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="小管家"))

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch.object(
            conversation_service_module,
            "aextract_proposal_batch",
            return_value=ProposalBatchExtractionOutput(),
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual("你好，我是小管家。", final_snapshot["messages"][1]["content"])

    def test_conversation_stale_socket_failure_does_not_lose_reply(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-2", "payload": {"text": "你好"}}],
        )
        broken_socket = _BrokenWebSocket(household_id=self.household_id, session_id=self.conversation_session_id, cookie=self.cookie_header)
        realtime_connection_manager.register(household_id=self.household_id, session_id=self.conversation_session_id, websocket=cast(Any, broken_socket))

        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="你好，我是小管家。", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-stale", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="小管家"))

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch.object(
            conversation_service_module,
            "aextract_proposal_batch",
            return_value=ProposalBatchExtractionOutput(),
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual("你好，我是小管家。", final_snapshot["messages"][1]["content"])

    def test_conversation_stream_failure_keeps_partial_text(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-partial", "payload": {"text": "讲个科幻故事"}}],
        )

        from app.modules.ai_gateway.provider_runtime import ProviderRuntimeError
        from app.modules.conversation import service as conversation_service_module

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("chunk", "很久很久以前，")
            yield ("chunk", "火星边缘漂着一座旧空间站。")
            raise ProviderRuntimeError("timeout", "provider request timeout")

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual("failed", final_snapshot["messages"][1]["status"])
        self.assertIn("很久很久以前", final_snapshot["messages"][1]["content"])

    def test_conversation_postprocess_failure_does_not_mark_reply_failed(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-postprocess-failed", "payload": {"text": "你叫什么？"}}],
        )

        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("chunk", "我是")
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="我是妞妞。", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-postprocess", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="妞妞"))

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch.object(
            conversation_service_module,
            "aextract_proposal_batch",
            side_effect=RuntimeError("proposal postprocess boom"),
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual("completed", final_snapshot["messages"][1]["status"])
        self.assertEqual("我是妞妞。", final_snapshot["messages"][1]["content"])

    def test_conversation_memory_recall_answer_does_not_create_proposal(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-memory-recall", "payload": {"text": "你知道我最喜欢吃什么吗"}}],
        )

        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="根据我的记录，你特别喜欢巧克力蛋糕和甜食。", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-memory", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="小管家"))

        async def _fake_extract_invoke(_db, task_type, variables, **kwargs):
            _ = (_db, kwargs)
            self.assertEqual("proposal_batch_extraction", task_type)
            turn_messages = str(variables.get("turn_messages") or "")
            matched = re.search(r"\[user_message\] user\(([^)]+)\):", turn_messages)
            self.assertIsNotNone(matched)
            user_message_id = matched.group(1)
            return LlmResult(
                raw_text="{}",
                display_text="",
                parsed=ProposalBatchExtractionOutput(
                    memory_items=[
                        ProposalExtractionItemOutput(
                            title="记忆提案：favorite_food",
                            summary="favorite_food：巧克力蛋糕和甜食",
                            confidence=0.91,
                            evidence_message_ids=[user_message_id],
                            payload={"memory_type": "preference", "favorite_food": "巧克力蛋糕和甜食"},
                        )
                    ]
                ),
                provider="mock-provider",
            )

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch(
            "app.modules.conversation.proposal_pipeline.ainvoke_llm",
            side_effect=_fake_extract_invoke,
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual([], final_snapshot["proposal_batches"])

    def test_conversation_duplicate_memory_proposal_is_filtered(self) -> None:
        create_manual_memory_card(
            self.db,
            payload=MemoryCardManualCreate(
                household_id=self.household_id,
                memory_type="preference",
                title="favorite_food",
                summary="巧克力蛋糕和甜食",
                content={"favorite_food": "巧克力蛋糕和甜食"},
                subject_member_id=self.member_id,
                dedupe_key="existing-favorite-food",
                reason="test setup",
            ),
            actor=self.member_actor,
        )
        self.db.commit()

        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-memory-duplicate", "payload": {"text": "你知道我最喜欢吃什么吗"}}],
        )

        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="你之前说过自己喜欢巧克力蛋糕和甜食。", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-memory-dup", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="小管家"))

        async def _fake_extract_invoke(_db, task_type, variables, **kwargs):
            _ = (_db, kwargs, task_type, variables)
            return LlmResult(
                raw_text="{}",
                display_text="",
                parsed=ProposalBatchExtractionOutput(
                    memory_items=[
                        ProposalExtractionItemOutput(
                            title="记忆提案：favorite_food",
                            summary="favorite_food：巧克力蛋糕和甜食",
                            confidence=0.93,
                            evidence_message_ids=[],
                            payload={"memory_type": "preference", "favorite_food": "巧克力蛋糕和甜食"},
                        )
                    ]
                ),
                provider="mock-provider",
            )

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch(
            "app.modules.conversation.proposal_pipeline.ainvoke_llm",
            side_effect=_fake_extract_invoke,
        ):
            asyncio.run(self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket)))

        final_snapshot = websocket.sent_messages[-1]["payload"]["snapshot"]
        self.assertEqual([], final_snapshot["proposal_batches"])

    def test_conversation_stream_does_not_block_http_request(self) -> None:
        from app.main import app
        from app.modules.conversation import service as conversation_service_module
        from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult

        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.conversation_session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "user.message", "session_id": self.conversation_session_id, "request_id": "conversation-request-concurrency", "payload": {"text": "说点什么"}}],
        )

        async def _fake_stream_orchestrated_turn(_db, **kwargs):
            _ = kwargs
            await asyncio.sleep(0.08)
            yield ("chunk", "第一段")
            await asyncio.sleep(0.08)
            yield ("done", ConversationOrchestratorResult(intent=ConversationIntent.FREE_CHAT, text="第一段最终回复", degraded=False, facts=[], suggestions=[], memory_candidate_payloads=[], config_suggestion=None, action_payloads=[], ai_trace_id="trace-concurrency", ai_provider_code="mock-provider", effective_agent_id=None, effective_agent_name="小管家"))

        async def _run_scenario() -> tuple[float, float, int]:
            transport = httpx.ASGITransport(app=app)
            request_finished_at = 0.0
            websocket_finished_at = 0.0

            async def _run_websocket() -> None:
                nonlocal websocket_finished_at
                await self._realtime_endpoint_module.realtime_conversation_websocket(cast(Any, websocket))
                websocket_finished_at = time.perf_counter()

            async def _run_http_request() -> int:
                nonlocal request_finished_at
                await asyncio.sleep(0.02)
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    response = await client.get("/")
                request_finished_at = time.perf_counter()
                return response.status_code

            websocket_task = asyncio.create_task(_run_websocket())
            status_code = await _run_http_request()
            await websocket_task
            return request_finished_at, websocket_finished_at, status_code

        with patch.object(conversation_service_module, "stream_orchestrated_turn", side_effect=_fake_stream_orchestrated_turn), patch.object(
            conversation_service_module,
            "aextract_proposal_batch",
            return_value=ProposalBatchExtractionOutput(),
        ):
            request_finished_at, websocket_finished_at, status_code = asyncio.run(_run_scenario())

        self.assertEqual(200, status_code)
        self.assertLess(request_finished_at, websocket_finished_at)


if __name__ == "__main__":
    unittest.main()
