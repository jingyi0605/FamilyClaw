import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMessage, ConversationSession
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationLaneSelection,
    ConversationOrchestratorResult,
)
from app.modules.conversation.proposal_analyzers import (
    ConfigProposalAnalyzer,
    MemoryProposalAnalyzer,
    ProposalAnalyzerFailure,
    ProposalAnalyzerRegistry,
    ProposalDraft,
)
from app.modules.conversation.proposal_pipeline import ProposalPipeline, ProposalPipelineResult, TurnProposalContext, build_turn_proposal_context
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput, ProposalExtractionItemOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class _FailingAnalyzer:
    name = "failing"
    proposal_kind = "broken"
    default_policy_category = "ask"

    def supports(self, turn_context: TurnProposalContext) -> bool:
        return True

    def analyze(self, turn_context: TurnProposalContext, extraction_output: ProposalBatchExtractionOutput) -> list[ProposalDraft]:
        raise RuntimeError("boom")


class _ReminderLikeAnalyzer:
    name = "reminder"
    proposal_kind = "reminder_create"
    default_policy_category = "ask"

    def supports(self, turn_context: TurnProposalContext) -> bool:
        return True

    def analyze(self, turn_context: TurnProposalContext, extraction_output: ProposalBatchExtractionOutput) -> list[ProposalDraft]:
        return [
            ProposalDraft(
                proposal_kind="reminder_create",
                policy_category="ask",
                title="提醒草稿",
                summary="测试提醒",
                evidence_message_ids=[turn_context.turn_messages[0].message_id],
                evidence_roles=["user"],
                dedupe_key="reminder:test",
                confidence=0.8,
                payload={"title": "提醒草稿", "action_type": "reminder_create"},
            )
        ]


class ConversationProposalPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_shadow = settings.conversation_proposal_shadow_enabled
        self._previous_write = settings.conversation_proposal_write_enabled

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
            HouseholdCreate(name="Proposal Flow Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
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
                self_identity="我是家庭管家",
                role_summary="负责家庭问答",
                personality_traits=["细心"],
                service_focus=["聊天"],
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
        settings.conversation_proposal_shadow_enabled = self._previous_shadow
        settings.conversation_proposal_write_enabled = self._previous_write
        self._tempdir.cleanup()

    def test_registry_isolates_single_analyzer_failure(self) -> None:
        context = self._build_context(user_text="明天提醒我开会", assistant_text="好的")
        registry = ProposalAnalyzerRegistry(analyzers=[_FailingAnalyzer(), _ReminderLikeAnalyzer()])

        drafts, failures = registry.run(context, ProposalBatchExtractionOutput())

        self.assertEqual(1, len(drafts))
        self.assertEqual("reminder_create", drafts[0].proposal_kind)
        self.assertEqual(1, len(failures))
        self.assertEqual("failing", failures[0].analyzer_name)

    def test_assistant_only_joke_does_not_create_memory_proposal(self) -> None:
        context = self._build_context(user_text="讲个笑话", assistant_text="你最喜欢蓝色沙发，对吧？")
        extraction = ProposalBatchExtractionOutput(
            memory_items=[
                ProposalExtractionItemOutput(
                    title="用户喜欢蓝色沙发",
                    summary="助手在笑话里说用户喜欢蓝色沙发。",
                    confidence=0.8,
                    evidence_message_ids=[context.turn_messages[1].message_id],
                    payload={"memory_type": "preference", "summary": "喜欢蓝色沙发"},
                )
            ]
        )

        drafts = MemoryProposalAnalyzer().analyze(context, extraction)

        self.assertEqual([], drafts)

    def test_user_explicit_rename_creates_config_proposal(self) -> None:
        context = self._build_context(user_text="以后你就叫阿福", assistant_text="好的，我记下了。")
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="应用 Agent 配置建议",
                    summary="用户明确要求把名字改成阿福。",
                    confidence=0.94,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"display_name": "阿福", "speaking_style": None, "personality_traits": []},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual("config_apply", drafts[0].proposal_kind)
        self.assertEqual("阿福", drafts[0].payload["display_name"])

    @patch("app.modules.conversation.service._generate_memory_candidates_for_turn")
    @patch("app.modules.conversation.service.ProposalPipeline.run")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_proposal_failure_does_not_break_main_reply(
        self,
        run_orchestrated_turn_mock,
        proposal_run_mock,
        generate_memory_mock,
    ) -> None:
        settings.conversation_proposal_shadow_enabled = True
        settings.conversation_proposal_write_enabled = False
        generate_memory_mock.return_value = None
        proposal_run_mock.side_effect = RuntimeError("proposal pipeline down")
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="当然可以，我们先聊聊天。",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name=self.agent.display_name,
            intent_detection=ConversationIntentDetection(
                primary_intent=ConversationIntentLabel.FREE_CHAT,
                route_intent=ConversationIntent.FREE_CHAT,
                confidence=0.8,
                reason="普通闲聊",
                lane_selection=ConversationLaneSelection(
                    lane=ConversationLane.FREE_CHAT,
                    confidence=0.8,
                    reason="按 free_chat 处理",
                    target_kind="none",
                    requires_clarification=False,
                    source="intent_mapping",
                ),
            ),
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="以后你叫阿福吧", channel="text"),
            actor=self.actor,
        )

        self.assertEqual("completed", turn.outcome)
        self.assertIsNone(turn.error_message)
        self.assertEqual("当然可以，我们先聊聊天。", turn.session.messages[-1].content)
        proposal_run_mock.assert_called_once()

    def _build_context(self, *, user_text: str, assistant_text: str) -> TurnProposalContext:
        now = utc_now_iso()
        session = ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=self.agent.id,
            current_request_id="req-test",
            last_event_seq=0,
            title="测试对话",
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        user_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="req-test",
            seq=1,
            role="user",
            message_type="text",
            content=user_text,
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json="[]",
            suggestions_json="[]",
            created_at=now,
            updated_at=now,
        )
        assistant_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="req-test",
            seq=2,
            role="assistant",
            message_type="text",
            content=assistant_text,
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json="[]",
            suggestions_json="[]",
            created_at=now,
            updated_at=now,
        )
        return build_turn_proposal_context(
            session=session,
            request_id="req-test",
            user_message=user_message,
            assistant_message=assistant_message,
            conversation_history_excerpt=[],
            lane_result={"lane": "free_chat", "target_kind": "none"},
            main_reply_summary=assistant_text,
        )


if __name__ == "__main__":
    unittest.main()
