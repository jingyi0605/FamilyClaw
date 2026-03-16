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
from app.modules.permission.schemas import MemberPermissionReplaceRequest, MemberPermissionRule
from app.modules.permission.service import replace_member_permissions
from app.modules.plugin import (
    AgentActionPluginInvokeRequest,
    PluginMountCreate,
    confirm_agent_action_plugin,
    invoke_agent_action_plugin,
    register_plugin_mount,
)


class ActionPluginPermissionTests(unittest.TestCase):
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

    def test_action_plugin_is_denied_without_execute_permission(self) -> None:
        household, member, agent, actor = self._create_agent_context("No Permission Home", "濡堝", "绗ㄧ")

        result = invoke_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentActionPluginInvokeRequest(
                plugin_id="homeassistant",
                payload={"resource_type": "device", "resource_scope": "family", "target_ref": "living-room-light"},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertFalse(result.success)
        self.assertEqual("denied", result.authorization_status)
        self.assertEqual("agent_action_plugin_denied", result.error_code)
        self.assertIn("娌℃湁鍔ㄤ綔鎵ц鏉冮檺", result.error_message or "")

    def test_readonly_plugin_cannot_be_executed_as_action(self) -> None:
        household, member, agent, actor = self._create_agent_context("Readonly Home", "鐖哥埜", "闃跨")
        replace_member_permissions(
            self.db,
            member_id=member.id,
            payload=MemberPermissionReplaceRequest(
                rules=[
                    MemberPermissionRule(
                        resource_type="device",
                        resource_scope="family",
                        action="execute",
                        effect="allow",
                    )
                ]
            ),
        )
        self.db.flush()

        result = invoke_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentActionPluginInvokeRequest(
                plugin_id="health-basic-reader",
                payload={"resource_type": "device", "resource_scope": "family"},
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertFalse(result.success)
        self.assertIn("action", result.error_message or "")

    def test_action_plugin_runs_after_permission_check(self) -> None:
        household, member, agent, actor = self._create_agent_context("Action Home", "濡堝", "灏忕瀹?)
        replace_member_permissions(
            self.db,
            member_id=member.id,
            payload=MemberPermissionReplaceRequest(
                rules=[
                    MemberPermissionRule(
                        resource_type="device",
                        resource_scope="family",
                        action="execute",
                        effect="allow",
                    )
                ]
            ),
        )
        self.db.flush()

        result = invoke_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentActionPluginInvokeRequest(
                plugin_id="homeassistant",
                payload={
                    "resource_type": "device",
                    "resource_scope": "family",
                    "target_ref": "living-room-light",
                    "action_name": "turn_on",
                },
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(result.success)
        self.assertEqual("allowed", result.authorization_status)
        self.assertEqual("medium", result.risk_level)
        self.assertTrue(result.queued)
        self.assertIsNotNone(result.job_id)
        self.assertEqual("queued", result.job_status)
        self.assertIsNone(result.output)

        audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.invoke_action",
            AuditLog.target_type == "plugin",
            AuditLog.target_id == "homeassistant",
        )
        audit_row = self.db.scalar(audit_stmt)
        assert audit_row is not None
        self.assertEqual("success", audit_row.result)
        details = json.loads(audit_row.details or "{}")
        self.assertEqual("allowed", details["authorization_status"])
        self.assertEqual("medium", details["risk_level"])

    def test_high_risk_action_requires_confirmation_before_execution(self) -> None:
        household, member, agent, actor = self._create_agent_context("High Risk Home", "濡堝", "瀹堥棬鍛?)
        replace_member_permissions(
            self.db,
            member_id=member.id,
            payload=MemberPermissionReplaceRequest(
                rules=[
                    MemberPermissionRule(
                        resource_type="device",
                        resource_scope="family",
                        action="execute",
                        effect="allow",
                    )
                ]
            ),
        )
        self.db.flush()

        first_result = invoke_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            request=AgentActionPluginInvokeRequest(
                plugin_id="homeassistant",
                payload={
                    "resource_type": "device",
                    "resource_scope": "family",
                    "target_ref": "front-door-lock",
                    "action_name": "unlock",
                },
            ),
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.flush()

        self.assertFalse(first_result.success)
        self.assertEqual("confirmation_required", first_result.authorization_status)
        self.assertEqual("agent_action_confirmation_required", first_result.error_code)
        self.assertIsNotNone(first_result.confirmation_request_id)

        confirmed_result = confirm_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            confirmation_request_id=first_result.confirmation_request_id or "",
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(confirmed_result.success)
        self.assertEqual("allowed", confirmed_result.authorization_status)
        self.assertEqual("high", confirmed_result.risk_level)
        self.assertEqual(first_result.confirmation_request_id, confirmed_result.confirmation_request_id)
        self.assertTrue(confirmed_result.queued)
        self.assertIsNotNone(confirmed_result.job_id)
        self.assertEqual("queued", confirmed_result.job_status)
        self.assertIsNone(confirmed_result.output)

        request_audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.request_action_confirmation",
            AuditLog.target_id == first_result.confirmation_request_id,
        )
        request_audit = self.db.scalar(request_audit_stmt)
        assert request_audit is not None
        self.assertEqual("pending", request_audit.result)

        confirm_audit_stmt = select(AuditLog).where(
            AuditLog.action == "agent.plugin.confirm_action",
            AuditLog.target_id == first_result.confirmation_request_id,
        )
        confirm_audit = self.db.scalar(confirm_audit_stmt)
        assert confirm_audit is not None
        self.assertEqual("success", confirm_audit.result)

    def test_third_party_action_plugin_runs_with_runner_mount(self) -> None:
        household, member, agent, actor = self._create_agent_context("Third Party Action Home", "濡堝", "澶栭儴鎵ц鍣?)
        replace_member_permissions(
            self.db,
            member_id=member.id,
            payload=MemberPermissionReplaceRequest(
                rules=[
                    MemberPermissionRule(
                        resource_type="device",
                        resource_scope="family",
                        action="execute",
                        effect="allow",
                    )
                ]
            ),
        )

        with tempfile.TemporaryDirectory() as tempdir:
            plugin_root = self._create_third_party_action_plugin(Path(tempdir), plugin_id="third-party-device-action")
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

            result = invoke_agent_action_plugin(
                self.db,
                household_id=household.id,
                agent_id=agent.id,
                request=AgentActionPluginInvokeRequest(
                    plugin_id="third-party-device-action",
                    payload={
                        "resource_type": "device",
                        "resource_scope": "family",
                        "target_ref": "living-room-light",
                        "action_name": "turn_on",
                    },
                ),
                actor=actor,
            )
            self.db.commit()

        self.assertTrue(result.success)
        self.assertEqual("allowed", result.authorization_status)
        self.assertTrue(result.queued)
        self.assertIsNotNone(result.job_id)
        self.assertEqual("queued", result.job_status)
        self.assertIsNone(result.output)

    def _create_agent_context(self, household_name: str, member_name: str, agent_name: str):
        household = create_household(
            self.db,
            HouseholdCreate(name=household_name, city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name=member_name, role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name=agent_name,
                agent_type="butler",
                self_identity=f"鎴戞槸{agent_name}",
                role_summary="瀹跺涵 AI 绠″",
                created_by="test",
            ),
        )
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id=f"account-{member.id}",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )
        self.db.flush()
        return household, member, agent, actor

    def _create_third_party_action_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "绗笁鏂瑰姩浣滄彃浠?,
                    "version": "0.1.0",
                    "types": ["action"],
                    "permissions": ["device.control"],
                    "risk_level": "medium",
                    "triggers": ["agent-action"],
                    "entrypoints": {"action": "plugin.executor.run"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "executor.py").write_text(
            "def run(payload=None):\n"
            "    data = payload or {}\n"
            "    return {\n"
            "        'source': 'third-party-device-action',\n"
            "        'executed': True,\n"
            "        'action_name': data.get('action_name'),\n"
            "        'received_payload': data\n"
            "    }\n",
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()


