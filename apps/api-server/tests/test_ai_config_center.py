import tempfile
import unittest
from pathlib import Path
import json
from types import SimpleNamespace
from unittest.mock import patch

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
from app.modules.ai_gateway.gateway_service import build_invocation_plan
from app.modules.ai_gateway.provider_config_service import list_provider_adapters
from app.modules.ai_gateway.schemas import AiCapabilityRouteUpsert, AiProviderProfileCreate
from app.modules.ai_gateway.service import create_provider_profile, upsert_capability_route
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household, get_household_setup_status
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog


class AiConfigCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self.db: Session = self.SessionLocal()
        import_region_catalog(
            self.db,
            items=[
                RegionCatalogImportItem(
                    region_code="110000",
                    parent_region_code=None,
                    admin_level="province",
                    name="Beijing",
                    full_name="Beijing",
                    path_codes=["110000"],
                    path_names=["Beijing"],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="Beijing City",
                    full_name="Beijing / Beijing City",
                    path_codes=["110000", "110100"],
                    path_names=["Beijing", "Beijing City"],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="Chaoyang",
                    full_name="Beijing / Beijing City / Chaoyang",
                    path_codes=["110000", "110100", "110105"],
                    path_names=["Beijing", "Beijing City", "Chaoyang"],
                ),
            ],
            source_version="test-v1",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_provider_adapter_catalog_exposes_builtin_ai_provider_plugins(self) -> None:
        adapters = list_provider_adapters()

        adapter_codes = {item.adapter_code for item in adapters}
        self.assertTrue({"chatgpt", "glm", "siliconflow", "kimi", "minimax"}.issubset(adapter_codes))

        chatgpt = next(item for item in adapters if item.adapter_code == "chatgpt")
        field_keys = {field.key for field in chatgpt.field_schema}
        self.assertIn("provider_code", field_keys)
        self.assertIn("model_name", field_keys)
        self.assertIn("secret_ref", field_keys)

    def test_provider_adapter_catalog_aligns_builtin_defaults(self) -> None:
        adapters = {item.adapter_code: item for item in list_provider_adapters()}

        minimax = adapters["minimax"]
        minimax_defaults = {field.key: field.default_value for field in minimax.field_schema}
        self.assertEqual("native_sdk", minimax.transport_type)
        self.assertEqual("anthropic_messages", minimax.api_family)
        self.assertEqual("https://api.minimax.io/anthropic", minimax_defaults["base_url"])
        self.assertEqual("MiniMax-M2.5", minimax_defaults["model_name"])
        self.assertEqual(["llm"], minimax.supported_model_types)

        doubao_coding = adapters["doubao-coding"]
        doubao_coding_defaults = {field.key: field.default_value for field in doubao_coding.field_schema}
        self.assertEqual("https://ark.cn-beijing.volces.com/api/coding/v3", doubao_coding_defaults["base_url"])

        byteplus = adapters["byteplus"]
        byteplus_defaults = {field.key: field.default_value for field in byteplus.field_schema}
        self.assertEqual("https://ark.ap-southeast.bytepluses.com/api/v3", byteplus_defaults["base_url"])

        byteplus_coding = adapters["byteplus-coding"]
        byteplus_coding_defaults = {field.key: field.default_value for field in byteplus_coding.field_schema}
        self.assertEqual("https://ark.ap-southeast.bytepluses.com/api/coding/v3", byteplus_coding_defaults["base_url"])

    def test_create_siliconflow_qwen_provider_does_not_write_vendor_defaults_into_profile(self) -> None:
        provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="family-siliconflow-main",
                display_name="SiliconFlow Main",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.siliconflow.cn/v1",
                secret_ref="env://SILICONFLOW_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                extra_config={
                    "adapter_code": "siliconflow",
                    "model_name": "Qwen/Qwen3.5-9B",
                },
            ),
        )
        self.assertNotIn("default_request_body", provider.extra_config)

    def test_runtime_policy_default_entry_stays_unique(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Test Home",
                timezone="Asia/Shanghai",
                locale="zh-CN",
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                ),
            ),
        )
        self.db.flush()

        first = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="Butler One",
                agent_type="butler",
                self_identity="I am Butler One",
                role_summary="璐熻矗瀹跺涵浜嬪姟",
                personality_traits=["calm"],
                service_focus=["闂瓟"],
                default_entry=False,
            ),
        )
        second = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="Butler Two",
                agent_type="butler",
                self_identity="I am Butler Two",
                role_summary="璐熻矗瀹跺涵浜嬪姟",
                personality_traits=["steady"],
                service_focus=["鎻愰啋"],
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
        self.assertEqual(
            {"memory": "ask", "config": "ask", "action": "ask"},
            json.loads(second_runtime.autonomous_action_policy_json),
        )

    def test_setup_status_moves_forward_after_formal_ai_config_completed(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Test Home",
                timezone="Asia/Shanghai",
                locale="zh-CN",
                region_selection=RegionSelection(
                    provider_code="builtin.cn-mainland",
                    country_code="CN",
                    region_code="110105",
                ),
            ),
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
                display_name="Household Main Model",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
        )
        self.db.flush()

        for capability in ["text"]:
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
                display_name="灏忕埅绠″",
                agent_type="butler",
                self_identity="I am the household butler",
                role_summary="Handle household Q&A and reminders",
                personality_traits=["缁嗗績"],
                service_focus=["瀹跺涵闂瓟", "鎻愰啋"],
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
                display_name="Bootstrap 妯″瀷",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
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
                capability="text",
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
                message="闃跨",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="璐熻矗瀹跺涵闂瓟銆佹彁閱掑拰鎴愬憳鍏虫€€",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="娓╁拰鐩存帴锛屽皯搴熻瘽",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="缁嗗績锛岀ǔ閲嶏紝鏈夎竟鐣屾劅",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )
        session = advance_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapMessageCreate(
                message="瀹跺涵闂瓟锛屾彁閱掑鐩橈紝鎴愬憳鍏虫€€",
                draft=session.draft,
                pending_field=session.pending_field,
            ),
        )

        self.assertEqual("reviewing", session.status)
        self.assertTrue(session.can_confirm)
        self.assertEqual(["缁嗗績", "绋抽噸", "鏈夎竟鐣屾劅"], session.draft.personality_traits)

        created = confirm_butler_bootstrap_session(
            self.db,
            household_id=household.id,
            session_id=session.session_id,
            payload=ButlerBootstrapConfirm(draft=session.draft, created_by="setup-wizard"),
        )
        self.db.commit()

        self.assertEqual("闃跨", created.display_name)
        self.assertEqual("butler", created.agent_type)
        self.assertIsNotNone(created.soul)
        assert created.soul is not None
        self.assertEqual("璐熻矗瀹跺涵闂瓟銆佹彁閱掑拰鎴愬憳鍏虫€€", created.soul.role_summary)
        self.assertEqual(["瀹跺涵闂瓟", "鎻愰啋澶嶇洏", "鎴愬憳鍏虫€€"], created.soul.service_focus)

        message_rows = agent_repository.list_bootstrap_messages(self.db, session_id=session.session_id)
        request_rows = agent_repository.list_bootstrap_requests(self.db, session_id=session.session_id)

        self.assertGreaterEqual(len(message_rows), 3)
        self.assertEqual([index + 1 for index in range(len(message_rows))], [item.seq for item in message_rows])
        self.assertEqual(5, len(request_rows))
        self.assertTrue(all(item.status == "succeeded" for item in request_rows))
        self.assertTrue(all(item.user_message_id for item in request_rows))

    def test_agent_model_binding_takes_priority_over_household_route(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Binding Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        route_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="binding-route-provider",
                display_name="Household Route Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
        )
        bound_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="binding-agent-provider",
                display_name="Agent Bound Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4.1-mini"},
            ),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="Bound Butler",
                agent_type="butler",
                self_identity="I am bound",
                role_summary="Handle household Q&A",
                personality_traits=["calm"],
                service_focus=["问答"],
                default_entry=True,
            ),
        )
        self.db.flush()

        upsert_capability_route(
            self.db,
            AiCapabilityRouteUpsert(
                capability="text",
                household_id=household.id,
                primary_provider_profile_id=route_provider.id,
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
        upsert_agent_runtime_policy(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                model_bindings=[{"capability": "text", "provider_profile_id": bound_provider.id}],
                agent_skill_model_bindings=[],
            ),
        )
        self.db.flush()

        plan = build_invocation_plan(
            self.db,
            capability="text",
            household_id=household.id,
            agent_id=agent.id,
            request_payload={"request_context": {"effective_agent_id": agent.id}},
        )

        assert plan.primary_provider is not None
        self.assertEqual(bound_provider.id, plan.primary_provider.provider_profile_id)

    def test_agent_skill_model_binding_takes_priority_over_agent_binding(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Skill Binding Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        route_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="skill-route-provider",
                display_name="Household Route Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4o-mini"},
            ),
        )
        agent_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="skill-agent-provider",
                display_name="Agent Bound Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4.1-mini"},
            ),
        )
        skill_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="skill-plugin-provider",
                display_name="Skill Bound Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "gpt-4.1"},
            ),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="Skill Bound Butler",
                agent_type="butler",
                self_identity="I am skill bound",
                role_summary="Handle household Q&A",
                personality_traits=["calm"],
                service_focus=["问答"],
                default_entry=True,
            ),
        )
        self.db.flush()

        upsert_capability_route(
            self.db,
            AiCapabilityRouteUpsert(
                capability="text",
                household_id=household.id,
                primary_provider_profile_id=route_provider.id,
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
        upsert_agent_runtime_policy(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                model_bindings=[{"capability": "text", "provider_profile_id": agent_provider.id}],
                agent_skill_model_bindings=[],
            ),
        )
        runtime_policy = agent_repository.get_runtime_policy(self.db, agent_id=agent.id)
        assert runtime_policy is not None
        runtime_policy.agent_skill_model_bindings_json = json.dumps([
            {
                "plugin_id": "demo-agent-skill",
                "capability": "text",
                "provider_profile_id": skill_provider.id,
            }
        ])
        self.db.flush()

        plan = build_invocation_plan(
            self.db,
            capability="text",
            household_id=household.id,
            agent_id=agent.id,
            plugin_id="demo-agent-skill",
            request_payload={
                "request_context": {
                    "effective_agent_id": agent.id,
                    "plugin_id": "demo-agent-skill",
                }
            },
        )

        assert plan.primary_provider is not None
        self.assertEqual(skill_provider.id, plan.primary_provider.provider_profile_id)

    def test_intent_recognition_binding_accepts_text_provider_and_falls_back_to_text_route(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Intent Binding Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        route_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="intent-route-provider",
                display_name="Intent Route Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://api.openai.com/v1",
                api_version=None,
                secret_ref="OPENAI_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=15000,
                cost_policy={},
                extra_config={"adapter_code": "chatgpt", "model_name": "glm-4.5"},
            ),
        )
        bound_provider = create_provider_profile(
            self.db,
            AiProviderProfileCreate(
                provider_code="intent-bound-provider",
                display_name="Intent Bound Provider",
                transport_type="openai_compatible",
                api_family="openai_chat_completions",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_version=None,
                secret_ref="DASHSCOPE_API_KEY",
                enabled=True,
                supported_capabilities=["text"],
                privacy_level="public_cloud",
                latency_budget_ms=8000,
                cost_policy={},
                extra_config={"adapter_code": "qwen", "model_name": "qwen2.5-14b-instruct"},
            ),
        )
        agent = create_agent(
            self.db,
            household_id=household.id,
            payload=AgentCreate(
                display_name="Intent Butler",
                agent_type="butler",
                self_identity="I route intents quickly",
                role_summary="Handle intent detection and chat",
                personality_traits=["calm"],
                service_focus=["问答"],
                default_entry=True,
            ),
        )
        self.db.flush()

        upsert_capability_route(
            self.db,
            AiCapabilityRouteUpsert(
                capability="text",
                household_id=household.id,
                primary_provider_profile_id=route_provider.id,
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
        upsert_agent_runtime_policy(
            self.db,
            household_id=household.id,
            agent_id=agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                routing_tags=["qa"],
                memory_scope=None,
                model_bindings=[{"capability": "intent_recognition", "provider_profile_id": bound_provider.id}],
                agent_skill_model_bindings=[],
            ),
        )
        self.db.flush()

        bound_plan = build_invocation_plan(
            self.db,
            capability="intent_recognition",
            household_id=household.id,
            agent_id=agent.id,
            request_payload={"request_context": {"effective_agent_id": agent.id}},
        )
        route_plan = build_invocation_plan(
            self.db,
            capability="intent_recognition",
            household_id=household.id,
            request_payload={"request_context": {}},
        )

        assert bound_plan.primary_provider is not None
        assert route_plan.primary_provider is not None
        self.assertEqual(bound_provider.id, bound_plan.primary_provider.provider_profile_id)
        self.assertEqual(route_provider.id, route_plan.primary_provider.provider_profile_id)

    def test_butler_bootstrap_requires_provider_first(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="No Provider Home", city="Suzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        with self.assertRaisesRegex(Exception, "AI"):
            start_butler_bootstrap_session(self.db, household_id=household.id)


class AiProviderAdapterCatalogTests(unittest.TestCase):
    def test_list_provider_adapters_reads_from_registered_plugins(self) -> None:
        fake_capability = SimpleNamespace(
            adapter_code="fake-provider",
            display_name="Fake Provider",
            field_schema=[
                {
                    "key": "secret_ref",
                    "label": "Secret Ref",
                    "field_type": "secret",
                    "required": True,
                    "options": [],
                }
            ],
            supported_model_types=["llm"],
            llm_workflow="openai_chat_completions",
            runtime_capability={
                "transport_type": "openai_compatible",
                "api_family": "openai_chat_completions",
                "default_privacy_level": "public_cloud",
                "default_supported_capabilities": ["text"],
            },
        )
        fake_plugin = SimpleNamespace(
            id="builtin.provider.fake-provider",
            name="Fake Provider",
            types=["ai-provider"],
            compatibility={"description": "fake plugin adapter"},
            capabilities=SimpleNamespace(ai_provider=fake_capability),
        )

        with patch(
            "app.modules.ai_gateway.provider_config_service.list_registered_plugins",
            return_value=SimpleNamespace(items=[fake_plugin]),
            create=True,
        ):
            with patch(
                "app.modules.ai_gateway.provider_config_service.list_registered_provider_adapters",
                side_effect=AssertionError("legacy provider registry should not be used"),
                create=True,
            ):
                adapters = list_provider_adapters()

        self.assertEqual(1, len(adapters))
        self.assertEqual("fake-provider", adapters[0].adapter_code)
        self.assertEqual("builtin.provider.fake-provider", adapters[0].plugin_id)


if __name__ == "__main__":
    unittest.main()

