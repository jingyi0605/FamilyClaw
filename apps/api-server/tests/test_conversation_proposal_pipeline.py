import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.modules.account.schemas import HouseholdAccountCreateRequest
from app.modules.account.service import AuthenticatedActor
from app.modules.account.service import create_household_account_with_binding
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
from app.modules.conversation.proposal_pipeline import (
    ProposalPipeline,
    ProposalPipelineResult,
    TurnProposalContext,
    build_turn_proposal_context,
    extract_proposal_batch,
)
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import create_conversation_session, create_conversation_turn
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.definitions import get_task
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput, ProposalExtractionItemOutput
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.scheduler.schemas import ScheduledTaskDefinitionCreate
from app.modules.scheduler.service import create_task_definition


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
                title="鎻愰啋鑽夌",
                summary="娴嬭瘯鎻愰啋",
                evidence_message_ids=[turn_context.turn_messages[0].message_id],
                evidence_roles=["user"],
                dedupe_key="reminder:test",
                confidence=0.8,
                payload={"title": "鎻愰啋鑽夌", "action_type": "reminder_create"},
            )
        ]


class ConversationProposalPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_shadow = settings.conversation_proposal_shadow_enabled
        self._previous_write = settings.conversation_proposal_write_enabled

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
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
                display_name="绗ㄧ",
                agent_type="butler",
                self_identity="鎴戞槸瀹跺涵绠″",
                role_summary="璐熻矗瀹跺涵闂瓟",
                personality_traits=["缁嗗績"],
                service_focus=["鑱婂ぉ"],
                default_entry=True,
            ),
        )
        self.account, _ = create_household_account_with_binding(
            self.db,
            HouseholdAccountCreateRequest(
                household_id=self.household.id,
                member_id=self.member.id,
                username="owner",
                password="owner123",
                must_change_password=False,
            ),
        )
        self.db.commit()

        self.actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id=self.member.id,
            account_id=self.account.id,
            account_type="household",
            account_status="active",
            username=self.account.username,
            household_id=self.household.id,
            member_id=self.member.id,
            member_role="admin",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        settings.conversation_proposal_shadow_enabled = self._previous_shadow
        settings.conversation_proposal_write_enabled = self._previous_write
        self._tempdir.cleanup()

    def test_registry_isolates_single_analyzer_failure(self) -> None:
        context = self._build_context(user_text="鏄庡ぉ鎻愰啋鎴戝紑浼?, assistant_text="濂界殑")
        registry = ProposalAnalyzerRegistry(analyzers=[_FailingAnalyzer(), _ReminderLikeAnalyzer()])

        drafts, failures = registry.run(context, ProposalBatchExtractionOutput())

        self.assertEqual(1, len(drafts))
        self.assertEqual("reminder_create", drafts[0].proposal_kind)
        self.assertEqual(1, len(failures))
        self.assertEqual("failing", failures[0].analyzer_name)

    def test_assistant_only_joke_does_not_create_memory_proposal(self) -> None:
        context = self._build_context(user_text="璁蹭釜绗戣瘽", assistant_text="浣犳渶鍠滄钃濊壊娌欏彂锛屽鍚э紵")
        extraction = ProposalBatchExtractionOutput(
            memory_items=[
                ProposalExtractionItemOutput(
                    title="鐢ㄦ埛鍠滄钃濊壊娌欏彂",
                    summary="鍔╂墜鍦ㄧ瑧璇濋噷璇寸敤鎴峰枩娆㈣摑鑹叉矙鍙戙€?,
                    confidence=0.8,
                    evidence_message_ids=[context.turn_messages[1].message_id],
                    payload={"memory_type": "preference", "summary": "鍠滄钃濊壊娌欏彂"},
                )
            ]
        )

        drafts = MemoryProposalAnalyzer().analyze(context, extraction)

        self.assertEqual([], drafts)

    def test_memory_proposal_analyzer_builds_summary_from_payload_when_missing(self) -> None:
        context = self._build_context(user_text="璁颁綇鎴戜笉鍠滄鍚冭荆妞?, assistant_text="濂界殑锛屾垜璁颁綇浜嗐€?)
        extraction = ProposalBatchExtractionOutput(
            memory_items=[
                ProposalExtractionItemOutput(
                    title=None,
                    summary=None,
                    confidence=0.88,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"涓嶅枩娆㈢殑椋熺墿": "杈ｆ"},
                )
            ]
        )

        drafts = MemoryProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual("memory_write", drafts[0].proposal_kind)
        self.assertIn("杈ｆ", drafts[0].summary or "")
        self.assertEqual("preference", drafts[0].payload["memory_type"])

    def test_proposal_pipeline_filters_noop_config_draft_when_name_matches_current_agent(self) -> None:
        now = utc_now_iso()
        session = ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=self.agent.id,
            current_request_id="req-test",
            last_event_seq=0,
            title="娴嬭瘯瀵硅瘽",
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        context = self._build_context(user_text="璁颁綇鎴戜笉鍠滄鍚冭荆妞?, assistant_text="濂界殑锛屾垜璁颁綇浜嗐€?)
        extraction = ProposalBatchExtractionOutput(
            memory_items=[
                ProposalExtractionItemOutput(
                    title=None,
                    summary=None,
                    confidence=0.88,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"涓嶅枩娆㈢殑椋熺墿": "杈ｆ"},
                )
            ],
            config_items=[
                ProposalExtractionItemOutput(
                    title="搴旂敤 Agent 閰嶇疆寤鸿",
                    summary="鎶婂悕瀛楁敼鎴愬綋鍓嶅悕瀛椼€?,
                    confidence=0.3,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"display_name": self.agent.display_name},
                )
            ],
        )
        pipeline = ProposalPipeline(extractor=lambda db, turn_context, household_id: extraction)

        result = pipeline.run(
            self.db,
            session=session,
            request_id="req-test",
            turn_context=context,
            persist=False,
        )

        self.assertEqual(1, len(result.drafts))
        self.assertEqual("memory_write", result.drafts[0].proposal_kind)

    def test_user_explicit_rename_creates_config_proposal(self) -> None:
        context = self._build_context(user_text="浠ュ悗浣犲氨鍙樋绂?, assistant_text="濂界殑锛屾垜璁颁笅浜嗐€?)
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="搴旂敤 Agent 閰嶇疆寤鸿",
                    summary="鐢ㄦ埛鏄庣‘瑕佹眰鎶婂悕瀛楁敼鎴愰樋绂忋€?,
                    confidence=0.94,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"display_name": "闃跨", "speaking_style": None, "personality_traits": []},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual("config_apply", drafts[0].proposal_kind)
        self.assertEqual("闃跨", drafts[0].payload["display_name"])

    def test_config_proposal_analyzer_normalizes_name_alias_to_display_name(self) -> None:
        context = self._build_context(user_text="灏卞彨璞嗚眴鍚?, assistant_text="濂斤紝閭ｆ垜璁颁竴涓嬨€?)
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="搴旂敤 Agent 閰嶇疆寤鸿",
                    summary="鐢ㄦ埛鏄庣‘鎻愬嚭鎶婂悕瀛楁敼鎴愯眴璞嗐€?,
                    confidence=0.92,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"name": "璞嗚眴"},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual("璞嗚眴", drafts[0].payload["display_name"])
        self.assertNotIn("name", drafts[0].payload)

    def test_config_proposal_analyzer_normalizes_prefixed_evidence_message_id(self) -> None:
        context = self._build_context(user_text="call you bubble", assistant_text="ok")
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="config update",
                    summary="rename agent",
                    confidence=0.91,
                    evidence_message_ids=[f"user_{context.turn_messages[0].message_id}"],
                    payload={"display_name": "Bubble"},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual([context.turn_messages[0].message_id], drafts[0].evidence_message_ids)
        self.assertEqual(["user"], drafts[0].evidence_roles)

    def test_memory_proposal_analyzer_normalizes_colon_prefixed_evidence_message_id(self) -> None:
        context = self._build_context(user_text="remember I like sweets", assistant_text="ok")
        extraction = ProposalBatchExtractionOutput(
            memory_items=[
                ProposalExtractionItemOutput(
                    title=None,
                    summary=None,
                    confidence=0.86,
                    evidence_message_ids=[f"user_message:{context.turn_messages[0].message_id}"],
                    payload={"food_preference": "鍠滄鍚冪敎"},
                )
            ]
        )

        drafts = MemoryProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual("memory_write", drafts[0].proposal_kind)
        self.assertEqual([context.turn_messages[0].message_id], drafts[0].evidence_message_ids)
        self.assertEqual(["user"], drafts[0].evidence_roles)

    @patch("app.modules.conversation.proposal_pipeline.invoke_llm")
    def test_extract_proposal_batch_redacts_assistant_reply_before_llm(self, invoke_llm_mock) -> None:
        context = self._build_context(
            user_text="浣犵煡閬撴垜鏈€鍠滄鍚冧粈涔堝悧",
            assistant_text="鏍规嵁鎴戠殑璁板綍锛屼綘鐗瑰埆鍠滄宸у厠鍔涜泲绯曞拰鐢滈銆?,
        )
        invoke_llm_mock.return_value = SimpleNamespace(data=ProposalBatchExtractionOutput())

        extract_proposal_batch(self.db, context, self.household.id)

        variables = invoke_llm_mock.call_args.kwargs["variables"]
        self.assertIn("浣犵煡閬撴垜鏈€鍠滄鍚冧粈涔堝悧", variables["turn_messages"])
        self.assertNotIn("宸у厠鍔涜泲绯曞拰鐢滈", variables["turn_messages"])
        self.assertIn("浠呬綔涓婁笅鏂?, variables["turn_messages"])
        self.assertNotIn("宸у厠鍔涜泲绯曞拰鐢滈", variables["main_reply_summary"])
        self.assertIn("涓嶈兘浣滀负鏂板浜嬪疄璇佹嵁", variables["main_reply_summary"])

    def test_once_schedule_intent_creates_scheduled_task_proposal(self) -> None:
        context = self._build_context(user_text="鏄庡ぉ涓婂崍10鐐规彁閱掓垜寮€浼?, assistant_text="鎴戞潵鏁寸悊鎴愪竴娆℃€ц鍒掍换鍔°€?)

        result = ProposalPipeline(extractor=lambda db, turn_context, household_id: ProposalBatchExtractionOutput()).run(
            self.db,
            session=self._build_session(),
            request_id="req-once",
            turn_context=context,
            persist=False,
        )

        self.assertEqual("scheduled_task_create", result.drafts[0].proposal_kind)
        self.assertEqual("once", result.drafts[0].payload["draft_payload"]["schedule_type"])

    def test_pause_intent_creates_scheduled_task_pause_proposal(self) -> None:
        actor = AuthenticatedActor(
            account_id=self.actor.account_id or "account-1",
            username=self.actor.username or "owner",
            account_type=self.actor.account_type,
            account_status=self.actor.account_status,
            household_id=self.actor.household_id,
            member_id=self.actor.member_id,
            member_role=self.actor.member_role,
            must_change_password=False,
        )
        task = create_task_definition(
            self.db,
            actor=actor,
            payload=ScheduledTaskDefinitionCreate(
                household_id=self.household.id,
                owner_scope="member",
                owner_member_id=self.member.id,
                code="take-medicine",
                name="鍚冭嵂鎻愰啋",
                trigger_type="schedule",
                schedule_type="daily",
                schedule_expr="21:00",
                target_type="agent_reminder",
                target_ref_id=self.agent.id,
            ),
        )
        context = self._build_context(user_text="鎶婂悆鑽彁閱掓殏鍋?, assistant_text="濂界殑锛屾垜鍏堢粰浣犵‘璁ゃ€?)

        result = ProposalPipeline(extractor=lambda db, turn_context, household_id: ProposalBatchExtractionOutput()).run(
            self.db,
            session=self._build_session(),
            request_id="req-pause",
            turn_context=context,
            persist=False,
        )

        self.assertEqual("scheduled_task_pause", result.drafts[0].proposal_kind)
        self.assertEqual(task.id, result.drafts[0].payload["task_id"])

    def test_config_proposal_analyzer_falls_back_to_latest_user_message_when_evidence_invalid(self) -> None:
        context = self._build_context(user_text="call you bubble", assistant_text="ok")
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="config update",
                    summary="rename agent",
                    confidence=0.91,
                    evidence_message_ids=["user_missing-message-id"],
                    payload={"display_name": "Bubble"},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual(1, len(drafts))
        self.assertEqual([context.turn_messages[0].message_id], drafts[0].evidence_message_ids)
        self.assertEqual(["user"], drafts[0].evidence_roles)
        self.assertEqual("Bubble", drafts[0].payload["display_name"])

    def test_config_proposal_analyzer_rejects_placeholder_name(self) -> None:
        context = self._build_context(user_text="鎴戠粰浣犳敼涓悕瀛楀惂", assistant_text="濂藉憖锛屼綘鎯虫敼鎴愪粈涔堬紵")
        extraction = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="搴旂敤 Agent 閰嶇疆寤鸿",
                    summary="鐢ㄦ埛琛ㄨ揪浜嗘兂鏀瑰悕锛屼絾杩樻病缁欏嚭鍏蜂綋鍚嶅瓧銆?,
                    confidence=0.6,
                    evidence_message_ids=[context.turn_messages[0].message_id],
                    payload={"name": "鏂板悕瀛?},
                )
            ]
        )

        drafts = ConfigProposalAnalyzer().analyze(context, extraction)

        self.assertEqual([], drafts)

    def test_proposal_batch_extraction_prompt_examples_do_not_break_format(self) -> None:
        task = get_task("proposal_batch_extraction")

        messages = task.build_messages(
            variables={
                "turn_messages": "[user_message] user(u1): 浠ュ悗浣犲氨鍙樋绂?,
                "trusted_events": "[]",
                "main_reply_summary": "濂界殑锛屼互鍚庢垜灏卞彨闃跨銆?,
            },
            conversation_history=[],
        )

        self.assertGreaterEqual(len(messages), 2)
        self.assertIn("display_name", messages[0]["content"])

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
            text="褰撶劧鍙互锛屾垜浠厛鑱婅亰澶┿€?,
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
                reason="鏅€氶棽鑱?,
                lane_selection=ConversationLaneSelection(
                    lane=ConversationLane.FREE_CHAT,
                    confidence=0.8,
                    reason="鎸?free_chat 澶勭悊",
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
            payload=ConversationTurnCreate(message="浠ュ悗浣犲彨闃跨鍚?, channel="text"),
            actor=self.actor,
        )

        self.assertEqual("completed", turn.outcome)
        self.assertIsNone(turn.error_message)
        self.assertEqual("褰撶劧鍙互锛屾垜浠厛鑱婅亰澶┿€?, turn.session.messages[-1].content)
        proposal_run_mock.assert_called_once()

    @patch("app.modules.conversation.service._append_debug_log")
    @patch("app.modules.conversation.service.ProposalPipeline.run")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_proposal_pipeline_completed_log_contains_raw_extraction_output(
        self,
        run_orchestrated_turn_mock,
        proposal_run_mock,
        append_debug_log_mock,
    ) -> None:
        settings.conversation_proposal_shadow_enabled = True
        settings.conversation_proposal_write_enabled = False
        extraction_output = ProposalBatchExtractionOutput(
            config_items=[
                ProposalExtractionItemOutput(
                    title="搴旂敤 Agent 閰嶇疆寤鸿",
                    summary="鐢ㄦ埛鏄庣‘瑕佹眰鎶婂悕瀛楁敼鎴愰樋绂忋€?,
                    confidence=0.94,
                    evidence_message_ids=["u1"],
                    payload={"display_name": "闃跨", "speaking_style": None, "personality_traits": []},
                )
            ]
        )
        proposal_run_mock.return_value = ProposalPipelineResult(
            batch_id=None,
            item_ids=[],
            drafts=[],
            failures=[ProposalAnalyzerFailure(analyzer_name="config_proposal_analyzer", error_message="test-failure")],
            extraction_output=extraction_output,
        )
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="濂界殑锛屾垜浠厛鑱婅亰澶┿€?,
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
                reason="鏅€氶棽鑱?,
                lane_selection=ConversationLaneSelection(
                    lane=ConversationLane.FREE_CHAT,
                    confidence=0.8,
                    reason="鎸?free_chat 澶勭悊",
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

        create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="浠ュ悗浣犲彨闃跨鍚?, channel="text"),
            actor=self.actor,
        )

        matched_payloads = [
            call.kwargs.get("payload", {})
            for call in append_debug_log_mock.call_args_list
            if call.kwargs.get("stage") == "proposal.pipeline.completed"
        ]
        self.assertEqual(1, len(matched_payloads))
        self.assertEqual("闃跨", matched_payloads[0]["extraction_output"]["config_items"][0]["payload"]["display_name"])
        self.assertEqual("config_proposal_analyzer", matched_payloads[0]["analyzer_failures"][0]["analyzer_name"])

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
            title="娴嬭瘯瀵硅瘽",
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
            db=self.db,
            session=session,
            request_id="req-test",
            authenticated_actor=AuthenticatedActor(
                account_id=self.actor.account_id or "account-1",
                username=self.actor.username or "owner",
                account_type=self.actor.account_type,
                account_status=self.actor.account_status,
                household_id=self.actor.household_id,
                member_id=self.actor.member_id,
                member_role=self.actor.member_role,
                must_change_password=False,
            ),
            user_message=user_message,
            assistant_message=assistant_message,
            conversation_history_excerpt=[],
            lane_result={"lane": "free_chat", "target_kind": "none"},
            main_reply_summary=assistant_text,
        )

    def _build_session(self, *, now: str | None = None) -> ConversationSession:
        session_now = now or utc_now_iso()
        return ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=self.agent.id,
            current_request_id="req-test",
            last_event_seq=0,
            title="娴嬭瘯瀵硅瘽",
            status="active",
            last_message_at=session_now,
            created_at=session_now,
            updated_at=session_now,
        )


if __name__ == "__main__":
    unittest.main()

