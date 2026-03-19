import unittest
from unittest.mock import patch

import app.db.models  # noqa: F401

from app.api.dependencies import ActorContext
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.orchestrator import run_orchestrated_turn
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import ConversationIntentDetectionOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.memory.schemas import MemoryCardManualCreate
from app.modules.memory.service import create_manual_memory_card


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider") -> None:
        self.text = text
        self.data = data
        self.provider = provider


class ConversationMemoryRecallTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Conversation Recall Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
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

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_injects_grouped_recall_hits_into_free_chat(self, invoke_llm_mock) -> None:
        fact_card = self._create_memory_card(
            memory_type="fact",
            title="Alice 喜欢喝拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
        )
        event_card = self._create_memory_card(
            memory_type="event",
            title="Alice 昨晚加班",
            summary="Alice 昨晚十点后才回家",
            dedupe_key="memory:event:overtime",
            last_observed_at="2026-03-18T22:30:00Z",
        )
        self.db.commit()

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
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.95,
                    reason="普通闲聊问题。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(text="好的，我记得这两件事。"),
        ]

        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="Alice 喜欢喝什么拿铁，昨晚发生了什么？",
            actor=self.actor,
            conversation_history=[],
        )

        free_chat_variables = invoke_llm_mock.call_args_list[1].kwargs["variables"]
        memory_context = free_chat_variables["memory_context"]

        self.assertIn("[stable_facts]", memory_context)
        self.assertIn("Alice 喜欢喝拿铁", memory_context)
        self.assertIn("[recent_events]", memory_context)
        self.assertIn("Alice 昨晚加班", memory_context)
        self.assertEqual(
            {fact_card.id, event_card.id},
            {item["memory_id"] for item in result.memory_trace_items},
        )
        self.assertEqual(
            {"stable_facts", "recent_events"},
            {item["group"] for item in result.memory_trace_items},
        )
        self.assertTrue(all(item["source_id"] for item in result.memory_trace_items))
        self.assertTrue(all(item["rank"] >= 1 for item in result.memory_trace_items))

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn", return_value=None)
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_create_conversation_turn_persists_memory_trace_rows(self, invoke_llm_mock, _proposal_mock) -> None:
        fact_card = self._create_memory_card(
            memory_type="fact",
            title="Alice 喜欢喝拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
        )
        event_card = self._create_memory_card(
            memory_type="event",
            title="Alice 昨晚加班",
            summary="Alice 昨晚十点后才回家",
            dedupe_key="memory:event:overtime",
            last_observed_at="2026-03-18T22:30:00Z",
        )
        self.db.commit()

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
            _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.95,
                    reason="普通闲聊问题。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(text="好的，我记得这两件事。"),
        ]

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="Alice 喜欢喝什么拿铁，昨晚发生了什么？", channel="app"),
            actor=self.actor,
        )
        self.db.commit()

        reads = list(
            conversation_repository.list_memory_reads(
                self.db,
                session_id=session.id,
                request_id=turn.request_id,
            )
        )

        self.assertEqual("completed", turn.outcome)
        self.assertEqual(2, len(reads))
        self.assertEqual(
            {fact_card.id, event_card.id},
            {item.memory_id for item in reads},
        )
        self.assertEqual(
            {"stable_facts", "recent_events"},
            {item.group_name for item in reads},
        )
        self.assertTrue(all(item.rank >= 1 for item in reads))
        self.assertTrue(all(item.source_id for item in reads))

    def _create_memory_card(
        self,
        *,
        memory_type: str,
        title: str,
        summary: str,
        dedupe_key: str,
        last_observed_at: str | None = None,
    ):
        return create_manual_memory_card(
            self.db,
            payload=MemoryCardManualCreate(
                household_id=self.household.id,
                memory_type=memory_type,
                title=title,
                summary=summary,
                content={"source": "test", "title": title},
                status="active",
                visibility="family",
                importance=4,
                confidence=0.92,
                subject_member_id=self.member.id,
                dedupe_key=dedupe_key,
                last_observed_at=last_observed_at,
                reason="测试数据",
            ),
            actor=self.actor,
        )


if __name__ == "__main__":
    unittest.main()
