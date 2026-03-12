import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi import HTTPException, WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
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
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.invoke import LlmResult, LlmStreamEvent
from app.modules.llm_task.output_models import ButlerBootstrapOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.realtime.connection_manager import realtime_connection_manager


class _FakeWebSocket:
    def __init__(self, *, household_id: str, session_id: str, cookie: str | None = None, inbound_messages: list[dict] | None = None):
        self.query_params = QueryParams({"household_id": household_id, "session_id": session_id})
        self.headers = Headers({"cookie": cookie} if cookie else {})
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


class RealtimeWsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_session_local = db_session_module.SessionLocal

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
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

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        self._realtime_endpoint_module.SessionLocal = self._previous_realtime_session_local
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_websocket_connects_and_pushes_ready_snapshot_and_pong(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[{"type": "ping", "session_id": self.session_id, "payload": {"nonce": "abc"}}],
        )

        asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        self.assertTrue(websocket.accepted)
        self.assertEqual(["session.ready", "session.snapshot", "pong"], [item["type"] for item in websocket.sent_messages])
        self.assertEqual("abc", websocket.sent_messages[2]["payload"]["nonce"])
        self.assertEqual(self.session_id, websocket.sent_messages[1]["payload"]["snapshot"]["session_id"])
        self.assertEqual(0, realtime_connection_manager.connection_count(household_id=self.household_id, session_id=self.session_id))

    def test_websocket_returns_business_error_for_unknown_session(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id="missing-session",
            cookie=self.cookie_header,
        )

        asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        self.assertTrue(websocket.accepted)
        self.assertEqual("agent.error", websocket.sent_messages[0]["type"])
        self.assertEqual("session_not_found", websocket.sent_messages[0]["payload"]["error_code"])
        self.assertEqual(1008, websocket.close_code)

    def test_websocket_user_message_emits_full_turn_events_and_persists_request(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[
                {
                    "type": "user.message",
                    "session_id": self.session_id,
                    "request_id": "request-1",
                    "payload": {"text": "我想叫阿福，风格温和直接，性格细心稳重。"},
                }
            ],
        )

        from app.modules.agent import bootstrap_service as bootstrap_service_module

        with patch.object(bootstrap_service_module, "_ensure_bootstrap_allowed", return_value=None), \
                patch.object(
                    bootstrap_service_module,
                    "stream_llm",
                    return_value=iter([
                        LlmStreamEvent("chunk", content="你好，我先记下这个名字。"),
                        LlmStreamEvent(
                            "done",
                            result=LlmResult(
                                raw_text="你好，我先记下这个名字。",
                                display_text="你好，我先记下这个名字。",
                            ),
                        ),
                    ]),
                ), \
                patch.object(
                    bootstrap_service_module,
                    "invoke_llm",
                    return_value=LlmResult(
                        raw_text='{"display_name":"阿福","speaking_style":"温和直接","personality_traits":["细心","稳重"],"is_complete":true}',
                        display_text="",
                        parsed=ButlerBootstrapOutput(
                            display_name="阿福",
                            speaking_style="温和直接",
                            personality_traits=["细心", "稳重"],
                            is_complete=True,
                        ),
                    ),
                ):
            asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        event_types = [item["type"] for item in websocket.sent_messages]
        self.assertEqual(
            ["session.ready", "session.snapshot", "user.message.accepted", "agent.chunk", "agent.state_patch", "agent.done"],
            event_types,
        )
        self.assertEqual("阿福", websocket.sent_messages[4]["payload"]["display_name"])

        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=self.session_id)
        self.assertEqual(1, len(request_rows))
        self.assertEqual("succeeded", request_rows[0].status)

        message_rows = agent_repository.list_bootstrap_messages(self.db, session_id=self.session_id)
        self.assertEqual(["assistant", "user", "assistant"], [item.role for item in message_rows])

    def test_websocket_failed_turn_emits_error_and_marks_request_failed(self) -> None:
        websocket = _FakeWebSocket(
            household_id=self.household_id,
            session_id=self.session_id,
            cookie=self.cookie_header,
            inbound_messages=[
                {
                    "type": "user.message",
                    "session_id": self.session_id,
                    "request_id": "request-failed",
                    "payload": {"text": "再试一次。"},
                }
            ],
        )

        from app.modules.agent import bootstrap_service as bootstrap_service_module

        with patch.object(bootstrap_service_module, "_ensure_bootstrap_allowed", return_value=None), \
                patch.object(
                    bootstrap_service_module,
                    "stream_llm",
                    side_effect=HTTPException(status_code=409, detail="上一轮还没结束，请稍后再试"),
                ):
            asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        event_types = [item["type"] for item in websocket.sent_messages]
        self.assertEqual(["session.ready", "session.snapshot", "user.message.accepted", "agent.error"], event_types)
        self.assertEqual("request_conflict", websocket.sent_messages[-1]["payload"]["error_code"])

        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=self.session_id)
        self.assertEqual(1, len(request_rows))
        self.assertEqual("failed", request_rows[0].status)
        self.assertEqual("request_conflict", request_rows[0].error_code)

    def test_websocket_rejects_missing_auth_cookie(self) -> None:
        websocket = _FakeWebSocket(household_id=self.household_id, session_id=self.session_id)

        asyncio.run(self._realtime_endpoint_module.realtime_agent_bootstrap_websocket(cast(Any, websocket)))

        self.assertFalse(websocket.accepted)
        self.assertEqual(1008, websocket.close_code)


if __name__ == "__main__":
    unittest.main()
