import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate, AgentRuntimePolicyUpsert
from app.modules.agent.service import create_agent, upsert_agent_runtime_policy
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMemoryCandidate, ConversationMessage
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentLabel,
    ConversationOrchestratorResult,
    _build_free_chat_variables,
    detect_conversation_intent,
    run_orchestrated_turn,
)
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import (
    confirm_conversation_action,
    confirm_memory_candidate,
    create_conversation_session,
    create_conversation_turn,
    dismiss_memory_candidate,
    get_conversation_session_detail,
    list_conversation_debug_logs,
    list_conversation_sessions,
    undo_conversation_action,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import (
    ConversationIntentDetectionOutput,
    MemoryExtractionOutput,
    ReminderExtractionOutput,
)
from app.modules.llm_task.parser import parse_to_model
from app.modules.ai_gateway.provider_runtime import build_template_fallback_output
from app.modules.memory import repository as memory_repository
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider") -> None:
        self.text = text
        self.data = data
        self.provider = provider


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

    def test_list_conversation_debug_logs_reflects_env_switch(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        previous = settings.conversation_debug_log_enabled
        try:
            settings.conversation_debug_log_enabled = False
            debug_logs = list_conversation_debug_logs(self.db, session_id=session.id, actor=self.actor)
            self.assertFalse(debug_logs.debug_enabled)
            self.assertEqual(0, len(debug_logs.items))

            settings.conversation_debug_log_enabled = True
            debug_logs = list_conversation_debug_logs(self.db, session_id=session.id, actor=self.actor)
            self.assertTrue(debug_logs.debug_enabled)
        finally:
            settings.conversation_debug_log_enabled = previous

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_writes_debug_logs_when_enabled(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="你好，我在。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-debug",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        previous = settings.conversation_debug_log_enabled
        try:
            settings.conversation_debug_log_enabled = True
            result = create_conversation_turn(
                self.db,
                session_id=session.id,
                payload=ConversationTurnCreate(message="你好"),
                actor=self.actor,
            )
            self.db.commit()

            self.assertEqual("completed", result.outcome)
            debug_logs = list_conversation_debug_logs(
                self.db,
                session_id=session.id,
                actor=self.actor,
                request_id=result.request_id,
            )
            stages = [item.stage for item in debug_logs.items]
            self.assertTrue(debug_logs.debug_enabled)
            self.assertIn("turn.received", stages)
            self.assertIn("orchestrator.completed", stages)
            self.assertIn("assistant.completed", stages)
            self.assertIn("turn.completed", stages)
        finally:
            settings.conversation_debug_log_enabled = previous

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

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_persists_completed_messages(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.STRUCTURED_QA,
            text="你好，我是笨笨。",
            degraded=False,
            facts=[],
            suggestions=["继续问一个问题"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-sync",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
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

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_persists_failed_assistant_message(self, run_orchestrated_turn_mock) -> None:
        from fastapi import HTTPException

        run_orchestrated_turn_mock.side_effect = HTTPException(status_code=502, detail="provider failed")
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

    @patch("app.modules.conversation.service._generate_memory_candidates_for_turn")
    @patch("app.modules.conversation.service.run_orchestrated_turn")
    def test_create_conversation_turn_passes_previous_history_into_query_context(self, run_orchestrated_turn_mock, generate_memory_candidates_mock) -> None:
        _ = generate_memory_candidates_mock
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

        def _fake_run(_db, session, message, actor, conversation_history, request_context=None):
            _ = session, message, actor
            self.assertEqual(
                [
                    {"role": "user", "content": "上一次的问题"},
                    {"role": "assistant", "content": "上一次的回答"},
                ],
                conversation_history,
            )
            self.assertTrue(isinstance(request_context, dict))
            assert request_context is not None
            self.assertEqual(session.id, request_context.get("session_id"))
            self.assertEqual("conversation_turn", request_context.get("channel"))
            self.assertTrue(isinstance(request_context.get("request_id"), str) and request_context.get("request_id"))
            return ConversationOrchestratorResult(
                intent=ConversationIntent.STRUCTURED_QA,
                text="这是新一轮回答",
                degraded=False,
                facts=[],
                suggestions=[],
                memory_candidate_payloads=[],
                config_suggestion=None,
                action_payloads=[],
                ai_trace_id="trace-history",
                ai_provider_code="mock-provider",
                effective_agent_id=self.agent.id,
                effective_agent_name="笨笨",
            )

        run_orchestrated_turn_mock.side_effect = _fake_run

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
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_generates_memory_candidates(self, run_orchestrated_turn_mock, invoke_llm_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="记下来了，你不吃香菜。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-memory",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
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
        self.assertEqual(1, len(result.session.action_records))
        self.assertEqual("memory.write", result.session.action_records[0].action_name)
        self.assertEqual("pending_confirmation", result.session.action_records[0].status)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_detect_conversation_intent_routes_story_to_free_chat(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.return_value = _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="free_chat",
                secondary_intents=[],
                confidence=0.93,
                reason="这是普通创作闲聊。",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="讲500字的科幻故事")
        self.assertEqual(ConversationIntentLabel.FREE_CHAT, intent.primary_intent)
        self.assertEqual(ConversationIntent.FREE_CHAT, intent.route_intent)

    def test_parse_intent_detection_output_from_dirty_text(self) -> None:
        parsed = parse_to_model(
            """这是补充说明，不该出现。
<output>
{"primary_intent":"free_chat","secondary_intents":[],"confidence":0.91,"reason":"普通问候","candidate_actions":[]}
</output>""",
            ConversationIntentDetectionOutput,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual("free_chat", parsed.primary_intent)

    def test_parse_intent_detection_output_tolerates_string_candidate_actions(self) -> None:
        parsed = parse_to_model(
            """<output>
{"primary_intent":"free_chat","secondary_intents":[],"confidence":0.6,"reason":"普通寒暄","candidate_actions":["继续进行一般性对话","提醒我明天开会"]}
</output>""",
            ConversationIntentDetectionOutput,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual("free_chat", parsed.primary_intent)
        self.assertEqual(1, len(parsed.candidate_actions))
        self.assertEqual("reminder_create", parsed.candidate_actions[0].action_type)

    def test_template_fallback_for_intent_detection_returns_structured_json(self) -> None:
        output = build_template_fallback_output(
            capability="qa_generation",
            payload={"task_type": "conversation_intent_detection"},
        )
        parsed = parse_to_model(str(output.get("text") or ""), ConversationIntentDetectionOutput)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual("free_chat", parsed.primary_intent)

    def test_template_fallback_for_free_chat_returns_human_greeting(self) -> None:
        output = build_template_fallback_output(
            capability="qa_generation",
            payload={"task_type": "free_chat", "user_message": "你好"},
        )
        self.assertIn("你好，我在", str(output.get("text") or ""))

    @patch("app.modules.conversation.orchestrator.get_conversation_debug_logger")
    @patch("app.modules.conversation.orchestrator.build_memory_context_bundle")
    @patch("app.modules.conversation.orchestrator.get_context_overview")
    @patch("app.modules.conversation.orchestrator.build_agent_runtime_context")
    def test_build_free_chat_variables_logs_memory_context_details(
        self,
        build_agent_runtime_context_mock,
        get_context_overview_mock,
        build_memory_context_bundle_mock,
        get_conversation_debug_logger_mock,
    ) -> None:
        build_agent_runtime_context_mock.return_value = {
            "agent": {"name": "笨笨"},
            "identity": {"role_summary": "AI管家", "speaking_style": "自然亲切"},
        }
        get_context_overview_mock.return_value = SimpleNamespace(
            active_member=SimpleNamespace(name="Owner"),
            home_mode="home",
            home_assistant_status="online",
        )
        build_memory_context_bundle_mock.return_value = SimpleNamespace(
            capability="conversation_free_chat",
            hot_summary=SimpleNamespace(
                total_visible_cards=2,
                top_memories=[
                    SimpleNamespace(memory_id="memory-1", title="给管家改名", memory_type="preference", summary="用户想把AI管家改名为暖暖。", updated_at="2026-03-14T00:00:00Z"),
                ],
                preference_highlights=["用户想把AI管家改名为暖暖。"],
                recent_event_highlights=[],
            ),
            query_result=SimpleNamespace(
                total=1,
                items=[
                    SimpleNamespace(
                        card=SimpleNamespace(id="memory-1", title="给管家改名", memory_type="preference", summary="用户想把AI管家改名为暖暖。"),
                        score=48,
                        matched_terms=["暖暖"],
                    )
                ],
            ),
        )
        logger_mock = Mock()
        get_conversation_debug_logger_mock.return_value = logger_mock

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        variables = _build_free_chat_variables(
            self.db,
            session=session,
            actor=self.actor,
            user_message="你叫什么来着",
            request_context={"request_id": "req-1", "session_id": session.id},
            log_memory_context=True,
        )
        self.assertIn("暖暖", variables["memory_context"])
        logger_mock.info.assert_called_once()
        logged_text = logger_mock.info.call_args[0][0]
        self.assertIn("memory_context.read", logged_text)
        self.assertIn("memory-1", logged_text)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_detect_conversation_intent_routes_family_status_to_structured_qa(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.return_value = _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="structured_qa",
                secondary_intents=["free_chat"],
                confidence=0.96,
                reason="用户在问家庭状态。",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="现在家里是什么状态？")
        self.assertEqual(ConversationIntentLabel.STRUCTURED_QA, intent.primary_intent)
        self.assertEqual(ConversationIntent.STRUCTURED_QA, intent.route_intent)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_detect_conversation_intent_routes_config_request_to_config_extraction(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.return_value = _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="config_change",
                secondary_intents=[],
                confidence=0.97,
                reason="用户明确想改助手名字和说话风格。",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="以后你就叫阿福，说话风格温柔一点")
        self.assertEqual(ConversationIntentLabel.CONFIG_CHANGE, intent.primary_intent)
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, intent.route_intent)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_detect_conversation_intent_routes_agent_name_query_to_free_chat(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.return_value = _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="free_chat",
                secondary_intents=["config_change"],
                confidence=0.9,
                reason="这是在问助手名字，不是在改配置。",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="你叫什么")
        self.assertEqual(ConversationIntentLabel.FREE_CHAT, intent.primary_intent)
        self.assertEqual(ConversationIntent.FREE_CHAT, intent.route_intent)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_detect_conversation_intent_low_confidence_falls_back_to_free_chat(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.return_value = _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="config_change",
                secondary_intents=["free_chat"],
                confidence=0.42,
                reason="可能像是在改配置，但不够明确。",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="你觉得阿福这个名字怎么样")
        self.assertEqual(ConversationIntentLabel.CONFIG_CHANGE, intent.primary_intent)
        self.assertEqual(ConversationIntent.FREE_CHAT, intent.route_intent)

    def test_detect_conversation_intent_agent_config_mode_is_hard_guardrail(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
                session_mode="agent_config",
            ),
            actor=self.actor,
        )
        intent = detect_conversation_intent(self.db, session=session, message="你叫什么")
        self.assertEqual(ConversationIntentLabel.CONFIG_CHANGE, intent.primary_intent)
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, intent.route_intent)
        self.assertEqual("session_mode.agent_config", intent.guardrail_rule)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_routes_reminder_intent_to_extraction(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.side_effect = [
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="reminder_create",
                    secondary_intents=[],
                    confidence=0.95,
                    reason="用户明确要求创建提醒。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(
                data=ReminderExtractionOutput(
                    should_create=True,
                    title="带钥匙",
                    description="出门前检查钥匙",
                    trigger_at="2026-03-14T08:00:00+08:00",
                )
            ),
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="明天早上八点提醒我带钥匙",
            actor=self.actor,
            conversation_history=[],
        )
        self.assertEqual(ConversationIntent.REMINDER_EXTRACTION, result.intent)
        self.assertEqual(ConversationIntentLabel.REMINDER_CREATE, result.intent_detection.primary_intent)
        self.assertEqual(1, len(result.action_payloads))
        self.assertEqual("reminder_create", result.action_payloads[0]["action_type"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_uses_natural_reply_for_config_change(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.side_effect = [
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="config_change",
                    secondary_intents=[],
                    confidence=0.95,
                    reason="用户明确想给助手改名。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(
                data=type(
                    "_ConfigDraft",
                    (),
                    {
                        "display_name": "阿福",
                        "speaking_style": None,
                        "personality_traits": [],
                    },
                )()
            ),
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="以后你就叫阿福",
            actor=self.actor,
            conversation_history=[],
        )
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("好，那我以后就叫阿福。你还想顺手调整一下我说话的风格，或者补几个性格标签吗？", result.text)
        self.assertEqual("阿福", result.config_suggestion["display_name"])
        self.assertEqual([], invoke_llm_mock.call_args_list[1].kwargs["conversation_history"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_passes_recent_history_to_config_extraction(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.side_effect = [
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="config_change",
                    secondary_intents=[],
                    confidence=0.95,
                    reason="用户在继续补充助手名字。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(
                data=type(
                    "_ConfigDraft",
                    (),
                    {
                        "display_name": "暖暖",
                        "speaking_style": None,
                        "personality_traits": [],
                    },
                )()
            ),
        ]
        history = [
            {"role": "user", "content": "给你改个名字好不好"},
            {"role": "assistant", "content": "当然可以，你想给我起什么新名字？"},
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="叫暖暖吧",
            actor=self.actor,
            conversation_history=history,
        )
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("暖暖", result.config_suggestion["display_name"])
        self.assertEqual("好，那我以后就叫暖暖。你还想顺手调整一下我说话的风格，或者补几个性格标签吗？", result.text)
        self.assertEqual(history, invoke_llm_mock.call_args_list[1].kwargs["conversation_history"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_does_not_extract_current_name_as_new_config(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.side_effect = [
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="config_change",
                    secondary_intents=[],
                    confidence=0.92,
                    reason="用户想讨论改名。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(
                data=type(
                    "_ConfigDraft",
                    (),
                    {
                        "display_name": self.agent.display_name,
                        "speaking_style": "幽默风趣",
                        "personality_traits": ["细心", "乐于助人"],
                    },
                )()
            ),
            _FakeLlmResult(text="当然可以，你想给我起什么新名字？也可以顺手告诉我想换成什么说话风格。"),
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="我给你改个名怎么样",
            actor=self.actor,
            conversation_history=[
                {"role": "assistant", "content": f"哈哈，我是{self.agent.display_name}，你的家庭AI管家哦！"}
            ],
        )
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("当然可以，你想给我起什么新名字？也可以顺手告诉我想换成什么说话风格。", result.text)
        self.assertIsNone(result.config_suggestion)
        self.assertEqual([], result.facts)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_low_confidence_returns_free_chat(self, invoke_llm_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        invoke_llm_mock.side_effect = [
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="config_change",
                    secondary_intents=["free_chat"],
                    confidence=0.35,
                    reason="只是随口聊名字，不够像配置修改。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(text="我现在叫笨笨，你想给我起新名字也可以。"),
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="你叫什么",
            actor=self.actor,
            conversation_history=[],
        )
        self.assertEqual(ConversationIntent.FREE_CHAT, result.intent)
        self.assertIsNone(result.config_suggestion)
        self.assertEqual("我现在叫笨笨，你想给我起新名字也可以。", result.text)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_routes_config_intent_without_family_qa(self, run_orchestrated_turn_mock, invoke_llm_mock) -> None:
        _ = invoke_llm_mock
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.CONFIG_EXTRACTION,
            text="我已经把这轮表达整理成 Agent 配置建议：\n- 名称建议：阿福",
            degraded=False,
            facts=[{"type": "config_suggestion", "label": "Agent 配置建议", "source": "conversation_orchestrator", "extra": {"display_name": "阿福"}}],
            suggestions=["去 AI 配置"],
            memory_candidate_payloads=[],
            config_suggestion={"display_name": "阿福"},
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
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
            payload=ConversationTurnCreate(message="以后你就叫阿福"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertIn("Agent 配置建议", result.session.messages[1].content)

    @patch("app.modules.conversation.service.invoke_llm")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_memory_intent_handler_persists_candidates_directly(self, run_orchestrated_turn_mock, invoke_llm_mock) -> None:
        _ = invoke_llm_mock
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="我已经从这轮内容里整理出记忆候选，右侧可以直接确认写入。",
            degraded=False,
            facts=[],
            suggestions=["确认写入记忆"],
            memory_candidate_payloads=[
                {
                    "memory_type": "preference",
                    "title": "不吃香菜",
                    "summary": "用户明确表示自己不吃香菜。",
                    "content": {"source": "conversation"},
                    "confidence": 0.92,
                }
            ],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
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
            payload=ConversationTurnCreate(message="记住，我不吃香菜"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual(1, len(result.session.memory_candidates))
        self.assertEqual("preference", result.session.memory_candidates[0].memory_type)
        self.assertEqual(1, len(result.session.action_records))
        self.assertEqual("memory.write", result.session.action_records[0].action_name)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_notify_config_action_executes_and_can_undo(self, run_orchestrated_turn_mock) -> None:
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                autonomous_action_policy={"memory": "ask", "config": "notify", "action": "ask"},
            ),
        )
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.CONFIG_EXTRACTION,
            text="我已经整理好了配置建议。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion={"display_name": "阿福", "speaking_style": "温和直接", "personality_traits": ["稳重"]},
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="以后你就叫阿福，说话温和直接一点"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual(1, len(turn.session.action_records))
        action = turn.session.action_records[0]
        self.assertEqual("config.apply", action.action_name)
        self.assertEqual("completed", action.status)
        self.assertEqual("阿福", get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor).active_agent_name)

        undo_result = undo_conversation_action(self.db, action_id=action.id, actor=self.actor)
        self.db.commit()
        self.assertEqual("undone", undo_result.action.status)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_confirm_pending_memory_action_creates_memory(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="我已经整理出了记忆候选。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[
                {
                    "memory_type": "preference",
                    "title": "不吃香菜",
                    "summary": "用户明确表示自己不吃香菜。",
                    "content": {"source": "conversation"},
                    "confidence": 0.92,
                }
            ],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="笨笨",
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="记住，我不吃香菜"),
            actor=self.actor,
        )
        self.db.commit()
        action = turn.session.action_records[0]

        execution = confirm_conversation_action(self.db, action_id=action.id, actor=self.actor)
        self.db.commit()

        self.assertEqual("completed", execution.action.status)
        self.assertEqual("memory.write", execution.action.action_name)
        memory_card_id = execution.action.result_payload.get("memory_card_id")
        self.assertTrue(isinstance(memory_card_id, str) and memory_card_id)

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
