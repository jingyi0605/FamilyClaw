import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.agent import repository as agent_repository
from app.modules.agent.schemas import AgentCreate, AgentRuntimePolicyUpsert
from app.modules.agent.bootstrap_service import (
    advance_butler_bootstrap_session,
    confirm_butler_bootstrap_session,
    start_butler_bootstrap_session,
)
from app.modules.agent.schemas import ButlerBootstrapConfirm, ButlerBootstrapMessageCreate
from app.modules.agent.service import create_agent, upsert_agent_runtime_policy
from app.modules.ai_gateway.provider_config_service import list_provider_adapters
from app.modules.ai_gateway.schemas import AiCapabilityRouteUpsert, AiProviderProfileCreate
from app.modules.ai_gateway.service import create_provider_profile, upsert_capability_route
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household, get_household_setup_status
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class AiConfigCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

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

    def test_provider_adapter_registry_exposes_core_adapters(self) -> None:
        adapters = list_provider_adapters()

        adapter_codes = {item.adapter_code for item in adapters}
        self.assertTrue({"chatgpt", "glm", "siliconflow", "kimi", "minimax"}.issubset(adapter_codes))

        chatgpt = next(item for item in adapters if item.adapter_code == "chatgpt")
        field_keys = {field.key for field in chatgpt.field_schema}
        self.assertIn("provider_code", field_keys)
        self.assertIn("model_name", field_keys)
        self.assertIn("secret_ref", field_keys)

    def test_runtime_policy_default_entry_stays_unique(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        first = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="主管家一号",
                agent_type="butler",
                self_identity="我是主管家一号",
                role_summary="负责家庭事务",
                personality_traits=["稳"],
                service_focus=["问答"],
                default_entry=False,
            ),
        )
        second = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="主管家二号",
                agent_type="butler",
                self_identity="我是主管家二号",
                role_summary="负责家庭事务",
                personality_traits=["稳"],
                service_focus=["提醒"],
                default_entry=False,
            ),
        )
        self.db.flush()

        upsert_agent_runtime_policy(
            self.db,
            household_id=household.id,
            agent_id=first.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
            ),
        )
        upsert_agent_runtime_policy(
            self.db,
            household_id=household.id,
            agent_id=second.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
            ),
        )
        self.db.commit()

        first_runtime = agent_repository.get_runtime_policy(self.db, agent_id=first.id)
        second_runtime = agent_repository.get_runtime_policy(self.db, agent_id=second.id)

        self.assertIsNotNone(first_runtime)
        self.assertIsNotNone(second_runtime)
        assert first_runtime is not None
        assert second_runtime is not None
        self.assertFalse(first_runtime.default_entry)
        self.assertTrue(second_runtime.default_entry)

    def test_setup_status_moves_forward_after_formal_ai_config_completed(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )

        provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="family-chatgpt-main",
                display_name="家庭主模型",
                transport_type="openai_compatible",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["qa_generation", "qa_structured_answer"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
        )
        self.db.flush()

        for capability in ["qa_generation", "qa_structured_answer"]:
            upsert_capability_route(
                self.db,
                AiCapabilityRouteUpsert(
                    capability=capability,
                    household_id=household.id,
                    primary_provider_profile_id=provider.id,
                    fallback_provider_profile_ids=[],
                    routing_mode="primary_then_fallback",
                    timeout_ms=15000,
                    max_retry_count=0,
                    allow_remote=True,
                    prompt_policy={},
                    response_policy={},
                    enabled=True,
                ),
            )

        create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="小爪管家",
                agent_type="butler",
                self_identity="我是家庭主管家",
                role_summary="负责家庭问答和提醒",
                personality_traits=["细心"],
                service_focus=["家庭问答", "提醒"],
                default_entry=True,
            ),
        )
        self.db.commit()

        setup_status = get_household_setup_status(self.db, household.id)
        self.assertEqual("completed", setup_status.status)
        self.assertEqual("finish", setup_status.current_step)
        self.assertFalse(setup_status.is_required)

    def test_butler_bootstrap_flow_reuses_existing_agent_creation_model(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Bootstrap Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="bootstrap-chatgpt-main",
                display_name="Bootstrap 模型",
                transport_type="openai_compatible",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["qa_generation"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
        )
        self.db.flush()

        upsert_capability_route(
            self.db,
            AiCapabilityRouteUpsert(
                capability="qa_generation",
                household_id=household.id,
                primary_provider_profile_id=provider.id,
                fallback_provider_profile_ids=[],
                routing_mode="primary_then_fallback",
                timeout_ms=15000,
                max_retry_count=0,
                allow_remote=True,
                prompt_policy={},
                response_policy={},
                enabled=True,
            ),
        )
        self.db.flush()

        session = start_butler_bootstrap_session(self.db, household_id=household.id)
        self.assertEqual("display_name", session.pending_field)

        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="阿福",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="负责家庭问答、提醒和成员关怀",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="温和直接，少废话",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="细心，稳重，有边界感",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="家庭问答，提醒复盘，成员关怀",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )

        self.assertEqual("reviewing", session.status)
        self.assertTrue(session.can_confirm)
        self.assertEqual(["细心", "稳重", "有边界感"], session.draft.personality_traits)

        created = confirm_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            payload=ButlerBootstrapConfirm(draft=session.draft, created_by="setup-wizard"),
        )
        self.db.commit()

        self.assertEqual("阿福", created.display_name)
        self.assertEqual("butler", created.agent_type)
        self.assertIsNotNone(created.soul)
        assert created.soul is not None
        self.assertEqual("负责家庭问答、提醒和成员关怀", created.soul.role_summary)
        self.assertEqual(["家庭问答", "提醒复盘", "成员关怀"], created.soul.service_focus)

    def test_butler_bootstrap_requires_provider_first(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="No Provider Home", city="Suzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        with self.assertRaisesRegex(Exception, "请先完成 AI 供应商配置"):
            start_butler_bootstrap_session(self.db, household_id=household.id)


if __name__ == "__main__":
    unittest.main()
