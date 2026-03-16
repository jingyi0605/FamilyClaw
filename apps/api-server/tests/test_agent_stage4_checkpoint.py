import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.agent.schemas import AgentCreate, AgentPluginMemoryCheckpointRequest
from app.modules.agent.service import create_agent, run_agent_plugin_memory_checkpoint
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class AgentStage4CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

        from app.modules.plugin import service as plugin_service_module

        self._original_builtin_root = plugin_service_module.BUILTIN_PLUGIN_ROOT
        plugin_service_module.BUILTIN_PLUGIN_ROOT = self.builtin_root

    def tearDown(self) -> None:
        from app.modules.plugin import service as plugin_service_module

        plugin_service_module.BUILTIN_PLUGIN_ROOT = self._original_builtin_root
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_stage4_checkpoint_runs_plugin_pipeline_and_reads_memory(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Stage4 Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="绗ㄧ",
                agent_type="butler",
                self_identity="鎴戞槸绗ㄧ",
                role_summary="瀹跺涵 AI 绠″",
                created_by="test",
            ),
        )
        self.db.flush()

        result = run_agent_plugin_memory_checkpoint(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            payload=AgentPluginMemoryCheckpointRequest(
                plugin_id="health-basic-reader",
                payload={"member_id": member.id},
            ),
        )
        self.db.commit()

        self.assertTrue(result.pipeline_success)
        self.assertFalse(result.degraded)
        self.assertEqual("health-basic-reader", result.plugin_id)
        self.assertGreater(result.raw_record_count, 0)
        self.assertGreater(result.memory_card_count, 0)
        self.assertIn("health-basic-reader", result.insight.used_plugins)
        self.assertTrue(any(fact.category == "daily_steps" for fact in result.insight.facts))
        self.assertIn("鎻掍欢鍐欏叆鐨勫搴蹇?, result.insight.summary)


if __name__ == "__main__":
    unittest.main()

