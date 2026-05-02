import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.db.utils import dump_json, new_uuid, utc_now_iso
from app.modules.agent import repository as agent_repository
from app.modules.agent.schemas import AgentCreate, AgentRuntimePolicyUpsert
from app.modules.agent.service import create_agent, upsert_agent_runtime_policy
from app.modules.conversation import repository as conversation_repository
from app.modules.conversation.models import ConversationProposalBatch, ConversationProposalItem
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import (
    _apply_config_proposal_item,
    _apply_policy_to_proposal_batch,
    create_conversation_session,
    delete_conversation_session,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Conversation Service Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        self.actor = ActorContext(
            role="admin",
            actor_type="member",
            actor_id=self.member.id,
            account_id="account-1",
            account_type="household",
            account_status="active",
            username="owner",
            household_id=self.household.id,
            member_id=self.member.id,
            member_role="admin",
            is_authenticated=True,
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="对话助手",
                agent_type="butler",
                self_identity="我是对话助手",
                role_summary="负责家庭对话",
                intro_message="你好",
                speaking_style="温和",
                personality_traits=["细心"],
                service_focus=["问答"],
                default_entry=True,
                conversation_enabled=True,
                created_by="test",
            ),
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_create_conversation_session_rejects_ineligible_explicit_agent(self) -> None:
        disabled_agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="禁用助手",
                agent_type="butler",
                self_identity="我是禁用助手",
                role_summary="禁用测试",
                personality_traits=["稳重"],
                service_focus=["问答"],
                default_entry=False,
                conversation_enabled=True,
                created_by="test",
            ),
        )
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=disabled_agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=False,
                default_entry=False,
            ),
        )
        self.db.commit()

        with self.assertRaises(HTTPException) as exc:
            create_conversation_session(
                self.db,
                payload=ConversationSessionCreate(
                    household_id=self.household.id,
                    active_agent_id=disabled_agent.id,
                ),
                actor=self.actor,
            )
        self.assertEqual(409, exc.exception.status_code)

    def test_delete_conversation_session_removes_session(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        self.db.commit()

        deleted = delete_conversation_session(
            self.db,
            session_id=session.id,
            actor=self.actor,
        )
        self.db.commit()

        self.assertEqual(session.id, deleted.id)
        self.assertIsNone(conversation_repository.get_session(self.db, session.id))

    def test_delete_conversation_session_rejects_processing_session(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        session_row = conversation_repository.get_session(self.db, session.id)
        assert session_row is not None
        session_row.current_request_id = "req-processing"
        self.db.commit()

        with self.assertRaises(HTTPException) as exc:
            delete_conversation_session(
                self.db,
                session_id=session.id,
                actor=self.actor,
            )
        self.assertEqual(409, exc.exception.status_code)
        self.assertIsNotNone(conversation_repository.get_session(self.db, session.id))

    def test_apply_config_proposal_item_updates_whitelisted_fields_only(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        session_row = conversation_repository.get_session(self.db, session.id)
        assert session_row is not None

        _apply_config_proposal_item(
            self.db,
            session=session_row,
            payload={
                "display_name": "新的助手名",
                "role_summary": "新的角色摘要",
                "intro_message": "新的简介",
                "speaking_style": "直接",
                "personality_traits": ["冷静", "有条理"],
                "service_focus": ["家庭事务", "提醒"],
                # 非白名单字段，必须被忽略。
                "self_identity": "不应该被覆盖",
                "routing_tags": ["internal"],
            },
        )
        self.db.commit()

        agent_row = agent_repository.get_agent_by_household_and_id(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
        )
        assert agent_row is not None
        soul = agent_repository.get_active_soul_profile(self.db, agent_id=self.agent.id)
        assert soul is not None

        self.assertEqual("新的助手名", agent_row.display_name)
        self.assertEqual("新的角色摘要", soul.role_summary)
        self.assertEqual("新的简介", soul.intro_message)
        self.assertEqual("直接", soul.speaking_style)
        self.assertEqual("我是对话助手", soul.self_identity)

    def test_apply_policy_to_proposal_batch_distinguishes_notify_and_auto(self) -> None:
        session_detail = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        session = conversation_repository.get_session(self.db, session_detail.id)
        assert session is not None

        # notify 模式
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                autonomous_action_policy={"memory": "ask", "config": "notify", "action": "ask"},
            ),
        )
        notify_batch_id = self._create_config_batch(session_id=session.id, request_id="req-notify", display_name="通知模式助手")
        _apply_policy_to_proposal_batch(
            self.db,
            session=session,
            batch_id=notify_batch_id,
            request_id="req-notify",
            actor=self.actor,
        )
        self.db.commit()

        notify_logs = list(conversation_repository.list_debug_logs(self.db, session_id=session.id, request_id="req-notify", limit=50))
        notify_stages = {item.stage for item in notify_logs}
        self.assertIn("proposal.item.executed_notify", notify_stages)

        # auto 模式
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=self.agent.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
                autonomous_action_policy={"memory": "ask", "config": "auto", "action": "ask"},
            ),
        )
        auto_batch_id = self._create_config_batch(session_id=session.id, request_id="req-auto", display_name="自动模式助手")
        _apply_policy_to_proposal_batch(
            self.db,
            session=session,
            batch_id=auto_batch_id,
            request_id="req-auto",
            actor=self.actor,
        )
        self.db.commit()

        auto_logs = list(conversation_repository.list_debug_logs(self.db, session_id=session.id, request_id="req-auto", limit=50))
        auto_stages = {item.stage for item in auto_logs}
        self.assertIn("proposal.item.executed_auto", auto_stages)

    def _create_config_batch(self, *, session_id: str, request_id: str, display_name: str) -> str:
        now = utc_now_iso()
        batch = ConversationProposalBatch(
            id=new_uuid(),
            session_id=session_id,
            request_id=request_id,
            source_message_ids_json="[]",
            source_roles_json="[]",
            lane_json='{"lane":"free_chat"}',
            status="pending_policy",
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_proposal_batch(self.db, batch)
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind="config_apply",
            policy_category="ask",
            status="pending_policy",
            title="应用配置",
            summary="测试配置执行策略",
            evidence_message_ids_json="[]",
            evidence_roles_json="[]",
            dedupe_key=f"config:{request_id}",
            confidence=0.9,
            payload_json=dump_json({"display_name": display_name}) or "{}",
            created_at=now,
            updated_at=now,
        )
        conversation_repository.add_proposal_item(self.db, item)
        self.db.flush()
        return batch.id


if __name__ == "__main__":
    unittest.main()
