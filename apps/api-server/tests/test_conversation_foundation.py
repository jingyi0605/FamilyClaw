import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMemoryCandidate, ConversationMessage
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import (
    confirm_memory_candidate,
    create_conversation_session,
    create_conversation_turn,
    dismiss_memory_candidate,
    get_conversation_session_detail,
    list_conversation_sessions,
    stream_conversation_turn,
)
from app.modules.family_qa.schemas import FamilyQaQueryResponse
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import MemoryExtractionOutput
from app.modules.memory import repository as memory_repository
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Chat Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="笨笨",
                agent_type="butler",
                self_identity="我是家庭主管家",
                role_summary="负责家庭问答",
                personality_traits=["细心", "稳重"],
                service_focus=["家庭问答", "提醒"],
                default_entry=True,
            ),
        )
        self.db.commit()

        self.actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id=self.member.id,
            account_id="account-1",
            account_type="household",
            account_status="active",
            username="owner",
            household_id=self.household.id,
            member_id=self.member.id,
            member_role="admin",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_conversation_storage_supports_session_message_and_candidate(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.flush()

        user_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-1",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="user",
            message_type="text",
            content="你好",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json=dump_json([]),
            suggestions_json=dump_json([]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, user_message)

        assistant_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-1",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="assistant",
            message_type="text",
            content="你好，我在。",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code="test-provider",
            ai_trace_id="trace-1",
            degraded=False,
            error_code=None,
            facts_json=dump_json([{"type": "active_member", "label": "Owner"}]),
            suggestions_json=dump_json(["现在家里什么状态？"]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, assistant_message)

        candidate = ConversationMemoryCandidate(
            id=new_uuid(),
            session_id=session.id,
            source_message_id=assistant_message.id,
            requester_member_id=self.member.id,
            status="pending_review",
            memory_type="fact",
            title="用户向管家打招呼",
            summary="用户与管家完成了首次问候。",
            content_json=dump_json({"source": "conversation", "message_id": assistant_message.id}),
            confidence=0.82,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_memory_candidate(self.db, candidate)
        self.db.commit()

        detail = get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor)

        self.assertEqual(2, len(detail.messages))
        self.assertEqual(["user", "assistant"], [item.role for item in detail.messages])
        self.assertEqual("你好，我在。", detail.messages[1].content)
        self.assertEqual(1, len(detail.memory_candidates))
        self.assertEqual("pending_review", detail.memory_candidates[0].status)
        self.assertEqual("笨笨", detail.active_agent_name)

    def test_list_sessions_only_returns_current_member_sessions(self) -> None:
        own_session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
                title="我的会话",
            ),
            actor=self.actor,
        )
        self.db.flush()

        another_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Another", role="adult"),
        )
        self.db.flush()
        another_actor = ActorContext(
            role="adult",
            actor_type="member",
            actor_id=another_member.id,
            account_id="account-2",
            account_type="household",
            account_status="active",
            username="another",
            household_id=self.household.id,
            member_id=another_member.id,
            member_role="adult",
            is_authenticated=True,
        )
        create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
                title="别人的会话",
            ),
            actor=another_actor,
        )
        self.db.commit()

        result = list_conversation_sessions(
            self.db,
            household_id=self.household.id,
            requester_member_id=None,
            actor=self.actor,
        )

        self.assertEqual(1, len(result.items))
        self.assertEqual(own_session.id, result.items[0].id)
        self.assertEqual("我的会话", result.items[0].title)

    @patch("app.modules.conversation.service.query_family_qa")
    def test_create_conversation_turn_persists_completed_messages(self, query_family_qa_mock) -> None:
        query_family_qa_mock.return_value = FamilyQaQueryResponse(
            answer_type="general",
            answer="你好，我是笨笨。",
            confidence=0.92,
            facts=[],
            degraded=False,
            suggestions=["继续问一个问题"],
            effective_agent_id=self.agent.id,
            effective_agent_type="butler",
            effective_agent_name="笨笨",
            ai_trace_id="trace-sync",
            ai_provider_code="mock-provider",
            ai_degraded=False,
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        result = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="你好"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertIsNone(result.error_message)
        self.assertEqual(2, len(result.session.messages))
        self.assertEqual("user", result.session.messages[0].role)
        self.assertEqual("assistant", result.session.messages[1].role)
        self.assertEqual("completed", result.session.messages[1].status)
        self.assertEqual("你好，我是笨笨。", result.session.messages[1].content)

    @patch("app.modules.conversation.service.query_family_qa")
    def test_create_conversation_turn_persists_failed_assistant_message(self, query_family_qa_mock) -> None:
        from fastapi import HTTPException

        query_family_qa_mock.side_effect = HTTPException(status_code=502, detail="provider failed")
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        result = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="你好"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("failed", result.outcome)
        self.assertEqual("provider failed", result.error_message)
        self.assertEqual(2, len(result.session.messages))
        self.assertEqual("failed", result.session.messages[1].status)
        self.assertEqual("error", result.session.messages[1].message_type)
        self.assertEqual("provider failed", result.session.messages[1].content)

    @patch("app.modules.conversation.service.query_family_qa")
    def test_stream_conversation_turn_emits_events_and_finishes_session(self, query_family_qa_mock) -> None:
        query_family_qa_mock.return_value = FamilyQaQueryResponse(
            answer_type="general",
            answer="你好，我是笨笨。现在一切正常。",
            confidence=0.9,
            facts=[],
            degraded=False,
            suggestions=["现在家里什么状态？"],
            effective_agent_id=self.agent.id,
            effective_agent_type="butler",
            effective_agent_name="笨笨",
            ai_trace_id="trace-stream",
            ai_provider_code="mock-provider",
            ai_degraded=False,
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.commit()

        raw_events = list(
            stream_conversation_turn(
                self.db,
                session_id=session.id,
                payload=ConversationTurnCreate(message="你好"),
                actor=self.actor,
            )
        )
        event_payloads = [
            json.loads(item.removeprefix("data: ").strip())
            for item in raw_events
            if item.startswith("data: ")
        ]
        event_types = [item["type"] for item in event_payloads]

        self.assertIn("user.message.accepted", event_types)
        self.assertIn("assistant.chunk", event_types)
        self.assertIn("assistant.done", event_types)

        final_event = next(item for item in event_payloads if item["type"] == "assistant.done")
        final_session = final_event["session"]
        self.assertEqual(2, len(final_session["messages"]))
        self.assertEqual("completed", final_session["messages"][1]["status"])
        self.assertEqual("你好，我是笨笨。现在一切正常。", final_session["messages"][1]["content"])

    @patch("app.modules.conversation.service.query_family_qa")
    def test_create_conversation_turn_passes_previous_history_into_query_context(self, query_family_qa_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.flush()

        previous_user = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="previous-request",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="user",
            message_type="text",
            content="上一次的问题",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json=dump_json([]),
            suggestions_json=dump_json([]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, previous_user)
        previous_assistant = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="previous-request",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="assistant",
            message_type="text",
            content="上一次的回答",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code="mock-provider",
            ai_trace_id="trace-previous",
            degraded=False,
            error_code=None,
            facts_json=dump_json([]),
            suggestions_json=dump_json([]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, previous_assistant)
        self.db.commit()

        def _fake_query(_db, payload, _actor):
            history = payload.context.get("conversation_history")
            self.assertEqual(
                [
                    {"role": "user", "content": "上一次的问题"},
                    {"role": "assistant", "content": "上一次的回答"},
                ],
                history,
            )
            return FamilyQaQueryResponse(
                answer_type="general",
                answer="这是新一轮回答",
                confidence=0.88,
                facts=[],
                degraded=False,
                suggestions=[],
                effective_agent_id=self.agent.id,
                effective_agent_type="butler",
                effective_agent_name="笨笨",
                ai_trace_id="trace-history",
                ai_provider_code="mock-provider",
                ai_degraded=False,
            )

        query_family_qa_mock.side_effect = _fake_query

        result = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="新的问题"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual("这是新一轮回答", result.session.messages[-1].content)

    @patch("app.modules.conversation.service.invoke_llm")
    @patch("app.modules.conversation.service.query_family_qa")
    def test_create_conversation_turn_generates_memory_candidates(self, query_family_qa_mock, invoke_llm_mock) -> None:
        query_family_qa_mock.return_value = FamilyQaQueryResponse(
            answer_type="general",
            answer="记下来了，你不吃香菜。",
            confidence=0.95,
            facts=[],
            degraded=False,
            suggestions=[],
            effective_agent_id=self.agent.id,
            effective_agent_type="butler",
            effective_agent_name="笨笨",
            ai_trace_id="trace-memory",
            ai_provider_code="mock-provider",
            ai_degraded=False,
        )

        class _FakeLlmResult:
            def __init__(self):
                self.data = MemoryExtractionOutput(
                    memories=[
                        {
                            "type": "preference",
                            "title": "不吃香菜",
                            "summary": "用户明确表示自己不吃香菜。",
                            "confidence": 0.93,
                        }
                    ]
                )

        invoke_llm_mock.return_value = _FakeLlmResult()

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        result = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="记住，我不吃香菜"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual(1, len(result.session.memory_candidates))
        self.assertEqual("preference", result.session.memory_candidates[0].memory_type)
        self.assertEqual("不吃香菜", result.session.memory_candidates[0].title)

    def test_confirm_memory_candidate_creates_memory_card(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.flush()

        assistant_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-memory",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="assistant",
            message_type="text",
            content="我记住了，你不吃香菜。",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code="mock-provider",
            ai_trace_id="trace-memory",
            degraded=False,
            error_code=None,
            facts_json=dump_json([]),
            suggestions_json=dump_json([]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, assistant_message)
        candidate = ConversationMemoryCandidate(
            id=new_uuid(),
            session_id=session.id,
            source_message_id=assistant_message.id,
            requester_member_id=self.member.id,
            status="pending_review",
            memory_type="preference",
            title="不吃香菜",
            summary="用户明确表示自己不吃香菜。",
            content_json=dump_json({"source": "conversation", "tag": "diet"}),
            confidence=0.91,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_memory_candidate(self.db, candidate)
        self.db.commit()

        result = confirm_memory_candidate(
            self.db,
            candidate_id=candidate.id,
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("confirmed", result.candidate.status)
        self.assertIsNotNone(result.memory_card_id)
        created_memory = memory_repository.get_memory_card(self.db, result.memory_card_id)
        self.assertIsNotNone(created_memory)
        assert created_memory is not None
        self.assertEqual("preference", created_memory.memory_type)
        self.assertEqual("不吃香菜", created_memory.title)

    def test_dismiss_memory_candidate_marks_candidate_dismissed(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.flush()

        candidate = ConversationMemoryCandidate(
            id=new_uuid(),
            session_id=session.id,
            source_message_id=None,
            requester_member_id=self.member.id,
            status="pending_review",
            memory_type="fact",
            title="待忽略候选",
            summary="这条候选应该被忽略。",
            content_json=dump_json({"source": "conversation"}),
            confidence=0.51,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_memory_candidate(self.db, candidate)
        self.db.commit()

        result = dismiss_memory_candidate(
            self.db,
            candidate_id=candidate.id,
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("dismissed", result.candidate.status)
        self.assertIsNone(result.memory_card_id)


if __name__ == "__main__":
    unittest.main()
