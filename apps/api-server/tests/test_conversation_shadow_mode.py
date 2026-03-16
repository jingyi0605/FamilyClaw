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

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
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
                display_name="绗ㄧ",
                agent_type="butler",
                self_identity="鎴戞槸瀹跺涵绠″",
                role_summary="璐熻矗瀹跺涵闂瓟",
                personality_traits=["缁嗗績"],
                service_focus=["鑱婂ぉ"],
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
        self._db_helper.close()
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
                    reason="鐢ㄦ埛鏄庣‘鎯崇粰鍔╂墜鏀瑰悕銆?,
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(
                data=type("_ConfigDraft", (), {"display_name": "闃跨", "speaking_style": None, "personality_traits": []})()
            ),
        ]
        select_lane_mock.return_value = ConversationLaneSelection(
            lane=ConversationLane.REALTIME_QUERY,
            confidence=0.82,
            reason="褰卞瓙妯″紡涓嬭涔夎矾鐢辫涓烘洿鍍忓疄鏃舵煡璇€?,
            target_kind="state_query",
            requires_clarification=False,
            source="intent_mapping",
        )

        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="浠ュ悗浣犲氨鍙樋绂?,
            actor=self.actor,
            conversation_history=[],
        )

        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("闃跨", result.config_suggestion["display_name"])
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
            text="濂界殑锛屾垜璁颁綇浜嗐€?,
            data=None,
        )
        run_orchestrated_turn_mock.return_value = __import__("types").SimpleNamespace(
            intent=ConversationIntent.FREE_CHAT,
            text="濂界殑锛屾垜璁颁綇浜嗐€?,
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
                reason="鏅€氳亰澶?,
                target_kind="none",
                requires_clarification=False,
                source="intent_mapping",
            ),
            intent_detection=ConversationIntentDetection(
                primary_intent=ConversationIntentLabel.FREE_CHAT,
                route_intent=ConversationIntent.FREE_CHAT,
                confidence=0.8,
                reason="鏅€氳亰澶?,
            ),
        )
        proposal_pipeline_mock.return_value = ProposalPipelineResult(
            batch_id=None,
            item_ids=[],
            drafts=[
                ProposalDraft(
                    proposal_kind="memory_write",
                    policy_category="ask",
                    title="涓嶅悆棣欒彍",
                    summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁涓嶅悆棣欒彍銆?,
                    evidence_message_ids=["u1"],
                    evidence_roles=["user"],
                    dedupe_key="memory:shadow:diet",
                    confidence=0.9,
                    payload={"memory_type": "preference", "summary": "鐢ㄦ埛鏄庣‘琛ㄧず鑷繁涓嶅悆棣欒彍銆?},
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
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜涓嶅悆棣欒彍"),
            actor=self.actor,
        )

        self.assertEqual("completed", turn.outcome)
        self.assertEqual([], turn.session.proposal_batches)


if __name__ == "__main__":
    unittest.main()

