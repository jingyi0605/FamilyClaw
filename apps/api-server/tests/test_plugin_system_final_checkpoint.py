import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.modules.agent.schemas import AgentCreate, AgentPluginMemoryCheckpointRequest
from app.modules.agent.service import create_agent, run_agent_plugin_memory_checkpoint
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.permission.schemas import MemberPermissionReplaceRequest, MemberPermissionRule
from app.modules.permission.service import replace_member_permissions
from app.modules.plugin import AgentActionPluginInvokeRequest, confirm_agent_action_plugin, invoke_agent_action_plugin, list_registered_plugins


class PluginSystemFinalCheckpointTests(unittest.TestCase):
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

    def test_final_checkpoint_runs_full_v1_chain(self) -> None:
        registry = list_registered_plugins(root_dir=self.builtin_root, state_file=self.state_file)
        self.assertTrue(any(item.id == "health-basic-reader" for item in registry.items))
        self.assertTrue(any(item.id == "homeassistant" for item in registry.items))

        household = create_household(
            self.db,
            HouseholdCreate(name="Final Check Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="妈妈", role="adult"),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="终检管家",
                agent_type="butler",
                self_identity="我是终检管家",
                role_summary="家庭 AI 管家",
                created_by="test",
            ),
        )
        actor = ActorContext(
            role="member",
            actor_type="member",
            actor_id=member.id,
            account_id="final-check-account",
            account_type="member",
            account_status="active",
            household_id=household.id,
            member_id=member.id,
            member_role=member.role,
            is_authenticated=True,
        )
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

        stage4_result = run_agent_plugin_memory_checkpoint(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            payload=AgentPluginMemoryCheckpointRequest(
                plugin_id="health-basic-reader",
                payload={"member_id": member.id},
            ),
        )
        self.assertTrue(stage4_result.queued)
        self.assertEqual("queued", stage4_result.job_status)
        self.assertIsNotNone(stage4_result.job_id)

        medium_action_result = invoke_agent_action_plugin(
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
        self.assertTrue(medium_action_result.success)
        self.assertTrue(medium_action_result.queued)
        self.assertEqual("queued", medium_action_result.job_status)

        high_risk_request = invoke_agent_action_plugin(
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
        self.assertEqual("confirmation_required", high_risk_request.authorization_status)
        self.assertFalse(high_risk_request.success)

        high_risk_confirmed = confirm_agent_action_plugin(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            confirmation_request_id=high_risk_request.confirmation_request_id or "",
            actor=actor,
            root_dir=self.builtin_root,
            state_file=self.state_file,
        )
        self.db.commit()

        self.assertTrue(high_risk_confirmed.success)
        self.assertEqual("allowed", high_risk_confirmed.authorization_status)
        self.assertTrue(high_risk_confirmed.queued)
        self.assertEqual("queued", high_risk_confirmed.job_status)


if __name__ == "__main__":
    unittest.main()
