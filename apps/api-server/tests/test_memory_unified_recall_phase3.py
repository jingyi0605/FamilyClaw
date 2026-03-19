import unittest
from unittest.mock import patch

import app.db.models  # noqa: F401
from fastapi import HTTPException
from sqlalchemy import select, text

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
from app.modules.memory.models import (
    EpisodicMemoryEntry,
    EpisodicMemoryEntryRevision,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    MemoryRecallDocument,
)
from app.modules.memory.recall_document_service import build_memory_recall_bundle
from app.modules.memory.schemas import EventRecordCreate, MemoryCardManualCreate
from app.modules.memory.service import (
    create_manual_memory_card,
    ingest_event_record,
    upsert_knowledge_document,
    upsert_knowledge_document_from_observation,
)
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import execute_plugin, run_plugin_sync_pipeline, save_plugin_raw_records


class _FakeLlmResult:
    def __init__(self, *, text: str = "", data=None, provider: str = "mock-provider") -> None:
        self.text = text
        self.data = data
        self.provider = provider


class MemoryUnifiedRecallPhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()
        self.builtin_root = __import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Phase3 Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
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

    def test_migration_creates_phase3_tables_and_indexes(self) -> None:
        table_names = {
            str(row.table_name)
            for row in self.db.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name IN (
                        'episodic_memory_entries',
                        'episodic_memory_entry_revisions',
                        'knowledge_documents',
                        'knowledge_document_revisions',
                        'memory_recall_documents'
                      )
                    """
                )
            ).all()
        }
        self.assertEqual(
            {
                "episodic_memory_entries",
                "episodic_memory_entry_revisions",
                "knowledge_documents",
                "knowledge_document_revisions",
                "memory_recall_documents",
            },
            table_names,
        )
        recall_columns = {
            str(row.column_name)
            for row in self.db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'memory_recall_documents'
                    """
                )
            ).all()
        }
        self.assertTrue({"layer", "source_kind", "source_id", "group_hint", "search_text", "search_tsv", "embedding"}.issubset(recall_columns))
        index_names = {
            str(row.indexname)
            for row in self.db.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename = 'memory_recall_documents'
                    """
                )
            ).all()
        }
        self.assertIn("idx_memory_recall_documents_search_tsv", index_names)

    def test_ingest_event_record_writes_l2_and_repeated_hits_promote_to_l3(self) -> None:
        payload = EventRecordCreate(
            household_id=self.household.id,
            event_type="family_event_occurred",
            source_type="system",
            payload={
                "title": "昨晚九点一起散步",
                "summary": "昨晚九点一起散步三十分钟",
                "memory_type": "event",
                "visibility": "family",
            },
        )
        event1, _ = ingest_event_record(self.db, payload)
        event2, _ = ingest_event_record(self.db, payload.model_copy(update={"occurred_at": "2026-03-19T01:00:00Z"}))
        self.db.commit()

        episodic_rows = list(self.db.scalars(select(EpisodicMemoryEntry).where(EpisodicMemoryEntry.household_id == self.household.id)).all())
        self.assertEqual(2, len(episodic_rows))
        episodic_revisions = list(
            self.db.scalars(select(EpisodicMemoryEntryRevision)).all()
        )
        self.assertEqual(2, len(episodic_revisions))
        self.assertTrue(all(item.action == "create" for item in episodic_revisions))
        recall_bundle = build_memory_recall_bundle(
            self.db,
            household_id=self.household.id,
            actor=self.actor,
            requester_member_id=self.member.id,
            query="散步",
        )
        self.assertTrue(any(hit.layer == "L2" for hit in recall_bundle.recent_events))
        self.assertTrue(any(hit.layer == "L3" for hit in recall_bundle.stable_facts))

        recall_docs = list(
            self.db.scalars(
                select(MemoryRecallDocument).where(MemoryRecallDocument.household_id == self.household.id)
            ).all()
        )
        self.assertTrue(any(row.layer == "L2" and row.group_hint == "recent_events" for row in recall_docs))
        self.assertTrue(any(row.layer == "L3" and row.group_hint == "stable_facts" for row in recall_docs))
        self.assertEqual("processed", event1.processing_status)
        self.assertEqual("processed", event2.processing_status)

    def test_plugin_raw_records_create_l4_knowledge_documents(self) -> None:
        result = run_plugin_sync_pipeline(
            self.db,
            household_id=self.household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": self.member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        self.assertEqual("success", result.run.status)
        knowledge_rows = list(
            self.db.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.household_id == self.household.id)
            ).all()
        )
        self.assertEqual(3, len(knowledge_rows))
        knowledge_revisions = list(
            self.db.scalars(select(KnowledgeDocumentRevision)).all()
        )
        self.assertEqual(3, len(knowledge_revisions))
        self.assertTrue(all(item.action == "create" for item in knowledge_revisions))

        recall_bundle = build_memory_recall_bundle(
            self.db,
            household_id=self.household.id,
            actor=self.actor,
            requester_member_id=self.member.id,
            query="sleep",
        )
        self.assertTrue(recall_bundle.external_knowledge)
        self.assertTrue(all(hit.layer == "L4" for hit in recall_bundle.external_knowledge))

    def test_rule_and_doc_knowledge_documents_join_unified_recall(self) -> None:
        upsert_knowledge_document(
            self.db,
            household_id=self.household.id,
            source_kind="rule",
            source_ref="house-rules:quiet-hours",
            title="安静时段规则",
            summary="晚上十点后客厅不播放高音量内容",
            body_text="规则文档：晚上十点后客厅不播放高音量内容，早上七点前同样适用。",
            visibility="family",
            updated_at="2026-03-19T09:00:00Z",
        )
        upsert_knowledge_document(
            self.db,
            household_id=self.household.id,
            source_kind="doc",
            source_ref="manual:coffee-machine",
            title="咖啡机说明文档",
            summary="长按清洁键三秒可进入清洁模式",
            body_text="说明文档：长按清洁键三秒进入清洁模式，清洁完成后机器会自动冲洗。",
            visibility="family",
            updated_at="2026-03-19T09:05:00Z",
        )
        updated_rule = upsert_knowledge_document(
            self.db,
            household_id=self.household.id,
            source_kind="rule",
            source_ref="house-rules:quiet-hours",
            title="安静时段规则",
            summary="晚上十点后客厅和卧室不播放高音量内容",
            body_text="规则文档：晚上十点后客厅和卧室不播放高音量内容，早上七点前同样适用。",
            visibility="family",
            updated_at="2026-03-19T09:10:00Z",
        )
        self.db.commit()

        knowledge_rows = list(
            self.db.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.household_id == self.household.id)
            ).all()
        )
        self.assertEqual({"rule", "doc"}, {row.source_kind for row in knowledge_rows})
        rule_revisions = list(
            self.db.scalars(
                select(KnowledgeDocumentRevision)
                .where(KnowledgeDocumentRevision.document_id == updated_rule.id)
                .order_by(KnowledgeDocumentRevision.revision_no.asc())
            ).all()
        )
        self.assertEqual(2, len(rule_revisions))
        self.assertEqual(["create", "update"], [row.action for row in rule_revisions])

        recall_bundle = build_memory_recall_bundle(
            self.db,
            household_id=self.household.id,
            actor=self.actor,
            requester_member_id=self.member.id,
            query="安静时段",
        )
        self.assertTrue(any(hit.source_kind == "rule" for hit in recall_bundle.external_knowledge))

    def test_l4_observation_rejects_member_outside_household(self) -> None:
        other_household = create_household(
            self.db,
            HouseholdCreate(name="Other Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        outsider = create_member(
            self.db,
            MemberCreate(household_id=other_household.id, name="Bob", role="adult"),
        )
        self.db.flush()

        execution_result = execute_plugin(
            PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": outsider.id},
            ),
            root_dir=self.builtin_root,
        )
        self.assertTrue(execution_result.success)
        assert isinstance(execution_result.output, dict)
        saved_rows = save_plugin_raw_records(
            self.db,
            household_id=self.household.id,
            execution_result=execution_result,
            raw_records=execution_result.output.get("records", []),
        )
        self.db.flush()

        with self.assertRaises(HTTPException):
            upsert_knowledge_document_from_observation(
                self.db,
                household_id=self.household.id,
                subject_member_id=outsider.id,
                source_plugin_id="health-basic-reader",
                source_raw_record_id=saved_rows[0].id,
                observation={
                    "subject_type": "Person",
                    "subject_id": outsider.id,
                    "category": "sleep_duration",
                    "value": 6.8,
                    "unit": "hour",
                    "observed_at": "2026-03-19T09:20:00Z",
                },
            )

    @patch("app.modules.conversation.service._run_proposal_pipeline_for_turn", return_value=None)
    @patch("app.modules.conversation.orchestrator.invoke_llm")
    def test_free_chat_injects_unified_recall_groups_and_persists_trace(self, invoke_llm_mock, _proposal_mock) -> None:
        create_manual_memory_card(
            self.db,
            payload=MemoryCardManualCreate(
                household_id=self.household.id,
                memory_type="preference",
                title="早餐偏好",
                summary="Alice 早餐更喜欢热拿铁",
            ),
            actor=self.actor,
        )
        ingest_event_record(
            self.db,
            EventRecordCreate(
                household_id=self.household.id,
                event_type="family_event_occurred",
                source_type="system",
                payload={"title": "昨晚散步", "summary": "昨晚九点一起散步三十分钟", "memory_type": "event"},
            ),
        )
        ingest_event_record(
            self.db,
            EventRecordCreate(
                household_id=self.household.id,
                event_type="family_event_occurred",
                source_type="system",
                payload={"title": "昨晚散步", "summary": "昨晚九点一起散步三十分钟", "memory_type": "event"},
                occurred_at="2026-03-19T01:00:00Z",
            ),
        )
        run_plugin_sync_pipeline(
            self.db,
            household_id=self.household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="integration",
                payload={"member_id": self.member.id},
            ),
            root_dir=self.builtin_root,
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
            self._intent_result(),
            _FakeLlmResult(text="你早餐更喜欢热拿铁。"),
            self._intent_result(),
            _FakeLlmResult(text="昨晚我们还聊到了散步安排。"),
            self._intent_result(),
            _FakeLlmResult(text="我记得你喜欢热拿铁，也记录到了散步和 sleep 数据。"),
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
            payload=ConversationTurnCreate(message="顺便总结一下昨晚散步的事", channel="app"),
            actor=self.actor,
        )
        turn = create_conversation_turn(
            self.db,
            session_id=session.id,
            payload=ConversationTurnCreate(message="继续刚才的话题，latte、散步和 sleep 还记得吗？", channel="app"),
            actor=self.actor,
        )
        self.db.commit()

        variables = invoke_llm_mock.call_args_list[-1].kwargs["variables"]
        memory_context = variables["memory_context"]
        self.assertIn("[session_summary]", memory_context)
        self.assertIn("[stable_facts]", memory_context)
        self.assertIn("[recent_events]", memory_context)
        self.assertIn("[external_knowledge]", memory_context)
        self.assertIn("热拿铁", memory_context)
        self.assertIn("散步", memory_context)
        self.assertIn("sleep", memory_context)

        reads = list(conversation_repository.list_memory_reads(self.db, session_id=session.id, request_id=turn.request_id))
        groups = {item.group_name for item in reads}
        self.assertIn("session_summary", groups)
        self.assertIn("stable_facts", groups)
        self.assertIn("recent_events", groups)
        self.assertIn("external_knowledge", groups)

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
