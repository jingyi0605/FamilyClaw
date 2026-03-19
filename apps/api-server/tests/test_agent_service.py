import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.agent import repository as agent_repository
from app.modules.agent.schemas import AgentCreate, AgentRuntimePolicyUpsert, AgentSoulProfileUpsert
from app.modules.agent.service import (
    AgentNotFoundError,
    create_agent,
    resolve_effective_agent,
    upsert_agent_runtime_policy,
    upsert_agent_soul,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household


class AgentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Agent Service Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def _create_agent(self, *, display_name: str, default_entry: bool = False, self_identity: str | None = None):
        return create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name=display_name,
                agent_type="butler",
                self_identity=self_identity or f"我是{display_name}",
                role_summary=f"{display_name} 负责家庭事务",
                personality_traits=["细心"],
                service_focus=["家庭对话"],
                conversation_enabled=True,
                default_entry=default_entry,
                created_by="test",
            ),
        )

    def test_resolve_effective_agent_conversation_only_prefers_default_entry(self) -> None:
        primary = self._create_agent(display_name="主助手", default_entry=False)
        secondary = self._create_agent(display_name="默认助手", default_entry=False)
        third = self._create_agent(display_name="备用助手", default_entry=False)

        # 先把 secondary 设为 default_entry，验证优先级。
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=secondary.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=True,
                default_entry=True,
            ),
        )
        self.db.commit()

        resolved = resolve_effective_agent(
            self.db,
            household_id=self.household.id,
            conversation_only=True,
        )
        self.assertEqual(secondary.id, resolved.id)

        # 再关闭 secondary 对话能力，应该回退到 primary。
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=secondary.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=False,
                default_entry=False,
            ),
        )
        self.db.commit()
        resolved_after_disable = resolve_effective_agent(
            self.db,
            household_id=self.household.id,
            conversation_only=True,
        )
        self.assertEqual(primary.id, resolved_after_disable.id)

        # 再把 primary 置为 inactive，最终应按排序选到 third。
        agent_row = agent_repository.get_agent_by_household_and_id(
            self.db,
            household_id=self.household.id,
            agent_id=primary.id,
        )
        assert agent_row is not None
        agent_row.status = "inactive"
        self.db.flush()
        resolved_sort_fallback = resolve_effective_agent(
            self.db,
            household_id=self.household.id,
            conversation_only=True,
        )
        self.assertEqual(third.id, resolved_sort_fallback.id)

    def test_resolve_effective_agent_conversation_only_rejects_explicit_ineligible(self) -> None:
        target = self._create_agent(display_name="不可对话助手")
        upsert_agent_runtime_policy(
            self.db,
            household_id=self.household.id,
            agent_id=target.id,
            payload=AgentRuntimePolicyUpsert(
                conversation_enabled=False,
                default_entry=False,
            ),
        )
        self.db.commit()

        with self.assertRaises(AgentNotFoundError):
            resolve_effective_agent(
                self.db,
                household_id=self.household.id,
                agent_id=target.id,
                conversation_only=True,
            )

    def test_upsert_agent_soul_ignores_external_self_identity_update(self) -> None:
        created = self._create_agent(display_name="资料助手", self_identity="我是初始身份")
        self.db.commit()

        updated = upsert_agent_soul(
            self.db,
            household_id=self.household.id,
            agent_id=created.id,
            payload=AgentSoulProfileUpsert(
                self_identity="我是被外部覆盖的新身份",
                role_summary="新的角色摘要",
                intro_message="你好，我是新的简介",
                speaking_style="简洁",
                personality_traits=["直接"],
                service_focus=["问答"],
                created_by="test",
            ),
        )
        self.db.commit()

        self.assertEqual("我是初始身份", updated.self_identity)
        self.assertEqual("新的角色摘要", updated.role_summary)

    def test_runtime_policy_rejects_default_entry_when_conversation_disabled(self) -> None:
        created = self._create_agent(display_name="策略助手")
        self.db.commit()

        with self.assertRaises(HTTPException) as exc:
            upsert_agent_runtime_policy(
                self.db,
                household_id=self.household.id,
                agent_id=created.id,
                payload=AgentRuntimePolicyUpsert(
                    conversation_enabled=False,
                    default_entry=True,
                ),
            )
        self.assertEqual(409, exc.exception.status_code)


if __name__ == "__main__":
    unittest.main()
