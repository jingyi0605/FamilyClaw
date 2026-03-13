import unittest
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import build_agent_memory_insight, create_agent
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import run_plugin_sync_pipeline


class AgentMemoryInsightTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_build_agent_memory_insight_uses_plugin_observations(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Insight Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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

        run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="homeassistant-device-sync",
                plugin_type="connector",
                payload={"room_id": "living-room"},
            ),
            root_dir=self.builtin_root,
        )
        run_plugin_sync_pipeline(
            self.db,
            household_id=household.id,
            request=PluginExecutionRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            root_dir=self.builtin_root,
        )
        self.db.commit()

        result = build_agent_memory_insight(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
        )

        self.assertEqual(agent.id, result.agent_id)
        self.assertIn("插件写入的家庭记忆", result.summary)
        self.assertIn("health-basic-reader", result.used_plugins)
        self.assertIn("homeassistant-device-sync", result.used_plugins)
        self.assertTrue(any(item.category == "sleep_duration" for item in result.facts))
        self.assertTrue(any(item.category == "room_temperature" for item in result.facts))
        self.assertTrue(any("睡眠" in item for item in result.suggestions))

    def test_build_agent_memory_insight_returns_empty_state_when_no_plugin_memory(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Empty Insight Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="阿福",
                agent_type="butler",
                self_identity="我是阿福",
                role_summary="家庭 AI 管家",
                created_by="test",
            ),
        )
        self.db.commit()

        result = build_agent_memory_insight(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
        )

        self.assertEqual([], result.used_plugins)
        self.assertEqual([], result.facts)
        self.assertIn("还没有可用的插件记忆", result.summary)


if __name__ == "__main__":
    unittest.main()
