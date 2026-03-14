import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalBatch, ConversationProposalItem, ConversationSession
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationProposalRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.db_path = Path(self._tempdir.name) / "test.db"
        self.database_url = f"sqlite:///{self.db_path}"
        settings.database_url = self.database_url

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        alembic_config.set_main_option("sqlalchemy.url", self.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(self.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Proposal Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        now = utc_now_iso()
        self.session = ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=None,
            current_request_id="req-1",
            last_event_seq=0,
            title="提案测试",
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_session(self.db, self.session)
        self.user_message = ConversationMessage(
            id=new_uuid(),
            session_id=self.session.id,
            request_id="req-1",
            seq=1,
            role="user",
            message_type="text",
            content="明天早上八点提醒我开会",
            status="completed",
            effective_agent_id=None,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json=None,
            suggestions_json=None,
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_message(self.db, self.user_message)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_repository_can_create_proposal_batch_and_items(self) -> None:
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=self.session.id,
            request_id="req-1",
            source_message_ids_json='["%s"]' % self.user_message.id,
            source_roles_json='["user"]',
            lane_json='{"lane":"free_chat","target_kind":"none"}',
            status="pending_policy",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, batch)

        memory_item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="memory_write",
            policy_category="ask",
            status="pending_policy",
            title="记住用户对会议提醒敏感",
            summary="用户提到明天早上八点要开会。",
            evidence_message_ids_json='["%s"]' % self.user_message.id,
            evidence_roles_json='["user"]',
            dedupe_key="memory:req-1:meeting",
            confidence=0.82,
            payload_json='{"kind":"memory_write","fact":"明天早上八点开会"}',
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        reminder_item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="reminder_create",
            policy_category="ask",
            status="pending_policy",
            title="提醒草稿",
            summary="明天早上八点提醒开会。",
            evidence_message_ids_json='["%s"]' % self.user_message.id,
            evidence_roles_json='["user"]',
            dedupe_key="reminder:req-1:meeting",
            confidence=0.96,
            payload_json='{"kind":"reminder_create","title":"开会","trigger_at":"2026-03-15T08:00:00+08:00"}',
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_item(self.db, memory_item)
        conversation_repository.add_proposal_item(self.db, reminder_item)
        self.db.commit()

        stored_batch = conversation_repository.get_proposal_batch(self.db, batch.id)
        stored_items = conversation_repository.list_proposal_items(self.db, batch_id=batch.id)

        self.assertIsNotNone(stored_batch)
        self.assertEqual("req-1", stored_batch.request_id)
        self.assertEqual("pending_policy", stored_batch.status)
        self.assertEqual(2, len(stored_items))
        self.assertEqual(
            {"memory_write", "reminder_create"},
            {item.proposal_kind for item in stored_items},
        )
        memory_item = next(item for item in stored_items if item.proposal_kind == "memory_write")
        self.assertEqual("memory:req-1:meeting", memory_item.dedupe_key)
        self.assertEqual('["user"]', memory_item.evidence_roles_json)

    def test_repository_can_query_batches_by_request_and_status(self) -> None:
        pending_batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=self.session.id,
            request_id="req-1",
            source_message_ids_json='["%s"]' % self.user_message.id,
            source_roles_json='["user"]',
            lane_json='{"lane":"free_chat"}',
            status="pending_policy",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        completed_batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=self.session.id,
            request_id="req-2",
            source_message_ids_json='["%s"]' % self.user_message.id,
            source_roles_json='["user"]',
            lane_json='{"lane":"free_chat"}',
            status="completed",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        conversation_repository.add_proposal_batch(self.db, pending_batch)
        conversation_repository.add_proposal_batch(self.db, completed_batch)
        self.db.commit()

        by_request = conversation_repository.get_proposal_batch_by_request(
            self.db,
            session_id=self.session.id,
            request_id="req-2",
        )
        pending_batches = conversation_repository.list_proposal_batches(
            self.db,
            session_id=self.session.id,
            status="pending_policy",
        )

        self.assertIsNotNone(by_request)
        self.assertEqual(completed_batch.id, by_request.id)
        self.assertEqual(1, len(pending_batches))
        self.assertEqual(pending_batch.id, pending_batches[0].id)


if __name__ == "__main__":
    unittest.main()
