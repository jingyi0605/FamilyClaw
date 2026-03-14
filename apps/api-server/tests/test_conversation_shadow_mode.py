import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import new_uuid
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationLaneSelection,
    run_orchestrated_turn,
)
from app.modules.conversation.proposal_analyzers import ProposalDraft
from app.modules.conversation.proposal_pipeline import ProposalPipelineResult
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.llm_task.output_models import ConversationIntentDetectionOutput


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider") -> None:
        self.text = text
        self.data = data
        self.provider = provider


class ConversationShadowModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_lane_shadow = settings.conversation_lane_shadow_enabled
        self._previous_takeover = settings.conversation_lane_takeover_enabled
        self._previous_proposal_shadow = settings.conversation_proposal_shadow_enabled
        self._previous_proposal_write = settings.conversation_proposal_write_enabled

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"
        settings.conversation_lane_shadow_enabled = False
        settings.conversation_lane_takeover_enabled = True
        settings.conversation_proposal_shadow_enabled = False
        settings.conversation_proposal_write_enabled = True

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Shadow Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
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
        settings.conversation_lane_shadow_enabled = self._previous_lane_shadow
        settings.conversation_lane_takeover_enabled = self._previous_takeover
        settings.conversation_proposal_shadow_enabled = self._previous_proposal_shadow
        settings.conversation_proposal_write_enabled = self._previous_proposal_write
        self._tempdir.cleanup()

    @patch("app.modules.conversation.orchestrator.get_conversation_debug_logger")
    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_lane_shadow_logs_without_taking_over(
        self,
        invoke_llm_mock,
        select_lane_mock,
        debug_logger_mock,
    ) -> None:
        settings.conversation_lane_shadow_enabled = True
        settings.conversation_lane_takeover_enabled = False
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
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
                data=type("_ConfigDraft", (), {"display_name": "阿福", "speaking_style": None, "personality_traits": []})()
            ),
        ]
        select_lane_mock.return_value = ConversationLaneSelection(
            lane=ConversationLane.REALTIME_QUERY,
            confidence=0.82,
            reason="影子模式下语义路由认为更像实时查询。",
            target_kind="state_query",
            requires_clarification=False,
            source="semantic_router",
        )

        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="以后你就叫阿福",
            actor=self.actor,
            conversation_history=[],
        )

        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("阿福", result.config_suggestion["display_name"])
        logged_payloads = "".join(str(call.args[0]) for call in debug_logger_mock.return_value.info.call_args_list)
        self.assertIn("lane.shadow.evaluated", logged_payloads)

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_proposal_shadow_runs_without_persisting_batches(
        self,
        run_orchestrated_turn_mock,
        proposal_pipeline_mock,
    ) -> None:
        settings.conversation_proposal_shadow_enabled = True
        settings.conversation_proposal_write_enabled = False
        run_orchestrated_turn_mock.return_value = _FakeLlmResult(
            text="好的，我记住了。",
            data=None,
        )
        run_orchestrated_turn_mock.return_value = __import__("types").SimpleNamespace(
            intent=ConversationIntent.FREE_CHAT,
            text="好的，我记住了。",
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
            lane_selection=ConversationLaneSelection(
                lane=ConversationLane.FREE_CHAT,
                confidence=0.8,
                reason="普通聊天",
                target_kind="none",
                requires_clarification=False,
                source="intent_mapping",
            ),
            intent_detection=ConversationIntentDetection(
                primary_intent=ConversationIntentLabel.FREE_CHAT,
                route_intent=ConversationIntent.FREE_CHAT,
                confidence=0.8,
                reason="普通聊天",
            ),
        )
        proposal_pipeline_mock.return_value = ProposalPipelineResult(
            batch_id=None,
            item_ids=[],
            drafts=[
                ProposalDraft(
                    proposal_kind="memory_write",
                    policy_category="ask",
                    title="不吃香菜",
                    summary="用户明确表示自己不吃香菜。",
                    evidence_message_ids=["u1"],
                    evidence_roles=["user"],
                    dedupe_key="memory:shadow:diet",
                    confidence=0.9,
                    payload={"memory_type": "preference", "summary": "用户明确表示自己不吃香菜。"},
                )
            ],
            failures=[],
            extraction_output=None,
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

        self.assertEqual("completed", turn.outcome)
        self.assertEqual([], turn.session.proposal_batches)


if __name__ == "__main__":
    unittest.main()
