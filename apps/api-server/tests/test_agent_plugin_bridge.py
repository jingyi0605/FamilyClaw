import json
import sys
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
from app.modules.plugin import AgentPluginInvokeRequest, PluginMountCreate, disable_plugin, invoke_agent_plugin, register_plugin_mount, set_household_plugin_enabled
from app.modules.plugin.schemas import PluginStateUpdateRequest


class AgentPluginBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self.builtin_root = Path(__file__).resolve().parents[1] / "app" / "plugins" / "builtin"
        self.state_file = Path(self._tempdir.name) / "plugin_registry_state.json"

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_invoke_agent_plugin_returns_success_and_records_audit(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Agent Plugin Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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
                plugin_type="integration",
                payload={"member_id": member.id},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(result.success)
        self.assertEqual(agent.id, result.agent_id)
        self.assertEqual("绗ㄧ", result.agent_name)
        self.assertEqual("health-basic-reader", result.plugin_id)
        self.assertEqual("integration", result.plugin_type)
        self.assertTrue(result.queued)
        self.assertEqual("queued", result.job_status)
        self.assertIsNotNone(result.job_id)
        self.assertIsNone(result.output)

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
        self.assertEqual("integration", details["plugin_type"])

    def test_invoke_agent_plugin_returns_failure_when_plugin_disabled(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Agent Plugin Fail Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="鐖哥埜", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="闃跨",
                agent_type="butler",
                self_identity="鎴戞槸闃跨",
                role_summary="瀹跺涵 AI 绠″",
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
                plugin_type="integration",
                payload={"member_id": member.id},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertFalse(result.success)
        self.assertEqual("agent_plugin_invoke_failed", result.error_code)
        self.assertIn("当前家庭停用", result.error_message or "")

        audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.invoke",
            AuditLog.target_type == "plugin",
            AuditLog.target_id == "health-basic-reader",
        )
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("fail", audit_row.result)

    def test_invoke_agent_plugin_supports_third_party_runner_mount(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Third Party Agent Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="澶栭儴鍔╂墜",
                agent_type="butler",
                self_identity="鎴戞槸澶栭儴鍔╂墜",
                role_summary="绗笁鏂规彃浠舵祴璇?Agent",
                created_by="test",
            ),
        )
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id="account-3",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_integration_plugin(Path(tempdir), plugin_id="third-party-agent-plugin")
            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )
            self.db.flush()

            result = invoke_agent_plugin(
                self.db,
                household_id=household.id,
                agent_id=agent.id,
                request=AgentPluginInvokeRequest(
                    plugin_id="third-party-agent-plugin",
                    plugin_type="integration",
                    payload={"member_id": member.id},
                ),
                actor=actor,
            )
            self.db.commit()

        self.assertTrue(result.success)
        self.assertTrue(result.queued)
        self.assertEqual("queued", result.job_status)
        self.assertIsNotNone(result.job_id)

    def test_invoke_agent_plugin_returns_failure_when_household_override_disables_third_party_plugin(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Third Party Disabled Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="濡堝", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="澶栭儴鍔╂墜",
                agent_type="butler",
                self_identity="鎴戞槸澶栭儴鍔╂墜",
                role_summary="绗笁鏂规彃浠舵祴璇?Agent",
                created_by="test",
            ),
        )
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id="account-4",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_integration_plugin(Path(tempdir), plugin_id="third-party-agent-plugin")
            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=10,
                ),
            )
            set_household_plugin_enabled(
                self.db,
                household_id=household.id,
                plugin_id="third-party-agent-plugin",
                payload=PluginStateUpdateRequest(enabled=False),
                updated_by="tester",
            )
            self.db.flush()

            result = invoke_agent_plugin(
                self.db,
                household_id=household.id,
                agent_id=agent.id,
                request=AgentPluginInvokeRequest(
                    plugin_id="third-party-agent-plugin",
                    plugin_type="integration",
                    payload={"member_id": member.id},
                ),
                actor=actor,
            )
            self.db.commit()

        self.assertFalse(result.success)
        self.assertEqual("agent_plugin_invoke_failed", result.error_code)
        self.assertIn("当前家庭停用", result.error_message or "")

    def _create_third_party_integration_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "绗笁鏂?Agent 鎻掍欢",
                    "version": "0.1.0",
                    "types": ["integration"],
                    "permissions": ["health.read"],
                    "risk_level": "low",
                    "triggers": ["agent"],
                    "entrypoints": {"integration": "plugin.integration.sync"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n"
            "    data = payload or {}\n"
            "    return {'source': 'third-party-agent-plugin', 'echo': data, 'records': []}\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()


