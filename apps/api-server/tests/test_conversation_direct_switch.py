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
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalBatch, ConversationProposalItem, ConversationSession
from app.modules.conversation.orchestrator import ConversationIntent, ConversationOrchestratorResult
from app.modules.conversation.proposal_analyzers import ProposalDraft
from app.modules.conversation.proposal_pipeline import ProposalPipelineResult
from app.modules.conversation.schemas import ConversationSessionCreate, ConversationTurnCreate
from app.modules.conversation.service import (
    confirm_conversation_proposal,
    create_conversation_session,
    create_conversation_turn,
    dismiss_conversation_proposal,
    get_conversation_session_detail,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.memory import repository as memory_repository
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationDirectSwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_takeover = settings.conversation_lane_takeover_enabled
        self._previous_write_enabled = settings.conversation_proposal_write_enabled

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Direct Switch Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
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
        settings.conversation_lane_takeover_enabled = self._previous_takeover
        settings.conversation_proposal_write_enabled = self._previous_write_enabled
        self._tempdir.cleanup()

    def test_session_detail_reads_proposal_batches(self) -> None:
        session = self._create_session()
        batch, item = self._create_memory_proposal(session=session)

        detail = get_conversation_session_detail(self.db, session_id=session.id, actor=self.actor)

        self.assertEqual(1, len(detail.proposal_batches))
        self.assertEqual(batch.id, detail.proposal_batches[0].id)
        self.assertEqual(item.id, detail.proposal_batches[0].items[0].id)
        self.assertFalse(hasattr(detail, "memory_candidates"))
        self.assertFalse(hasattr(detail, "action_records"))

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn")
    @patch("app.modules.conversation.service._run_orchestrated_turn")
    def test_create_turn_returns_new_proposal_model(
        self,
        run_orchestrated_turn_mock,
        proposal_pipeline_mock,
    ) -> None:
        session = self._create_session()
        run_orchestrated_turn_mock.return_value = ConversationOrchestratorResult(
            intent=ConversationIntent.FREE_CHAT,
            text="濂界殑锛屾垜鍏堣涓嬭繖浠朵簨銆?,
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
        )

        def _persist(*args, **kwargs):
            user_message = kwargs["user_message"]
            created_batch = ConversationProposalBatch(
                id=new_uuid(),
                session_id=session.id,
                request_id=kwargs["request_id"],
                source_message_ids_json=dump_json([user_message.id]) or "[]",
                source_roles_json=dump_json(["user"]) or "[]",
                lane_json='{"lane":"free_chat"}',
                status="pending_confirmation",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            conversation_repository.add_proposal_batch(self.db, created_batch)
            created_item = ConversationProposalItem(
                id=new_uuid(),
                batch_id=created_batch.id,
                proposal_kind="memory_write",
                policy_category="ask",
                status="pending_confirmation",
                title="涓嶅悆棣欒彍",
                summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁涓嶅悆棣欒彍銆?,
                evidence_message_ids_json=dump_json([user_message.id]) or "[]",
                evidence_roles_json=dump_json(["user"]) or "[]",
                dedupe_key="memory:test:diet",
                confidence=0.93,
                payload_json=dump_json({"memory_type": "preference", "summary": "鐢ㄦ埛涓嶅悆棣欒彍"}) or "{}",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
            conversation_repository.add_proposal_item(self.db, created_item)
            self.db.flush()
            return ProposalPipelineResult(
                batch_id=created_batch.id,
                item_ids=[created_item.id],
                drafts=[
                    ProposalDraft(
                        proposal_kind="memory_write",
                        policy_category="ask",
                        title="涓嶅悆棣欒彍",
                        summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁涓嶅悆棣欒彍銆?,
                        evidence_message_ids=[user_message.id],
                        evidence_roles=["user"],
                        dedupe_key="memory:test:diet",
                        confidence=0.93,
                        payload={"memory_type": "preference", "summary": "鐢ㄦ埛涓嶅悆棣欒彍"},
                    )
                ],
                failures=[],
                extraction_output=None,
            )

        proposal_pipeline_mock.side_effect = _persist

        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="璁颁綇锛屾垜涓嶅悆棣欒彍"),
            actor=self.actor,
        )

        self.assertEqual("completed", turn.outcome)
        self.assertEqual(1, len(turn.session.proposal_batches))
        self.assertEqual("memory_write", turn.session.proposal_batches[0].items[0].proposal_kind)

    def test_confirm_conversation_proposal_creates_memory_card(self) -> None:
        session = self._create_session()
        batch, item = self._create_memory_proposal(session=session)

        result = confirm_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.actor)
        self.db.commit()

        self.assertEqual("completed", result.item.status)
        self.assertIsNotNone(result.affected_target_id)
        memory_card = memory_repository.get_memory_card(self.db, result.affected_target_id)
        self.assertIsNotNone(memory_card)
        assert memory_card is not None
        self.assertEqual("涓嶅悆棣欒彍", memory_card.title)
        refreshed_batch = conversation_repository.get_proposal_batch(self.db, batch.id)
        self.assertEqual("completed", refreshed_batch.status)

    def test_dismiss_conversation_proposal_marks_item_dismissed(self) -> None:
        session = self._create_session()
        batch, item = self._create_memory_proposal(session=session)

        result = dismiss_conversation_proposal(self.db, proposal_item_id=item.id, actor=self.actor)
        self.db.commit()

        self.assertEqual("dismissed", result.item.status)
        refreshed_batch = conversation_repository.get_proposal_batch(self.db, batch.id)
        self.assertEqual("ignored", refreshed_batch.status)

    def _create_session(self) -> ConversationSession:
        detail = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(household_id=self.household.id, active_agent_id=self.agent.id),
            actor=self.actor,
        )
        session = conversation_repository.get_session(self.db, detail.id)
        assert session is not None
        return session

    def _create_memory_proposal(self, *, session: ConversationSession) -> tuple[ConversationProposalBatch, ConversationProposalItem]:
        now = utc_now_iso()
        user_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="req-memory",
            seq=1,
            role="user",
            message_type="text",
            content="璁颁綇锛屾垜涓嶅悆棣欒彍",
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
        conversation_repository.add_message(self.db, user_message)
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session.id,
            request_id="req-memory",
            source_message_ids_json=dump_json([user_message.id]) or "[]",
            source_roles_json=dump_json(["user"]) or "[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_confirmation",
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_confirmation",
            title="涓嶅悆棣欒彍",
            summary="鐢ㄦ埛鏄庣‘琛ㄧず鑷繁涓嶅悆棣欒彍銆?,
            evidence_message_ids_json=dump_json([user_message.id]) or "[]",
            evidence_roles_json=dump_json(["user"]) or "[]",
            dedupe_key="memory:switch:diet",
            confidence=0.95,
            payload_json=dump_json({"memory_type": "preference", "summary": "鐢ㄦ埛涓嶅悆棣欒彍"}) or "{}",
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.commit()
        return batch, item


if __name__ == "__main__":
    unittest.main()

