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

        db_path = Path(self._tempdir.name) / "test.db"
        settings.database_url = f"sqlite:///{db_path}"

        alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(settings.database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

        from app.modules.plugin import service as plugin_service_module

        self._original_builtin_root = plugin_service_module.BUILTIN_PLUGIN_ROOT
        plugin_service_module.BUILTIN_PLUGIN_ROOT = self.builtin_root

    def tearDown(self) -> None:
        from app.modules.plugin import service as plugin_service_module

        plugin_service_module.BUILTIN_PLUGIN_ROOT = self._original_builtin_root
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_stage4_checkpoint_runs_plugin_pipeline_and_reads_memory(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Stage4 Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="笨笨",
                agent_type="butler",
                self_identity="我是笨笨",
                role_summary="家庭 AI 管家",
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
        self.assertIn("插件写入的家庭记忆", result.insight.summary)


if __name__ == "__main__":
    unittest.main()
