import unittest

from app.db.engine import build_database_engine_kwargs, ensure_postgresql_url, is_postgresql_url
from app.modules.agent.models import FamilyAgent, FamilyAgentSoulProfile
from app.modules.ai_gateway.models import AiCapabilityRoute


def _get_index(table, name: str):
    for index in table.indexes:
        if index.name == name:
            return index
    raise AssertionError(f"找不到索引 {name}")


class DatabaseEngineConfigTests(unittest.TestCase):
    def test_non_postgresql_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "仅支持 PostgreSQL"):
            ensure_postgresql_url("sqlite:///./data/test.db")

    def test_postgresql_engine_kwargs_enable_pooling(self) -> None:
        kwargs = build_database_engine_kwargs(
            "postgresql+psycopg://familyclaw:secret@127.0.0.1:5432/familyclaw",
            pool_size=12,
            max_overflow=7,
            pool_timeout_seconds=45,
            pool_recycle_seconds=900,
        )

        self.assertTrue(is_postgresql_url("postgresql+psycopg://familyclaw:secret@127.0.0.1:5432/familyclaw"))
        self.assertEqual(kwargs["pool_size"], 12)
        self.assertEqual(kwargs["max_overflow"], 7)
        self.assertEqual(kwargs["pool_timeout"], 45)
        self.assertEqual(kwargs["pool_recycle"], 900)
        self.assertEqual(kwargs["pool_pre_ping"], True)
        self.assertNotIn("connect_args", kwargs)


class PartialIndexDialectTests(unittest.TestCase):
    def test_ai_capability_route_partial_indexes_include_postgresql_where(self) -> None:
        global_index = _get_index(
            AiCapabilityRoute.__table__,
            "uq_ai_capability_routes_global_capability",
        )
        household_index = _get_index(
            AiCapabilityRoute.__table__,
            "uq_ai_capability_routes_household_capability",
        )

        self.assertEqual(str(global_index.dialect_options["postgresql"]["where"]), "household_id IS NULL")
        self.assertEqual(str(household_index.dialect_options["postgresql"]["where"]), "household_id IS NOT NULL")

    def test_agent_partial_indexes_include_postgresql_where(self) -> None:
        primary_index = _get_index(FamilyAgent.__table__, "uq_family_agents_household_primary")
        active_profile_index = _get_index(
            FamilyAgentSoulProfile.__table__,
            "uq_family_agent_soul_profiles_agent_active",
        )

        self.assertEqual(str(primary_index.dialect_options["postgresql"]["where"]), "is_primary = true")
        self.assertEqual(str(active_profile_index.dialect_options["postgresql"]["where"]), "is_active = true")


if __name__ == "__main__":
    unittest.main()
