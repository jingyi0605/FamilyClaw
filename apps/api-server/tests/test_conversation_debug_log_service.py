import tempfile
import unittest

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext
from app.core.config import settings
from app.modules.agent.schemas import AgentCreate
from app.modules.agent.service import create_agent
from app.modules.conversation.schemas import ConversationSessionCreate
from app.modules.conversation.service import (
    append_conversation_debug_log,
    create_conversation_session,
    list_conversation_debug_logs,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ConversationDebugLogServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db = self._db_helper.SessionLocal()

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Debug Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Owner", role="admin"),
        )
        self.agent = create_agent(
            self.db,
            household_id=self.household.id,
            payload=AgentCreate(
                display_name="管家",
                agent_type="butler",
                self_identity="我是家庭管家。",
                role_summary="负责家庭问答",
                personality_traits=["细心"],
                service_focus=["家庭问答"],
                default_entry=True,
            ),
        )
        self.db.commit()
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

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_append_conversation_debug_log_persists_entry_when_enabled(self) -> None:
        session = create_conversation_session(
            self.db,
            payload=ConversationSessionCreate(
                household_id=self.household.id,
                active_agent_id=self.agent.id,
            ),
            actor=self.actor,
        )
        previous = settings.conversation_debug_log_enabled
        try:
            settings.conversation_debug_log_enabled = True
            appended = append_conversation_debug_log(
                self.db,
                session_id=session.id,
                request_id="request-debug-log-1",
                stage="voice.identity.resolved",
                source="voice",
                message="已完成声纹识别与身份决策。",
                payload={
                    "identity_status": "resolved",
                    "requester_member_id": self.member.id,
                    "voiceprint_hint": {"status": "matched", "provider": "mock"},
                },
            )
            self.db.commit()

            self.assertTrue(appended)
            debug_logs = list_conversation_debug_logs(
                self.db,
                session_id=session.id,
                actor=self.actor,
                request_id="request-debug-log-1",
            )
            self.assertEqual(1, len(debug_logs.items))
            self.assertEqual("voice.identity.resolved", debug_logs.items[0].stage)
            self.assertEqual("resolved", debug_logs.items[0].payload["identity_status"])
            self.assertEqual(self.member.id, debug_logs.items[0].payload["requester_member_id"])
        finally:
            settings.conversation_debug_log_enabled = previous


if __name__ == "__main__":
    unittest.main()
