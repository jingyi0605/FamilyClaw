import json
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.audit.models import AuditLog
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin import AgentPluginInvokeRequest, disable_plugin, invoke_agent_plugin


class AgentPluginBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        self.state_file = Path(self._tempdir.name) / "plugin_registry_state.json"

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

    def test_invoke_agent_plugin_returns_success_and_records_audit(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Agent Plugin Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id="account-1",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )
        self.db.flush()

        result = invoke_agent_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentPluginInvokeRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(result.success)
        self.assertEqual(agent.id, result.agent_id)
        self.assertEqual("笨笨", result.agent_name)
        self.assertEqual("health-basic-reader", result.plugin_id)
        self.assertEqual("connector", result.plugin_type)
        self.assertIsInstance(result.output, dict)
        assert isinstance(result.output, dict)
        self.assertEqual(3, len(result.output.get("records", [])))

        audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.invoke",
            AuditLog.target_type == "plugin",
            AuditLog.target_id == "health-basic-reader",
        )
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("success", audit_row.result)
        details = json.loads(audit_row.details or "{}")
        self.assertEqual(agent.id, details["agent_id"])
        self.assertEqual("health-basic-reader", details["plugin_id"])
        self.assertEqual("connector", details["plugin_type"])

    def test_invoke_agent_plugin_returns_failure_when_plugin_disabled(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Agent Plugin Fail Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="爸爸", role="adult"),
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
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id="account-2",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )
        disable_plugin("health-basic-reader", root_dir=self.builtin_root, state_file=self.state_file)
        self.db.flush()

        result = invoke_agent_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentPluginInvokeRequest(
                plugin_id="health-basic-reader",
                plugin_type="connector",
                payload={"member_id": member.id},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertFalse(result.success)
        self.assertEqual("agent_plugin_invoke_failed", result.error_code)
        self.assertIn("插件已禁用", result.error_message or "")

        audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.invoke",
            AuditLog.target_type == "plugin",
            AuditLog.target_id == "health-basic-reader",
        )
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("fail", audit_row.result)


if __name__ == "__main__":
    unittest.main()
