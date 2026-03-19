import unittest
from unittest.mock import patch

import app.db.models  # noqa: F401
from sqlalchemy import text

from app.api.dependencies import ActorContext
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import ConversationIntentDetectionOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider") -> None:
        self.text = text
        self.data = data
        self.provider = provider


class ConversationSessionSummaryPhase2Tests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Session Summary Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Alice", role="admin"),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="管家",
                agent_type="butler",
                self_identity="我是家庭管家。",
                role_summary="负责家庭问答",
                personality_traits=["细心"],
                service_focus=["家庭问答"],
                default_entry=True,
            ),
        )
        self.db.commit()

        self.actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id=self.member.id,
            account_id="account-admin",
            account_type="household",
            account_status="active",
            username="alice",
            household_id=self.household.id,
            member_id=self.member.id,
            member_role="admin",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_migration_creates_session_summary_table_and_relaxes_trace_fk(self) -> None:
        column_names = {
            str(row.column_name)
            for row in self.db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'conversation_session_summaries'
                    """
                )
            ).all()
        }
        self.assertEqual(
            {
                "id",
                "session_id",
                "household_id",
                "requester_member_id",
                "summary",
                "open_topics_json",
                "recent_confirmations_json",
                "covered_message_seq",
                "status",
                "generated_at",
                "updated_at",
            },
            column_names,
        )

        memory_id_fk_count = int(
            self.db.execute(
                text(
                    """
                    SELECT count(*)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = 'conversation_memory_reads'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = 'memory_id'
                    """
                )
            ).scalar()
            or 0
        )
        self.assertEqual(0, memory_id_fk_count)

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn", return_value=None)
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_create_conversation_turn_refreshes_session_summary_after_threshold(self, invoke_llm_mock, _proposal_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                requester_member_id=self.member.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        invoke_llm_mock.side_effect = [
            self._intent_result(),
            _FakeLlmResult(text="你更喜欢热拿铁。"),
            self._intent_result(),
            _FakeLlmResult(text="昨晚你十点后才回家。"),
        ]

        create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="帮我记一下我早餐更喜欢热拿铁", channel="app"),
            actor=self.actor,
        )
        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="顺便总结一下昨晚发生了什么", channel="app"),
            actor=self.actor,
        )
        self.db.commit()

        summary = conversation_repository.get_session_summary(self.db, session_id=session.id)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual("fresh", summary.status)
        self.assertEqual(4, summary.covered_message_seq)
        self.assertIn("拿铁", summary.summary)
        self.assertIn("昨晚", summary.summary)
        self.assertEqual("completed", turn.outcome)

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn", return_value=None)
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_follow_up_turn_injects_session_summary_and_persists_l1_trace(self, invoke_llm_mock, _proposal_mock) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                requester_member_id=self.member.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        invoke_llm_mock.side_effect = [
            self._intent_result(),
            _FakeLlmResult(text="你早餐更喜欢热拿铁。"),
            self._intent_result(),
            _FakeLlmResult(text="昨晚你十点后才回家。"),
            self._intent_result(),
            _FakeLlmResult(text="我记得，我们刚刚聊过拿铁和昨晚加班。"),
        ]

        create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="帮我记一下我早餐更喜欢热拿铁", channel="app"),
            actor=self.actor,
        )
        create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="顺便总结一下昨晚发生了什么", channel="app"),
            actor=self.actor,
        )
        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="继续刚才的话题，我们已经确认了什么？", channel="app"),
            actor=self.actor,
        )

        free_chat_variables = invoke_llm_mock.call_args_list[-1].kwargs["variables"]
        memory_context = free_chat_variables["memory_context"]
        self.assertIn("[session_summary]", memory_context)
        self.assertIn("拿铁", memory_context)
        self.db.commit()

        reads = list(
            conversation_repository.list_memory_reads(
                self.db,
                session_id=session.id,
                request_id=turn.request_id,
            )
        )
        self.assertTrue(any(item.group_name == "session_summary" and item.layer == "L1" for item in reads))
        self.assertTrue(any(item.source_kind == "conversation_session_summary" for item in reads))

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn", return_value=None)
    @patch("app.modules.conversation.service.maybe_refresh_session_summary", side_effect=RuntimeError("summary boom"))
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_session_summary_failure_does_not_break_turn(
        self,
        invoke_llm_mock,
        _summary_mock,
        _proposal_mock,
    ) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                requester_member_id=self.member.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        invoke_llm_mock.side_effect = [
            self._intent_result(),
            _FakeLlmResult(text="没问题，我继续回答。"),
            self._intent_result(),
            _FakeLlmResult(text="晚饭可以做得简单一点。"),
        ]

        create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="今天继续聊一下晚饭安排", channel="app"),
            actor=self.actor,
        )
        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="再补一句，今晚尽量清淡一点", channel="app"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", turn.outcome)
        debug_logs = conversation_repository.list_debug_logs(self.db, session_id=session.id, request_id=turn.request_id)
        self.assertTrue(any(item.stage == "session_summary.failed" for item in debug_logs))

    def _intent_result(self) -> _FakeLlmResult:
        return _FakeLlmResult(
            data=ConversationIntentDetectionOutput(
                primary_intent="free_chat",
                secondary_intents=[],
                confidence=0.95,
                reason="普通闲聊问题。",
                candidate_actions=[],
            )
        )


if __name__ == "__main__":
    unittest.main()
