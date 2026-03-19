import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate, AgentRuntimePolicyUpsert
from app.modules.agent.service import create_agent, get_agent_detail, upsert_agent_runtime_policy
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalBatch, ConversationProposalItem
from app.modules.device.models import Device
from app.modules.llm_task import LlmResult, LlmStreamEvent
from app.modules.conversation.orchestrator import (
    ConversationIntent,
    ConversationIntentDetection,
    ConversationIntentLabel,
    ConversationLane,
    ConversationLaneSelection,
    ConversationOrchestratorResult,
    _build_free_chat_variables,
    detect_conversation_intent,
    run_orchestrated_turn,
    stream_orchestrated_turn,
)
from app.modules.conversation.proposal_analyzers import ProposalDraft
from app.modules.conversation.proposal_pipeline import ProposalPipelineResult
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import (
    create_conversation_session,
    create_conversation_turn,
    confirm_conversation_proposal,
    dismiss_conversation_proposal,
    get_conversation_session_detail,
    list_conversation_debug_logs,
    list_conversation_sessions,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.llm_task.output_models import (
    ConversationIntentDetectionOutput,
    ReminderExtractionOutput,
)
from app.modules.llm_task.parser import parse_to_model
from app.modules.ai_gateway.provider_runtime import build_template_fallback_output
from app.modules.agent.service import build_agent_runtime_context
from app.modules.family_qa.fact_view_service import build_qa_fact_view
from app.modules.memory.context_engine import build_memory_context_bundle
from app.modules.memory.models import MemoryCard
from app.modules.memory import repository as memory_repository
from app.modules.member.schemas import MemberCreate
from app.modules.member.preferences_schemas import MemberPreferenceUpsert
from app.modules.member.preferences_service import upsert_member_preferences
from app.modules.member.service import create_member
from app.modules.relationship.schemas import MemberRelationshipCreate
from app.modules.relationship.service import create_relationship
from app.modules.reminder.service import list_tasks as list_reminder_tasks


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider", degraded: bool = False) -> None:
        self.text = text
        self.data = data
        self.provider = provider
        self.degraded = degraded


class ConversationFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
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
                display_name="绗ㄧ",
                agent_type="butler",
                self_identity="鎴戞槸瀹跺涵涓荤瀹",
                role_summary="璐熻矗瀹跺涵闂瓟",
                personality_traits=["缁嗗績", "绋抽噸"],
                service_focus=["瀹跺涵闂瓟", "鎻愰啋"],
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

    def _build_channel_system_actor(self, *, member_id: str) -> ActorContext:
        return ActorContext(
            role="system",
            actor_type="system",
            actor_id="channel-conversation-bridge",
            account_id="system",
            account_type="system",
            account_status="active",
            username="system",
            household_id=self.household.id,
            member_id=member_id,
            member_role=None,
            is_authenticated=True,
        )

    def _create_memory_card_for_member(
        self,
        *,
        member_id: str,
        title: str,
        summary: str,
        normalized_text: str,
        visibility: str = "family",
        memory_type: str = "fact",
    ) -> MemoryCard:
        card = MemoryCard(
            id=new_uuid(),
            household_id=self.household.id,
            memory_type=memory_type,
            title=title,
            summary=summary,
            normalized_text=normalized_text,
            content_json=dump_json({"source": "test"}) or "{}",
            status="active",
            visibility=visibility,
            importance=4,
            confidence=0.95,
            subject_member_id=member_id,
            dedupe_key=f"test-memory:{member_id}:{title}",
            created_by="test",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        memory_repository.add_memory_card(self.db, card)
        self.db.flush()
        return card

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def _persist_mock_proposal_result(
        self,
        *,
        session_id: str,
        request_id: str,
        evidence_message_id: str,
        proposal_kind: str,
        payload: dict,
        title: str,
        summary: str,
        dedupe_key: str,
        confidence: float = 0.93,
    ) -> ProposalPipelineResult:
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session_id,
            request_id=request_id,
            source_message_ids_json=dump_json([evidence_message_id]) or "[]",
            source_roles_json=dump_json(["user"]) or "[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind=proposal_kind,
            policy_category="ask",
            status="pending_confirmation",
            title=title,
            summary=summary,
            evidence_message_ids_json=dump_json([evidence_message_id]) or "[]",
            evidence_roles_json=dump_json(["user"]) or "[]",
            dedupe_key=dedupe_key,
            confidence=confidence,
            payload_json=dump_json(payload) or "{}",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.flush()
        return ProposalPipelineResult(
            batch_id=batch.id,
            item_ids=[item.id],
            drafts=[
                ProposalDraft(
                    proposal_kind=proposal_kind,
                    policy_category="ask",
                    title=title,
                    summary=summary,
                    evidence_message_ids=[evidence_message_id],
                    evidence_roles=["user"],
                    dedupe_key=dedupe_key,
                    confidence=confidence,
                    payload=payload,
                )
            ],
            failures=[],
            extraction_output=None,
        )

    def test_create_conversation_session_rejects_explicit_non_conversation_agent(self) -> None:
        silent_agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="静默助手",
                agent_type="custom",
                self_identity="我是静默助手",
                role_summary="不允许直接聊天",
                personality_traits=["克制"],
                service_focus=["内部任务"],
                default_entry=False,
            ),
        )
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=silent_agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=False,
                default_entry=False,
                routing_tags=[],
                memory_scope=None,
            ),
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=silent_agent.id),
                actor=self.actor,
            )

        self.assertEqual(409, ctx.exception.status_code)
        self.assertIn("no available agent", str(ctx.exception.detail))

    def test_create_conversation_session_prefers_default_entry_conversation_agent(self) -> None:
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=False,
                default_entry=False,
                routing_tags=[],
                memory_scope=None,
            ),
        )
        backup_agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="候补助手",
                agent_type="custom",
                self_identity="我是候补助手",
                role_summary="负责接管聊天",
                personality_traits=["稳定"],
                service_focus=["问答"],
                default_entry=False,
            ),
        )
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=backup_agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=[],
                memory_scope=None,
            ),
        )
        self.db.commit()

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id),
            actor=self.actor,
        )

        self.assertEqual(backup_agent.id, session.active_agent_id)

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
            content="浣犲ソ",
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
            content="浣犲ソ锛屾垜鍦ㄣ€",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code="test-provider",
            ai_trace_id="trace-1",
            degraded=False,
            error_code=None,
            facts_json=dump_json([{"type": "active_member", "label": "Owner"}]),
            suggestions_json=dump_json(["鐜板湪瀹堕噷浠€涔堢姸鎬侊紵"]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, assistant_message)

        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-hello",
            source_message_ids_json=dump_json([assistant_message.id]) or "[]",
            source_roles_json=dump_json(["assistant"]) or "[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_confirmation",
            title="鐢ㄦ埛鍚戠瀹舵墦鎷涘懠",
            summary="鐢ㄦ埛涓庣瀹跺畬鎴愪簡棣栨闂€欍€",
            evidence_message_ids_json=dump_json([assistant_message.id]) or "[]",
            evidence_roles_json=dump_json(["assistant"]) or "[]",
            dedupe_key="memory:greeting",
            confidence=0.82,
            payload_json=dump_json({"source": "conversation", "message_id": assistant_message.id}) or "{}",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.commit()

        detail = get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor)

        self.assertEqual(2, len(detail.messages))
        self.assertEqual(["user", "assistant"], [item.role for item in detail.messages])
        self.assertEqual("浣犲ソ锛屾垜鍦ㄣ€", detail.messages[1].content)
        self.assertEqual(1, len(detail.proposal_batches))
        self.assertEqual("memory_write", detail.proposal_batches[0].items[0].proposal_kind)
        self.assertEqual("绗ㄧ", detail.active_agent_name)

    def test_build_agent_runtime_context_prefers_member_preferred_name(self) -> None:
        upsert_member_preferences(
            self.db,
            member_id=self.member.id,
            payload=MemberPreferenceUpsert(preferred_name="瀹濆疂"),
        )
        self.db.commit()

        runtime_context = build_agent_runtime_context(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            requester_member_id=self.member.id,
        )

        requester_profile = runtime_context.get("requester_member_profile")
        assert isinstance(requester_profile, dict)
        self.assertEqual("瀹濆疂", requester_profile.get("preferred_display_name"))

    def test_build_qa_fact_view_prefers_member_preferred_name(self) -> None:
        upsert_member_preferences(
            self.db,
            member_id=self.member.id,
            payload=MemberPreferenceUpsert(preferred_name="瀹濆疂"),
        )
        self.db.commit()

        fact_view = build_qa_fact_view(
            self.db,
            household_id=self.household.id,
            requester_member_id=self.member.id,
            agent_id=self.agent.id,
            actor=self.actor,
            question="鎴戠幇鍦ㄥ湪鍝",
        )

        self.assertIsNotNone(fact_view.active_member)
        assert fact_view.active_member is not None
        self.assertEqual("瀹濆疂", fact_view.active_member.name)
        self.assertIn("瀹濆疂", [item.name for item in fact_view.member_states])
        self.assertIn("瀹濆疂", [item.name for item in fact_view.member_profiles])

    def test_build_memory_context_bundle_uses_bound_member_for_channel_system_actor(self) -> None:
        target_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Jack", role="adult"),
        )
        self._create_memory_card_for_member(
            member_id=target_member.id,
            title="鐖卞ソ鏄敱姝",
            summary="Jack 鐨勭埍濂芥槸鍞辨瓕銆",
            normalized_text="鐖卞ソ 鍠滄鍞辨瓕 鍞辨瓕",
            memory_type="preference",
        )
        self.db.commit()

        bundle = build_memory_context_bundle(
            self.db,
            household_id=self.household.id,
            actor=self._build_channel_system_actor(member_id=target_member.id),
            requester_member_id=target_member.id,
            question="浣犵煡閬撴垜鐨勭埍濂藉悧",
            capability="conversation_free_chat",
        )

        self.assertEqual(1, bundle.hot_summary.total_visible_cards)
        self.assertEqual(1, bundle.query_result.total)
        self.assertEqual("鐖卞ソ鏄敱姝", bundle.query_result.items[0].card.title)

    def test_build_qa_fact_view_reads_memory_for_channel_system_actor(self) -> None:
        target_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Jack", role="adult"),
        )
        self._create_memory_card_for_member(
            member_id=target_member.id,
            title="鐖卞ソ鏄敱姝",
            summary="Jack 鐨勭埍濂芥槸鍞辨瓕銆",
            normalized_text="鐖卞ソ 鍠滄鍞辨瓕 鍞辨瓕",
            memory_type="preference",
        )
        self.db.commit()

        fact_view = build_qa_fact_view(
            self.db,
            household_id=self.household.id,
            requester_member_id=target_member.id,
            agent_id=self.agent.id,
            actor=self._build_channel_system_actor(member_id=target_member.id),
            question="浣犵煡閬撴垜鐨勭埍濂藉悧",
        )

        self.assertEqual("available", fact_view.memory_summary.status)
        self.assertEqual(1, len(fact_view.memory_summary.items))
        self.assertEqual("鐖卞ソ鏄敱姝", fact_view.memory_summary.items[0].label)

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
            text="浣犲ソ锛屾垜鍦ㄣ€",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-debug",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
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
                payload=ConversationTurnCreate(message="浣犲ソ"),
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
                title="鎴戠殑浼氳瘽",
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
                title="鍒汉鐨勪細璇",
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
        self.assertEqual("鎴戠殑浼氳瘽", result.items[0].title)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_persists_completed_messages(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.STRUCTURED_QA,
            text="浣犲ソ锛屾垜鏄绗ㄣ€",
            degraded=False,
            facts=[],
            suggestions=["缁х画闂竴涓棶棰"],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-sync",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
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
            payload=ConversationTurnCreate(message="浣犲ソ"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertIsNone(result.error_message)
        self.assertEqual(2, len(result.session.messages))
        self.assertEqual("user", result.session.messages[0].role)
        self.assertEqual("assistant", result.session.messages[1].role)
        self.assertEqual("completed", result.session.messages[1].status)
        self.assertEqual("浣犲ソ锛屾垜鏄绗ㄣ€", result.session.messages[1].content)

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
            payload=ConversationTurnCreate(message="浣犲ソ"),
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
            content="涓婁竴娆＄殑闂",
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
            content="涓婁竴娆＄殑鍥炵瓟",
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
                    {"role": "user", "content": "涓婁竴娆＄殑闂"},
                    {"role": "assistant", "content": "涓婁竴娆＄殑鍥炵瓟"},
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
                text="杩欐槸鏂颁竴杞洖绛",
                degraded=False,
                facts=[],
                suggestions=[],
                memory_candidate_payloads=[],
                config_suggestion=None,
                action_payloads=[],
                ai_trace_id="trace-history",
                ai_provider_code="mock-provider",
                effective_agent_id=self.agent.id,
                effective_agent_name="绗ㄧ",
            )

        run_orchestrated_turn_mock.side_effect = _fake_run

        result = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="鏂扮殑闂"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual("杩欐槸鏂颁竴杞洖绛", result.session.messages[-1].content)

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_writes_new_proposal_batches(self, run_orchestrated_turn_mock, proposal_pipeline_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="璁颁笅鏉ヤ簡锛屼綘delayed memory銆",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id="trace-memory",
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )
        def _persist_proposal_result(*args, **kwargs):
            user_message = kwargs["user_message"]
            batch = ConversationProposalBatch(
                id=new_uuid(),
                session_id=user_message.session_id,
                request_id=user_message.request_id,
                source_message_ids_json=dump_json([user_message.id]) or "[]",
                source_roles_json=dump_json(["user"]) or "[]",
                lane_json='{"lane":"free_chat"}',
                status="pending_confirmation",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            conversation_repository.add_proposal_batch(self.db, batch)
            item = ConversationProposalItem(
                id=new_uuid(),
                batch_id=batch.id,
                proposal_kind="memory_write",
                policy_category="ask",
                status="pending_confirmation",
                title="delayed memory",
                summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆",
                evidence_message_ids_json=dump_json([user_message.id]) or "[]",
                evidence_roles_json=dump_json(["user"]) or "[]",
                dedupe_key="memory:test:diet",
                confidence=0.93,
                payload_json=dump_json({"memory_type": "preference", "summary": "鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆"}) or "{}",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            conversation_repository.add_proposal_item(self.db, item)
            self.db.flush()
            return ProposalPipelineResult(
                batch_id=batch.id,
                item_ids=[item.id],
                drafts=[
                    ProposalDraft(
                        proposal_kind="memory_write",
                        policy_category="ask",
                        title="delayed memory",
                        summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆",
                        evidence_message_ids=[user_message.id],
                        evidence_roles=["user"],
                        dedupe_key="memory:test:diet",
                        confidence=0.93,
                        payload={"memory_type": "preference", "summary": "鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆"},
                    )
                ],
                failures=[],
                extraction_output=None,
            )

        proposal_pipeline_mock.side_effect = _persist_proposal_result

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
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜delayed memory"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual(1, len(result.session.proposal_batches))
        self.assertEqual(1, len(result.session.proposal_batches[0].items))
        self.assertEqual("memory_write", result.session.proposal_batches[0].items[0].proposal_kind)
        self.assertEqual("pending_confirmation", result.session.proposal_batches[0].items[0].status)

    @patch("app.modules.conversation.service.ProposalPipeline.run")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_notify_config_proposal_executes_and_keeps_completed_record(
        self,
        run_orchestrated_turn_mock,
        proposal_run_mock,
    ) -> None:
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
            intent=ConversationIntent.FREE_CHAT,
            text="鍚嶅瓧鎴戣涓嬩簡銆",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )

        def _persist(*args, **kwargs):
            turn_context = kwargs["turn_context"]
            return self._persist_mock_proposal_result(
                session_id=kwargs["session"].id,
                request_id=kwargs["request_id"],
                evidence_message_id=turn_context.user_messages[0].message_id,
                proposal_kind="config_apply",
                payload={"display_name": "娉℃场"},
                title="搴旂敤 Agent 閰嶇疆寤鸿",
                summary="鐢ㄦ埛鎯虫妸鍔╂墜鍚嶅瓧鏀规垚娉℃场銆",
                dedupe_key="config:test:bubble",
            )

        proposal_run_mock.side_effect = _persist

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="鍙场娉℃€庝箞鏍"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual(1, len(turn.session.proposal_batches))
        item = turn.session.proposal_batches[0].items[0]
        self.assertEqual("config_apply", item.proposal_kind)
        self.assertEqual("notify", item.policy_category)
        self.assertEqual("completed", item.status)
        self.assertEqual("娉℃场", get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor).active_agent_name)
        stages = [item.stage for item in list_conversation_debug_logs(self.db, session_id=session.id, actor=self.actor).items]
        self.assertIn("proposal.item.executed_notify", stages)
        self.assertNotIn("proposal.item.executed_auto", stages)

    @patch("app.modules.conversation.service.ProposalPipeline.run")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_auto_memory_proposal_executes_and_keeps_completed_record(
        self,
        run_orchestrated_turn_mock,
        proposal_run_mock,
    ) -> None:
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                autonomous_action_policy={"memory": "auto", "config": "ask", "action": "ask"},
            ),
        )
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="杩欎欢浜嬫垜璁颁笅浜嗐€",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )

        def _persist(*args, **kwargs):
            turn_context = kwargs["turn_context"]
            return self._persist_mock_proposal_result(
                session_id=kwargs["session"].id,
                request_id=kwargs["request_id"],
                evidence_message_id=turn_context.user_messages[0].message_id,
                proposal_kind="memory_write",
                payload={"memory_type": "preference", "summary": "鐢ㄦ埛delayed memory"},
                title="delayed memory",
                summary="鐢ㄦ埛delayed memory",
                dedupe_key="memory:test:diet",
            )

        proposal_run_mock.side_effect = _persist

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜delayed memory"),
            actor=self.actor,
        )
        self.db.commit()

        cards, total = memory_repository.list_memory_cards(
            self.db,
            household_id=self.household.id,
            page=1,
            page_size=20,
        )
        self.assertEqual(1, len(turn.session.proposal_batches))
        item = turn.session.proposal_batches[0].items[0]
        self.assertEqual("memory_write", item.proposal_kind)
        self.assertEqual("auto", item.policy_category)
        self.assertEqual("completed", item.status)
        self.assertEqual(1, total)
        self.assertEqual("delayed memory", cards[0].title)
        stages = [item.stage for item in list_conversation_debug_logs(self.db, session_id=session.id, actor=self.actor).items]
        self.assertIn("proposal.item.executed_auto", stages)
        self.assertNotIn("proposal.item.executed_notify", stages)

    @patch("app.modules.conversation.service.ProposalPipeline.run")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_notify_reminder_proposal_executes_and_keeps_completed_record(
        self,
        run_orchestrated_turn_mock,
        proposal_run_mock,
    ) -> None:
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                autonomous_action_policy={"memory": "ask", "config": "ask", "action": "notify"},
            ),
        )
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="鎻愰啋鎴戝凡缁忓畨鎺掑ソ浜嗐€",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )

        def _persist(*args, **kwargs):
            turn_context = kwargs["turn_context"]
            return self._persist_mock_proposal_result(
                session_id=kwargs["session"].id,
                request_id=kwargs["request_id"],
                evidence_message_id=turn_context.user_messages[0].message_id,
                proposal_kind="reminder_create",
                payload={
                    "action_type": "reminder_create",
                    "title": "寮€浼",
                    "trigger_at": "2026-03-15T08:00:00+08:00",
                    "description": "鎻愰啋鎴戝弬鍔犳櫒浼",
                },
                title="鍒涘缓鎻愰啋锛氬紑浼",
                summary="鎻愰啋鎴戞槑澶╂棭涓婂紑浼氥€",
                dedupe_key="reminder:test:meeting",
            )

        proposal_run_mock.side_effect = _persist

        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="鎻愰啋鎴戞槑澶╂棭涓婂叓鐐瑰紑浼"),
            actor=self.actor,
        )
        self.db.commit()

        tasks = list_reminder_tasks(self.db, household_id=self.household.id)
        self.assertEqual(1, len(turn.session.proposal_batches))
        item = turn.session.proposal_batches[0].items[0]
        self.assertEqual("reminder_create", item.proposal_kind)
        self.assertEqual("notify", item.policy_category)
        self.assertEqual("completed", item.status)
        self.assertEqual(1, len(tasks))
        self.assertEqual("寮€浼", tasks[0].title)

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
                reason="杩欐槸鏅€氬垱浣滈棽鑱娿€",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="璁?00瀛楃殑绉戝够鏁呬簨")
        self.assertEqual(ConversationIntentLabel.FREE_CHAT, intent.primary_intent)
        self.assertEqual(ConversationIntent.FREE_CHAT, intent.route_intent)

    def test_parse_intent_detection_output_from_dirty_text(self) -> None:
        parsed = parse_to_model(
            """This extra log explains the environment state.
<output>
{"primary_intent":"free_chat","secondary_intents":[],"confidence":0.91,"reason":"baseline parse note","candidate_actions":[]}
</output>""",
            ConversationIntentDetectionOutput,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual("free_chat", parsed.primary_intent)

    def test_parse_intent_detection_output_tolerates_string_candidate_actions(self) -> None:
        parsed = parse_to_model(
            """<output>
{"primary_intent":"free_chat","secondary_intents":[],"confidence":0.6,"reason":"structured parse note","candidate_actions":["suggestion_a","reminder_create"]}
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
            capability="text",
            payload={"task_type": "conversation_intent_detection"},
        )
        parsed = parse_to_model(str(output.get("text") or ""), ConversationIntentDetectionOutput)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual("free_chat", parsed.primary_intent)

    def test_template_fallback_for_free_chat_returns_human_greeting(self) -> None:
        output = build_template_fallback_output(
            capability="text",
            payload={"task_type": "free_chat", "user_message": "浣犲ソ"},
        )
        self.assertIn("浣犲ソ锛屾垜鍦", str(output.get("text") or ""))

    @patch("app.modules.conversation.orchestrator._build_free_chat_prompt_context")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_free_chat_does_not_treat_memory_degraded_as_response_degraded(
        self,
        invoke_llm_mock,
        build_free_chat_prompt_context_mock,
    ) -> None:
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
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.92,
                    reason="普通闲聊。",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(text="这轮回答是正常的。", degraded=False),
        ]
        build_free_chat_prompt_context_mock.return_value = SimpleNamespace(
            variables={"agent_context": "", "memory_context": "", "device_context": "", "household_context": ""},
            memory_bundle=SimpleNamespace(degraded=True),
            memory_trace_items=[],
        )

        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="你好",
            actor=self.actor,
            conversation_history=[],
        )

        self.assertEqual("这轮回答是正常的。", result.text)
        self.assertFalse(result.degraded)

    @patch("app.modules.conversation.orchestrator._build_free_chat_prompt_context")
    @patch("app.modules.conversation.orchestrator.stream_llm")
    @patch("app.modules.conversation.orchestrator.adetect_conversation_intent")
    def test_stream_orchestrated_turn_free_chat_does_not_treat_memory_degraded_as_response_degraded(
        self,
        adetect_conversation_intent_mock,
        stream_llm_mock,
        build_free_chat_prompt_context_mock,
    ) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        adetect_conversation_intent_mock.return_value = ConversationIntentDetection(
            primary_intent=ConversationIntentLabel.FREE_CHAT,
            secondary_intents=[],
            confidence=0.92,
            reason="普通闲聊。",
            candidate_actions=[],
            route_intent=ConversationIntent.FREE_CHAT,
        )
        build_free_chat_prompt_context_mock.return_value = SimpleNamespace(
            variables={"agent_context": "", "memory_context": "", "device_context": "", "household_context": ""},
            memory_bundle=SimpleNamespace(degraded=True),
            memory_trace_items=[],
        )

        async def _fake_stream():
            yield LlmStreamEvent("chunk", content="先回一半。")
            yield LlmStreamEvent(
                "done",
                result=LlmResult(
                    raw_text="完整回答。",
                    display_text="完整回答。",
                    provider="mock-provider",
                    degraded=False,
                ),
            )

        stream_llm_mock.return_value = _fake_stream()

        async def _collect():
            events: list[tuple[str, object]] = []
            async for event_type, payload in stream_orchestrated_turn(
                self.db,
                session=session,
                message="你好",
                actor=self.actor,
                conversation_history=[],
            ):
                events.append((event_type, payload))
            return events

        import asyncio

        events = asyncio.run(_collect())
        done_events = [payload for event_type, payload in events if event_type == "done"]
        self.assertEqual(1, len(done_events))
        self.assertFalse(done_events[0].degraded)

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
            "agent": {"name": "绗ㄧ"},
            "identity": {"role_summary": "AI绠″", "speaking_style": "鑷劧浜插垏"},
        }
        get_context_overview_mock.return_value = SimpleNamespace(
            active_member=SimpleNamespace(name="Owner"),
            home_mode="home",
            platform_health_status="offline",
        )
        build_memory_context_bundle_mock.return_value = SimpleNamespace(
            capability="conversation_free_chat",
            hot_summary=SimpleNamespace(
                total_visible_cards=2,
                top_memories=[
                    SimpleNamespace(memory_id="memory-1", title="缁欑瀹舵敼鍚", memory_type="preference", summary="鐢ㄦ埛鎯虫妸AI绠″鏀瑰悕涓烘殩鏆栥€", updated_at="2026-03-14T00:00:00Z"),
                ],
                preference_highlights=["鐢ㄦ埛鎯虫妸AI绠″鏀瑰悕涓烘殩鏆栥€"],
                recent_event_highlights=[],
            ),
            query_result=SimpleNamespace(
                total=1,
                items=[
                    SimpleNamespace(
                        card=SimpleNamespace(id="memory-1", title="缁欑瀹舵敼鍚", memory_type="preference", summary="鐢ㄦ埛鎯虫妸AI绠″鏀瑰悕涓烘殩鏆栥€"),
                        score=48,
                        matched_terms=["鏆栨殩"],
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
            user_message="浣犲彨浠€涔堟潵鐫€",
            request_context={"request_id": "req-1", "session_id": session.id},
            log_memory_context=True,
        )
        self.assertIn("鏆栨殩", variables["memory_context"])
        logger_mock.info.assert_called_once()
        logged_text = logger_mock.info.call_args[0][0]
        self.assertIn("memory_context.read", logged_text)
        self.assertIn("memory-1", logged_text)

    @patch("app.modules.conversation.orchestrator.build_memory_context_bundle")
    @patch("app.modules.conversation.orchestrator.build_agent_runtime_context")
    def test_build_free_chat_variables_prefers_member_preferred_name_in_household_context(
        self,
        build_agent_runtime_context_mock,
        build_memory_context_bundle_mock,
    ) -> None:
        upsert_member_preferences(
            self.db,
            member_id=self.member.id,
            payload=MemberPreferenceUpsert(preferred_name="瀹濆疂"),
        )
        self.db.commit()

        build_agent_runtime_context_mock.return_value = {
            "agent": {"name": "缁椼劎顑"},
            "identity": {"role_summary": "AI缁犫€愁啀", "speaking_style": "閼奉亞鍔ф禍鎻掑瀼"},
        }
        build_memory_context_bundle_mock.return_value = SimpleNamespace(
            hot_summary=SimpleNamespace(
                preference_highlights=[],
                recent_event_highlights=[],
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
        variables = _build_free_chat_variables(
            self.db,
            session=session,
            actor=self.actor,
            user_message="浣犺寰楁垜鍚",
        )

        self.assertIn("瀹濆疂", variables["household_context"])
        self.assertNotIn("Owner", variables["household_context"])

    @patch("app.modules.conversation.orchestrator.build_memory_context_bundle")
    @patch("app.modules.conversation.orchestrator.build_agent_runtime_context")
    def test_build_free_chat_variables_include_member_age_guardian_and_relationship(
        self,
        build_agent_runtime_context_mock,
        build_memory_context_bundle_mock,
    ) -> None:
        child_member = create_member(
            self.db,
            MemberCreate(
                household_id=self.household.id,
                name="朵朵",
                nickname="朵朵",
                role="child",
                gender="female",
                age_group="child",
                birthday=date(2018, 3, 20),
                guardian_member_id=self.member.id,
            ),
        )
        create_relationship(
            self.db,
            MemberRelationshipCreate(
                household_id=self.household.id,
                source_member_id=child_member.id,
                target_member_id=self.member.id,
                relation_type="daughter",
            ),
        )
        self.db.commit()

        build_agent_runtime_context_mock.return_value = {
            "agent": {"name": "绗ㄧ"},
            "identity": {"role_summary": "AI绠″", "speaking_style": "鑷劧浜插垏"},
        }
        build_memory_context_bundle_mock.return_value = SimpleNamespace(
            capability="conversation_free_chat",
            hot_summary=SimpleNamespace(
                preference_highlights=[],
                recent_event_highlights=[],
                total_visible_cards=0,
                top_memories=[],
            ),
            recall=SimpleNamespace(
                session_summary=[],
                stable_facts=[],
                recent_events=[],
                external_knowledge=[],
                degraded=False,
                degrade_reasons=[],
            ),
            query_result=SimpleNamespace(total=0, items=[]),
        )

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
            user_message="朵朵多大了",
        )

        self.assertIn("家庭成员档案", variables["household_context"])
        self.assertIn("朵朵", variables["household_context"])
        self.assertIn("年龄=", variables["household_context"])
        self.assertIn("监护人=Owner", variables["household_context"])
        self.assertIn("关系=对Owner是女儿", variables["household_context"])
        self.assertIn("当前实时信息", variables["household_context"])
        self.assertIn(
            f"今天日期：{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')}",
            variables["household_context"],
        )
        self.assertIn("当前本地时间：", variables["household_context"])
        self.assertIn("星期：", variables["household_context"])
        self.assertIn("当前时区：Asia/Shanghai", variables["household_context"])

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
                reason="鐢ㄦ埛鍦ㄩ棶瀹跺涵鐘舵€併€",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="鐜板湪瀹堕噷鏄粈涔堢姸鎬侊紵")
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
                reason="鐢ㄦ埛鏄庣‘鎯虫敼鍔╂墜鍚嶅瓧鍜岃璇濋鏍笺€",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="浠ュ悗浣犲氨鍙樋绂忥紝璇磋瘽椋庢牸娓╂煍涓€鐐")
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
                reason="杩欐槸鍦ㄩ棶鍔╂墜鍚嶅瓧锛屼笉鏄湪鏀归厤缃€",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="浣犲彨浠€涔")
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
                reason="鍙兘鍍忔槸鍦ㄦ敼閰嶇疆锛屼絾涓嶅鏄庣‘銆",
                candidate_actions=[],
            )
        )
        intent = detect_conversation_intent(self.db, session=session, message="浣犺寰楅樋绂忚繖涓悕瀛楁€庝箞鏍")
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
        intent = detect_conversation_intent(self.db, session=session, message="浣犲彨浠€涔")
        self.assertEqual(ConversationIntentLabel.CONFIG_CHANGE, intent.primary_intent)
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, intent.route_intent)
        self.assertEqual("session_mode.agent_config", intent.guardrail_rule)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_routes_reminder_intent_to_extraction(self, invoke_llm_mock) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = False
        try:
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
                        reason="鐢ㄦ埛鏄庣‘瑕佹眰鍒涘缓鎻愰啋銆",
                        candidate_actions=[],
                    )
                ),
                _FakeLlmResult(
                    data=ReminderExtractionOutput(
                        should_create=True,
                        title="甯﹂挜鍖",
                        description="鍑洪棬鍓嶆鏌ラ挜鍖",
                        trigger_at="2026-03-14T08:00:00+08:00",
                    )
                ),
            ]
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鏄庡ぉ鏃╀笂鍏偣鎻愰啋鎴戝甫閽ュ寵",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover
        self.assertEqual(ConversationIntent.REMINDER_EXTRACTION, result.intent)
        self.assertEqual(ConversationIntentLabel.REMINDER_CREATE, result.intent_detection.primary_intent)
        self.assertEqual(1, len(result.action_payloads))
        self.assertEqual("reminder_create", result.action_payloads[0]["action_type"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_uses_natural_reply_for_config_change(self, invoke_llm_mock) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = False
        try:
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
                        reason="鐢ㄦ埛鏄庣‘鎯崇粰鍔╂墜鏀瑰悕銆",
                        candidate_actions=[],
                    )
                ),
                _FakeLlmResult(
                    data=type(
                        "_ConfigDraft",
                        (),
                        {
                            "display_name": "闃跨",
                            "speaking_style": None,
                            "personality_traits": [],
                        },
                    )()
                ),
            ]
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="浠ュ悗浣犲氨鍙樋绂",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("濂斤紝閭ｆ垜浠ュ悗灏卞彨闃跨銆備綘杩樻兂椤烘墜璋冩暣涓€涓嬫垜璇磋瘽鐨勯鏍硷紝鎴栬€呰ˉ鍑犱釜鎬ф牸鏍囩鍚楋紵", result.text)
        self.assertEqual("闃跨", result.config_suggestion["display_name"])
        self.assertEqual([], invoke_llm_mock.call_args_list[1].kwargs["conversation_history"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_passes_recent_history_to_config_extraction(self, invoke_llm_mock) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = False
        try:
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
                        reason="鐢ㄦ埛鍦ㄧ户缁ˉ鍏呭姪鎵嬪悕瀛椼€",
                        candidate_actions=[],
                    )
                ),
                _FakeLlmResult(
                    data=type(
                        "_ConfigDraft",
                        (),
                        {
                            "display_name": "鏆栨殩",
                            "speaking_style": None,
                            "personality_traits": [],
                        },
                    )()
                ),
            ]
            history = [
                {"role": "user", "content": "缁欎綘鏀逛釜鍚嶅瓧濂戒笉濂"},
                {"role": "assistant", "content": "褰撶劧鍙互锛屼綘鎯崇粰鎴戣捣浠€涔堟柊鍚嶅瓧锛"},
            ]
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鍙殩鏆栧惂",
                actor=self.actor,
                conversation_history=history,
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("鏆栨殩", result.config_suggestion["display_name"])
        self.assertEqual("濂斤紝閭ｆ垜浠ュ悗灏卞彨鏆栨殩銆備綘杩樻兂椤烘墜璋冩暣涓€涓嬫垜璇磋瘽鐨勯鏍硷紝鎴栬€呰ˉ鍑犱釜鎬ф牸鏍囩鍚楋紵", result.text)
        self.assertEqual(history, invoke_llm_mock.call_args_list[1].kwargs["conversation_history"])

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_does_not_extract_current_name_as_new_config(self, invoke_llm_mock) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = False
        try:
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
                        reason="鐢ㄦ埛鎯宠璁烘敼鍚嶃€",
                        candidate_actions=[],
                    )
                ),
                _FakeLlmResult(
                    data=type(
                        "_ConfigDraft",
                        (),
                        {
                            "display_name": self.agent.display_name,
                            "speaking_style": "骞介粯椋庤叮",
                            "personality_traits": ["缁嗗績", "涔愪簬鍔╀汉"],
                        },
                    )()
                ),
                _FakeLlmResult(text="褰撶劧鍙互锛屼綘鎯崇粰鎴戣捣浠€涔堟柊鍚嶅瓧锛熶篃鍙互椤烘墜鍛婅瘔鎴戞兂鎹㈡垚浠€涔堣璇濋鏍笺€"),
            ]
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鎴戠粰浣犳敼涓悕鎬庝箞鏍",
                actor=self.actor,
                conversation_history=[
                    {"role": "assistant", "content": f"你好，我是{self.agent.display_name}。"}
                ],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover
        self.assertEqual(ConversationIntent.CONFIG_EXTRACTION, result.intent)
        self.assertEqual("褰撶劧鍙互锛屼綘鎯崇粰鎴戣捣浠€涔堟柊鍚嶅瓧锛熶篃鍙互椤烘墜鍛婅瘔鎴戞兂鎹㈡垚浠€涔堣璇濋鏍笺€", result.text)
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
                    reason="鍙槸闅忓彛鑱婂悕瀛楋紝涓嶅鍍忛厤缃慨鏀广€",
                    candidate_actions=[],
                )
            ),
            _FakeLlmResult(text="鎴戠幇鍦ㄥ彨绗ㄧ锛屼綘鎯崇粰鎴戣捣鏂板悕瀛椾篃鍙互銆"),
        ]
        result = run_orchestrated_turn(
            self.db,
            session=session,
            message="浣犲彨浠€涔",
            actor=self.actor,
            conversation_history=[],
        )
        self.assertEqual(ConversationIntent.FREE_CHAT, result.intent)
        self.assertIsNone(result.config_suggestion)
        self.assertEqual("鎴戠幇鍦ㄥ彨绗ㄧ锛屼綘鎯崇粰鎴戣捣鏂板悕瀛椾篃鍙互銆", result.text)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_with_lane_takeover_routes_config_change_to_free_chat(self, invoke_llm_mock) -> None:
        previous_value = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
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
                        reason="鐢ㄦ埛鏄庣‘鎯崇粰鍔╂墜鏀瑰悕銆",
                        candidate_actions=[],
                    )
                ),
                _FakeLlmResult(text="濂界殑锛屾垜浠厛鎸夎亰澶╃户缁€備綘鎯宠鎴戞敼鎴愪粈涔堝悕瀛楋紵"),
            ]
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="浠ュ悗浣犲氨鍙樋绂",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_value

        self.assertEqual(ConversationIntent.FREE_CHAT, result.intent)
        self.assertEqual("free_chat", result.lane_selection.lane.value)
        self.assertIsNone(result.config_suggestion)
        self.assertEqual("濂界殑锛屾垜浠厛鎸夎亰澶╃户缁€備綘鎯宠鎴戞敼鎴愪粈涔堝悕瀛楋紵", result.text)

    @patch("app.modules.conversation.orchestrator.query_family_qa")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_with_lane_takeover_keeps_structured_qa_in_realtime_query(self, invoke_llm_mock, query_family_qa_mock) -> None:
        previous_value = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
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
                    secondary_intents=[],
                    confidence=0.95,
                    reason="鐢ㄦ埛鍦ㄦ煡瀹跺涵鐘舵€併€",
                    candidate_actions=[],
                )
            )
            query_family_qa_mock.return_value = SimpleNamespace(
                answer="鐜板湪瀹堕噷鏈変汉銆",
                degraded=False,
                ai_degraded=False,
                facts=[],
                suggestions=[],
                ai_trace_id=None,
                ai_provider_code="qa-mock",
                effective_agent_id=self.agent.id,
                effective_agent_name=self.agent.display_name,
            )
            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鐜板湪瀹堕噷鏈変汉鍚",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_value

        self.assertEqual(ConversationIntent.STRUCTURED_QA, result.intent)
        self.assertEqual("realtime_query", result.lane_selection.lane.value)

    @patch("app.modules.conversation.orchestrator.query_family_qa")
    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_with_lane_takeover_routes_free_chat_intent_to_realtime_query(
        self,
        invoke_llm_mock,
        select_lane_mock,
        query_family_qa_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
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
                    confidence=0.62,
                    reason="鏃ф剰鍥捐瘑鍒厛鎸?free_chat 鍏滃簳銆",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.REALTIME_QUERY,
                confidence=0.89,
                reason="璇箟璺敱鍛戒腑鐘舵€佹煡璇㈣溅閬撱€",
                target_kind="state_query",
                requires_clarification=False,
                source="intent_mapping",
            )
            query_family_qa_mock.return_value = SimpleNamespace(
                answer="鐜板湪瀹堕噷鏈変汉銆",
                degraded=False,
                ai_degraded=False,
                facts=[],
                suggestions=[],
                ai_trace_id=None,
                ai_provider_code="qa-mock",
                effective_agent_id=self.agent.id,
                effective_agent_name=self.agent.display_name,
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鐜板湪瀹堕噷鏈変汉鍚",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.STRUCTURED_QA, result.intent)
        self.assertEqual("realtime_query", result.lane_selection.lane.value)
        self.assertEqual("鐜板湪瀹堕噷鏈変汉銆", result.text)
        query_family_qa_mock.assert_called_once()

    @patch("app.modules.conversation.orchestrator.query_family_qa")
    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_with_lane_takeover_keeps_realtime_query_out_of_free_chat_path(
        self,
        invoke_llm_mock,
        select_lane_mock,
        query_family_qa_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
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
                    confidence=0.51,
                    reason="鏃ф剰鍥捐瘑鍒棤娉曠ǔ瀹氬垽鏂€",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.REALTIME_QUERY,
                confidence=0.84,
                reason="璇箟璺敱鍛戒腑瀹炴椂鍙栨暟銆",
                target_kind="state_query",
                requires_clarification=False,
                source="intent_mapping",
            )
            query_family_qa_mock.return_value = SimpleNamespace(
                answer="瀹㈠巺娓╁害鏄?24 搴︺€",
                degraded=False,
                ai_degraded=False,
                facts=[],
                suggestions=[],
                ai_trace_id=None,
                ai_provider_code="qa-mock",
                effective_agent_id=self.agent.id,
                effective_agent_name=self.agent.display_name,
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="瀹㈠巺娓╁害澶氬皯",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.STRUCTURED_QA, result.intent)
        self.assertEqual("瀹㈠巺娓╁害鏄?24 搴︺€", result.text)
        self.assertIsNone(result.config_suggestion)
        self.assertEqual([], result.memory_candidate_payloads)

    @patch("app.modules.conversation.orchestrator.execute_device_action")
    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_fast_action_executes_device_control(
        self,
        invoke_llm_mock,
        select_lane_mock,
        execute_device_action_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
            session = create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(
                    household_id=self.household.id,
                    active_agent_id=self.agent.id,
                ),
                actor=self.actor,
            )
            device = Device(
                id=new_uuid(),
                household_id=self.household.id,
                room_id=None,
                name="瀹㈠巺鐏",
                device_type="light",
                vendor="ha",
                status="active",
                controllable=1,
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            self.db.add(device)
            self.db.commit()
            invoke_llm_mock.return_value = _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.7,
                    reason="鍏堟寜鏅€氳亰澶╁厹搴曘€",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.FAST_ACTION,
                confidence=0.9,
                reason="鍛戒腑璁惧鎺у埗杞﹂亾銆",
                target_kind="device_action",
                requires_clarification=False,
                source="test",
            )
            execute_device_action_mock.return_value = (
                SimpleNamespace(
                    device=SimpleNamespace(name="瀹㈠巺鐏"),
                    action="turn_off",
                    model_dump=lambda mode="json": {
                        "device": {"name": "瀹㈠巺鐏"},
                        "action": "turn_off",
                        "result": "success",
                    },
                ),
                SimpleNamespace(details={}),
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鎶婂鍘呯伅鍏虫帀",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual("fast_action", result.lane_selection.lane.value)
        self.assertEqual("宸蹭负浣犲叧闂鍘呯伅銆", result.text)
        self.assertEqual("fast_action_receipt", result.facts[0]["type"])
        execute_device_action_mock.assert_called_once()

    @patch("app.modules.conversation.orchestrator.execute_device_action")
    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_fast_action_hides_raw_http_exception_payload(
        self,
        invoke_llm_mock,
        select_lane_mock,
        execute_device_action_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
            session = create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(
                    household_id=self.household.id,
                    active_agent_id=self.agent.id,
                ),
                actor=self.actor,
            )
            device = Device(
                id=new_uuid(),
                household_id=self.household.id,
                room_id=None,
                name="客厅灯",
                device_type="light",
                vendor="ha",
                status="active",
                controllable=1,
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            self.db.add(device)
            self.db.commit()
            invoke_llm_mock.return_value = _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.7,
                    reason="先按普通聊天兜底。",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.FAST_ACTION,
                confidence=0.9,
                reason="命中设备控制车道。",
                target_kind="device_action",
                requires_clarification=False,
                source="test",
            )
            execute_device_action_mock.side_effect = HTTPException(
                status_code=503,
                detail={
                    "detail": "device platform is unreachable",
                    "error_code": "platform_unreachable",
                    "timestamp": "2026-03-17T09:30:28.435865Z",
                },
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="把客厅灯打开",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertEqual(
            "我知道你想立刻控制设备，但这次执行失败了：设备平台暂时不可达，设备本身可能在线，请稍后再试。",
            result.text,
        )
        self.assertNotIn("503", result.text)
        self.assertNotIn("platform_unreachable", result.text)
        self.assertNotIn("{", result.text)

    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_fast_action_asks_for_clarification_when_target_ambiguous(
        self,
        invoke_llm_mock,
        select_lane_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
            session = create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(
                    household_id=self.household.id,
                    active_agent_id=self.agent.id,
                ),
                actor=self.actor,
            )
            for device_name in ("瀹㈠巺鐏", "鍗у鐏"):
                self.db.add(
                    Device(
                        id=new_uuid(),
                        household_id=self.household.id,
                        room_id=None,
                        name=device_name,
                        device_type="light",
                        vendor="ha",
                        status="active",
                        controllable=1,
                        created_at=utc_now_iso(),
                        updated_at=utc_now_iso(),
                    )
                )
            self.db.commit()
            invoke_llm_mock.return_value = _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.7,
                    reason="鍏堟寜鏅€氳亰澶╁厹搴曘€",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.FAST_ACTION,
                confidence=0.9,
                reason="鍛戒腑璁惧鎺у埗杞﹂亾銆",
                target_kind="device_action",
                requires_clarification=False,
                source="test",
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鎶婄伅鍏虫帀",
                actor=self.actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertIn("澶氫釜鍙兘鐨勮澶", result.text)
        self.assertCountEqual(["鍗у鐏", "瀹㈠巺鐏"], result.suggestions)

    @patch("app.modules.conversation.orchestrator.select_conversation_lane")
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_run_orchestrated_turn_fast_action_rejects_non_admin_actor(
        self,
        invoke_llm_mock,
        select_lane_mock,
    ) -> None:
        previous_takeover = settings.conversation_lane_takeover_enabled
        settings.conversation_lane_takeover_enabled = True
        try:
            viewer_actor = ActorContext(
                role="member",
                actor_type="member",
                actor_id=self.member.id,
                account_id="account-1",
                account_type="household",
                account_status="active",
                username="viewer",
                household_id=self.household.id,
                member_id=self.member.id,
                member_role="member",
                is_authenticated=True,
            )
            session = create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(
                    household_id=self.household.id,
                    active_agent_id=self.agent.id,
                ),
                actor=self.actor,
            )
            self.db.add(
                Device(
                    id=new_uuid(),
                    household_id=self.household.id,
                    room_id=None,
                    name="瀹㈠巺鐏",
                    device_type="light",
                    vendor="ha",
                    status="active",
                    controllable=1,
                    created_at=utc_now_iso(),
                    updated_at=utc_now_iso(),
                )
            )
            self.db.commit()
            invoke_llm_mock.return_value = _FakeLlmResult(
                data=ConversationIntentDetectionOutput(
                    primary_intent="free_chat",
                    secondary_intents=[],
                    confidence=0.7,
                    reason="鍏堟寜鏅€氳亰澶╁厹搴曘€",
                    candidate_actions=[],
                )
            )
            select_lane_mock.return_value = ConversationLaneSelection(
                lane=ConversationLane.FAST_ACTION,
                confidence=0.9,
                reason="鍛戒腑璁惧鎺у埗杞﹂亾銆",
                target_kind="device_action",
                requires_clarification=False,
                source="test",
            )

            result = run_orchestrated_turn(
                self.db,
                session=session,
                message="鎶婂鍘呯伅鍏虫帀",
                actor=viewer_actor,
                conversation_history=[],
            )
        finally:
            settings.conversation_lane_takeover_enabled = previous_takeover

        self.assertEqual(ConversationIntent.FAST_ACTION, result.intent)
        self.assertIn("娌℃湁璁惧蹇帶鏉冮檺", result.text)

    @patch("app.modules.conversation.orchestrator.invoke_llm")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_conversation_turn_routes_config_intent_without_family_qa(self, run_orchestrated_turn_mock, invoke_llm_mock) -> None:
        _ = invoke_llm_mock
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.CONFIG_EXTRACTION,
            text="鎴戝凡缁忔妸杩欒疆琛ㄨ揪鏁寸悊鎴?Agent 閰嶇疆寤鸿锛歕n- 鍚嶇О寤鸿锛氶樋绂",
            degraded=False,
            facts=[{"type": "config_suggestion", "label": "Agent 閰嶇疆寤鸿", "source": "conversation_orchestrator", "extra": {"display_name": "闃跨"}}],
            suggestions=["鍘?AI 閰嶇疆"],
            memory_candidate_payloads=[],
            config_suggestion={"display_name": "闃跨"},
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
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
            payload=ConversationTurnCreate(message="浠ュ悗浣犲氨鍙樋绂"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertIn("Agent 閰嶇疆寤鸿", result.session.messages[1].content)

    @patch("app.modules.conversation.service.invoke_llm")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_memory_intent_handler_persists_candidates_directly(self, run_orchestrated_turn_mock, invoke_llm_mock) -> None:
        _ = invoke_llm_mock
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="鎴戝凡缁忎粠杩欒疆鍐呭閲屾暣鐞嗗嚭璁板繂鍊欓€夛紝鍙充晶鍙互鐩存帴纭鍐欏叆銆",
            degraded=False,
            facts=[],
            suggestions=["纭鍐欏叆璁板繂"],
            memory_candidate_payloads=[
                {
                    "memory_type": "preference",
                    "title": "delayed memory",
                    "summary": "鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆",
                    "content": {"source": "conversation"},
                    "confidence": 0.92,
                }
            ],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
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
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜delayed memory"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.outcome)
        self.assertEqual(1, len(result.session.proposal_batches))
        self.assertEqual(1, len(result.session.proposal_batches[0].items))
        self.assertEqual("memory_write", result.session.proposal_batches[0].items[0].proposal_kind)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_legacy_notify_config_proposal_applies_agent_update_without_confirmation(self, run_orchestrated_turn_mock) -> None:
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
            text="鎴戝凡缁忔暣鐞嗗ソ浜嗛厤缃缓璁€",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[],
            config_suggestion={
                "display_name": "闃跨",
                "role_summary": "负责家庭问答和提醒",
                "intro_message": "以后我来继续帮你盯着家里的安排。",
                "speaking_style": "娓╁拰鐩存帴",
                "personality_traits": ["绋抽噸"],
                "service_focus": ["家庭问答", "日程提醒"],
            },
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="浠ュ悗浣犲氨鍙樋绂忥紝璇磋瘽娓╁拰鐩存帴涓€鐐"),
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual(1, len(turn.session.proposal_batches))
        item = turn.session.proposal_batches[0].items[0]
        self.assertEqual("config_apply", item.proposal_kind)
        self.assertEqual("notify", item.policy_category)
        self.assertEqual("completed", item.status)
        self.assertEqual("闃跨", get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor).active_agent_name)
        agent_detail = get_agent_detail(self.db, household_id=self.household.id, agent_id=self.agent.id)
        assert agent_detail.soul is not None
        self.assertEqual("负责家庭问答和提醒", agent_detail.soul.role_summary)
        self.assertEqual("以后我来继续帮你盯着家里的安排。", agent_detail.soul.intro_message)
        self.assertEqual("娓╁拰鐩存帴", agent_detail.soul.speaking_style)
        self.assertEqual(["绋抽噸"], agent_detail.soul.personality_traits)
        self.assertEqual(["家庭问答", "日程提醒"], agent_detail.soul.service_focus)

    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_confirm_pending_memory_proposal_creates_memory(self, run_orchestrated_turn_mock) -> None:
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.MEMORY_EXTRACTION,
            text="鎴戝凡缁忔暣鐞嗗嚭浜嗚蹇嗗€欓€夈€",
            degraded=False,
            facts=[],
            suggestions=[],
            memory_candidate_payloads=[
                {
                    "memory_type": "preference",
                    "title": "delayed memory",
                    "summary": "鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆",
                    "content": {"source": "conversation"},
                    "confidence": 0.92,
                }
            ],
            config_suggestion=None,
            action_payloads=[],
            ai_trace_id=None,
            ai_provider_code="mock-provider",
            effective_agent_id=self.agent.id,
            effective_agent_name="绗ㄧ",
        )
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜delayed memory"),
            actor=self.actor,
        )
        self.db.commit()
        item = turn.session.proposal_batches[0].items[0]
        execution = confirm_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.actor)
        self.db.commit()

        self.assertEqual("completed", execution.item.status)
        self.assertEqual("memory_write", execution.item.proposal_kind)
        memory_card_id = execution.affected_target_id
        self.assertTrue(isinstance(memory_card_id, str) and memory_card_id)

    def test_confirm_conversation_proposal_creates_memory_card(self) -> None:
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
            content="鎴戣浣忎簡锛屼綘delayed memory銆",
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
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-memory",
            source_message_ids_json=dump_json([assistant_message.id]) or "[]",
            source_roles_json=dump_json(["assistant"]) or "[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_confirmation",
            title="delayed memory",
            summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁delayed memory銆",
            evidence_message_ids_json=dump_json([assistant_message.id]) or "[]",
            evidence_roles_json=dump_json(["assistant"]) or "[]",
            dedupe_key="memory:manual:diet",
            confidence=0.91,
            payload_json=dump_json({"memory_type": "preference", "source": "conversation", "tag": "diet"}) or "{}",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.commit()

        result = confirm_conversation_proposal(
            self.db,
            proposal_item_id=item.id,
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("completed", result.item.status)
        self.assertIsNotNone(result.affected_target_id)
        created_memory = memory_repository.get_memory_card(self.db, result.affected_target_id)
        self.assertIsNotNone(created_memory)
        assert created_memory is not None
        self.assertEqual("preference", created_memory.memory_type)
        self.assertEqual("delayed memory", created_memory.title)

    def test_confirm_conversation_proposal_uses_subject_member_and_effective_at_from_payload(self) -> None:
        child = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="朵朵", role="child"),
        )
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
            request_id="request-growth-memory",
            seq=conversation_repository.get_next_message_seq(self.db, session_id=session.id),
            role="assistant",
            message_type="text",
            content="我记下朵朵第一次会走路了。",
            status="completed",
            effective_agent_id=self.agent.id,
            ai_provider_code="mock-provider",
            ai_trace_id="trace-growth-memory",
            degraded=False,
            error_code=None,
            facts_json=dump_json([]),
            suggestions_json=dump_json([]),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_message(self.db, assistant_message)
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-growth-memory",
            source_message_ids_json=dump_json([assistant_message.id]) or "[]",
            source_roles_json=dump_json(["assistant"]) or "[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_confirmation",
            title="朵朵第一次会走路",
            summary="朵朵第一次会走路（2026-03-18）",
            evidence_message_ids_json=dump_json([assistant_message.id]) or "[]",
            evidence_roles_json=dump_json(["assistant"]) or "[]",
            dedupe_key="memory:growth:dodo:first-walk",
            confidence=0.95,
            payload_json=dump_json(
                {
                    "memory_type": "growth",
                    "subject_member_id": child.id,
                    "subject_name": "朵朵",
                    "milestone": "第一次会走路",
                    "effective_at": "2026-03-18T00:00:00+08:00",
                    "related_members": [{"member_id": self.member.id, "relation_role": "owner"}],
                }
            )
            or "{}",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.commit()

        result = confirm_conversation_proposal(
            self.db,
            proposal_item_id=item.id,
            actor=self.actor,
        )
        self.db.commit()

        created_memory = memory_repository.get_memory_card(self.db, result.affected_target_id)
        self.assertIsNotNone(created_memory)
        assert created_memory is not None
        self.assertEqual("growth", created_memory.memory_type)
        self.assertEqual(child.id, created_memory.subject_member_id)
        self.assertEqual("2026-03-18T00:00:00+08:00", created_memory.effective_at)
        self.assertEqual(1, len(created_memory.related_members))
        self.assertEqual(self.member.id, created_memory.related_members[0].member_id)

    def test_dismiss_conversation_proposal_marks_item_dismissed(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.flush()

        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session.id,
            request_id="request-dismiss",
            source_message_ids_json="[]",
            source_roles_json="[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_confirmation",
            title="寰呭拷鐣ュ€欓€",
            summary="杩欐潯鍊欓€夊簲璇ヨ蹇界暐銆",
            evidence_message_ids_json="[]",
            evidence_roles_json="[]",
            dedupe_key="memory:dismiss:test",
            confidence=0.51,
            payload_json=dump_json({"memory_type": "fact", "source": "conversation"}) or "{}",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.commit()

        result = dismiss_conversation_proposal(
            self.db,
            proposal_item_id=item.id,
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual("dismissed", result.item.status)
        self.assertIsNone(result.affected_target_id)


if __name__ == "__main__":
    unittest.main()

