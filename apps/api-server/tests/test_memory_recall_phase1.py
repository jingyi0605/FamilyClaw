import unittest
from unittest.mock import patch

import app.db.models  # noqa: F401
from sqlalchemy import text

from app.api.dependencies import ActorContext
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.memory.query_service import query_memory_cards
from app.modules.memory.schemas import MemoryCardManualCreate, MemoryQueryRequest
from app.modules.memory.service import create_manual_memory_card


class MemoryRecallPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Recall Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.owner = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Alice", role="adult"),
        )
        self.other_member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Bob", role="adult"),
        )
        self.db.commit()

        self.actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=self.owner.id,
            account_id="account-owner",
            account_type="household",
            account_status="active",
            username="alice",
            household_id=self.household.id,
            member_id=self.owner.id,
            member_role="adult",
            is_authenticated=True,
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_migration_adds_recall_projection_columns_and_indexes(self) -> None:
        rows = self.db.execute(
            text(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'memory_cards'
                  AND column_name IN (
                    'search_text',
                    'search_tsv',
                    'embedding',
                    'projection_version',
                    'projection_updated_at'
                  )
                ORDER BY column_name
                """
            )
        ).all()
        column_types = {str(row.column_name): str(row.udt_name) for row in rows}

        self.assertEqual(
            {
                "embedding",
                "projection_updated_at",
                "projection_version",
                "search_text",
                "search_tsv",
            },
            set(column_types.keys()),
        )
        self.assertEqual("text", column_types["search_text"])
        self.assertEqual("tsvector", column_types["search_tsv"])
        self.assertEqual("int4", column_types["projection_version"])
        self.assertEqual("text", column_types["projection_updated_at"])
        self.assertIn(column_types["embedding"], {"text", "vector"})

        index_names = {
            str(row.indexname)
            for row in self.db.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename = 'memory_cards'
                    """
                )
            ).all()
        }
        self.assertIn("idx_memory_cards_search_tsv", index_names)

        trace_table_exists = self.db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = 'conversation_memory_reads'
                )
                """
            )
        ).scalar()
        self.assertTrue(bool(trace_table_exists))

    def test_create_manual_memory_card_populates_recall_projection_fields(self) -> None:
        card = self._create_memory_card(
            member_id=self.owner.id,
            memory_type="fact",
            title="Alice 喜欢拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
        )
        self.db.commit()

        row = self.db.execute(
            text(
                """
                SELECT search_text, search_tsv IS NOT NULL AS has_search_tsv, projection_version, projection_updated_at
                FROM memory_cards
                WHERE id = :memory_id
                """
            ),
            {"memory_id": card.id},
        ).mappings().one()

        self.assertIn("alice", str(row["search_text"]))
        self.assertIn("拿铁", str(row["search_text"]))
        self.assertTrue(bool(row["has_search_tsv"]))
        self.assertEqual(1, int(row["projection_version"]))
        self.assertTrue(str(row["projection_updated_at"]).strip())

    def test_query_memory_cards_returns_grouped_hits_and_filters_hidden_cards(self) -> None:
        fact_card = self._create_memory_card(
            member_id=self.owner.id,
            memory_type="fact",
            title="Alice 喜欢拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
            importance=5,
        )
        event_card = self._create_memory_card(
            member_id=self.owner.id,
            memory_type="event",
            title="Alice 昨晚加班",
            summary="Alice 昨晚十点后才回家",
            dedupe_key="memory:event:overtime",
            importance=4,
            last_observed_at="2026-03-18T22:30:00Z",
        )
        hidden_card = self._create_memory_card(
            member_id=self.other_member.id,
            memory_type="fact",
            title="Bob 的敏感病史",
            summary="这条敏感信息不应该被 Alice 看见",
            dedupe_key="memory:fact:bob-sensitive",
            visibility="sensitive",
        )
        self.db.commit()

        result = query_memory_cards(
            self.db,
            payload=MemoryQueryRequest(
                household_id=self.household.id,
                requester_member_id=self.owner.id,
                query="Alice 最近喜欢喝什么，昨晚发生了什么",
                status="active",
                limit=10,
                group_limit=3,
            ),
            actor=self.actor,
        )

        self.assertEqual(2, result.total)
        self.assertEqual([fact_card.id], [item.memory_id for item in result.recall.stable_facts])
        self.assertEqual([event_card.id], [item.memory_id for item in result.recall.recent_events])
        self.assertNotIn(hidden_card.id, [item.memory_id for item in result.items])
        self.assertEqual("stable_facts", result.recall.stable_facts[0].group_name)
        self.assertEqual("recent_events", result.recall.recent_events[0].group_name)
        self.assertEqual(1, result.recall.stable_facts[0].rank)
        self.assertEqual(1, result.recall.recent_events[0].rank)

    def test_query_memory_cards_marks_degraded_when_pgvector_unavailable(self) -> None:
        self._create_memory_card(
            member_id=self.owner.id,
            memory_type="fact",
            title="Alice 喜欢拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
        )
        self.db.commit()

        with patch("app.modules.memory.query_service.is_pgvector_enabled", return_value=False):
            result = query_memory_cards(
                self.db,
                payload=MemoryQueryRequest(
                    household_id=self.household.id,
                    requester_member_id=self.owner.id,
                    query="Alice 喜欢喝什么",
                    status="active",
                    limit=5,
                    group_limit=3,
                ),
                actor=self.actor,
            )

        self.assertTrue(result.degraded)
        self.assertIn("pgvector_unavailable", result.degrade_reasons)
        self.assertGreaterEqual(result.total, 1)

    def test_query_memory_cards_falls_back_to_visible_cards_when_recall_impl_fails(self) -> None:
        card = self._create_memory_card(
            member_id=self.owner.id,
            memory_type="fact",
            title="Alice 喜欢拿铁",
            summary="Alice 早餐更喜欢喝热拿铁",
            dedupe_key="memory:fact:latte",
        )
        self.db.commit()

        with patch("app.modules.memory.query_service._query_memory_cards_impl", side_effect=RuntimeError("boom")):
            result = query_memory_cards(
                self.db,
                payload=MemoryQueryRequest(
                    household_id=self.household.id,
                    requester_member_id=self.owner.id,
                    query="Alice 喜欢喝什么",
                    status="active",
                    limit=5,
                    group_limit=3,
                ),
                actor=self.actor,
            )

        self.assertTrue(result.degraded)
        self.assertEqual(["memory_recall_query_failed"], result.degrade_reasons)
        self.assertIn(card.id, [item.memory_id for item in result.items])

    def _create_memory_card(
        self,
        *,
        member_id: str,
        memory_type: str,
        title: str,
        summary: str,
        dedupe_key: str,
        visibility: str = "family",
        importance: int = 3,
        confidence: float = 0.9,
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
                visibility=visibility,
                importance=importance,
                confidence=confidence,
                subject_member_id=member_id,
                dedupe_key=dedupe_key,
                last_observed_at=last_observed_at,
                reason="测试数据",
            ),
            actor=self.actor,
        )


if __name__ == "__main__":
    unittest.main()
