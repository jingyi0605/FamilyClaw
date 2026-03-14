import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.channel.models import (
    ChannelConversationBinding,
    ChannelDelivery,
    ChannelInboundEvent,
    ChannelPluginAccount,
    MemberChannelBinding,
)
from app.modules.channel.repository import (
    add_channel_conversation_binding,
    add_channel_delivery,
    add_channel_inbound_event,
    add_channel_plugin_account,
    add_member_channel_binding,
    get_channel_conversation_binding_by_external_key,
    get_channel_inbound_event_by_external_event,
    get_member_channel_binding_by_external_user,
    list_channel_deliveries,
    list_channel_plugin_accounts,
    list_member_channel_bindings,
)
from app.modules.conversation.models import ConversationMessage, ConversationSession
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class ChannelRepositoryTests(unittest.TestCase):
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

    def test_channel_account_and_member_binding_constraints(self) -> None:
        household, member = self._create_household_and_member()
        account = self._create_channel_account(household_id=household.id)
        self.db.flush()

        accounts = list_channel_plugin_accounts(self.db, household_id=household.id)
        self.assertEqual(1, len(accounts))
        self.assertEqual(account.id, accounts[0].id)

        binding = MemberChannelBinding(
            id=new_uuid(),
            household_id=household.id,
            member_id=member.id,
            channel_account_id=account.id,
            platform_code="telegram",
            external_user_id="tg-user-001",
            external_chat_id="tg-chat-001",
            display_hint="妈妈的 Telegram",
            binding_status="active",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_member_channel_binding(self.db, binding)
        self.db.flush()

        bindings = list_member_channel_bindings(self.db, member_id=member.id)
        self.assertEqual(1, len(bindings))
        matched = get_member_channel_binding_by_external_user(
            self.db,
            household_id=household.id,
            platform_code="telegram",
            external_user_id="tg-user-001",
        )
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(member.id, matched.member_id)
        self.db.commit()

        duplicate_account = ChannelPluginAccount(
            id=new_uuid(),
            household_id=household.id,
            plugin_id="channel-telegram",
            platform_code="telegram",
            account_code=account.account_code,
            display_name="重复账号",
            connection_mode="webhook",
            config_json="{}",
            status="draft",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_channel_plugin_account(self.db, duplicate_account)
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

        account = self._reload_channel_account(account.id)
        duplicate_binding = MemberChannelBinding(
            id=new_uuid(),
            household_id=household.id,
            member_id=member.id,
            channel_account_id=account.id,
            platform_code="telegram",
            external_user_id="tg-user-001",
            external_chat_id="tg-chat-002",
            display_hint="重复绑定",
            binding_status="active",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_member_channel_binding(self.db, duplicate_binding)
        with self.assertRaises(IntegrityError):
            self.db.flush()

    def test_channel_conversation_event_and_delivery_records(self) -> None:
        household, member = self._create_household_and_member()
        account = self._create_channel_account(household_id=household.id)
        session, assistant_message = self._create_conversation_fixture(
            household_id=household.id,
            member_id=member.id,
        )
        self.db.flush()

        conversation_binding = ChannelConversationBinding(
            id=new_uuid(),
            household_id=household.id,
            channel_account_id=account.id,
            platform_code="telegram",
            external_conversation_key="chat:12345",
            external_user_id="tg-user-001",
            member_id=member.id,
            conversation_session_id=session.id,
            active_agent_id=None,
            last_message_at=utc_now_iso(),
            status="active",
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_channel_conversation_binding(self.db, conversation_binding)

        inbound_event = ChannelInboundEvent(
            id=new_uuid(),
            household_id=household.id,
            channel_account_id=account.id,
            platform_code="telegram",
            external_event_id="evt-001",
            event_type="message",
            external_user_id="tg-user-001",
            external_conversation_key="chat:12345",
            normalized_payload_json='{"text":"你好"}',
            status="matched",
            conversation_session_id=session.id,
            error_code=None,
            error_message=None,
            received_at=utc_now_iso(),
            processed_at=utc_now_iso(),
        )
        add_channel_inbound_event(self.db, inbound_event)

        delivery = ChannelDelivery(
            id=new_uuid(),
            household_id=household.id,
            channel_account_id=account.id,
            platform_code="telegram",
            conversation_session_id=session.id,
            assistant_message_id=assistant_message.id,
            external_conversation_key="chat:12345",
            delivery_type="reply",
            request_payload_json='{"text":"收到"}',
            provider_message_ref="provider-msg-001",
            status="sent",
            attempt_count=1,
            last_error_code=None,
            last_error_message=None,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_channel_delivery(self.db, delivery)
        self.db.flush()

        matched_binding = get_channel_conversation_binding_by_external_key(
            self.db,
            household_id=household.id,
            channel_account_id=account.id,
            external_conversation_key="chat:12345",
        )
        self.assertIsNotNone(matched_binding)
        assert matched_binding is not None
        self.assertEqual(session.id, matched_binding.conversation_session_id)

        matched_event = get_channel_inbound_event_by_external_event(
            self.db,
            household_id=household.id,
            channel_account_id=account.id,
            external_event_id="evt-001",
        )
        self.assertIsNotNone(matched_event)
        assert matched_event is not None
        self.assertEqual("matched", matched_event.status)

        deliveries = list_channel_deliveries(self.db, household_id=household.id)
        self.assertEqual(1, len(deliveries))
        self.assertEqual(assistant_message.id, deliveries[0].assistant_message_id)
        self.assertEqual("sent", deliveries[0].status)

    def _create_household_and_member(self):
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Channel Home",
                city="Shanghai",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.flush()
        member = create_member(
            self.db,
            MemberCreate(
                household_id=household.id,
                name="妈妈",
                role="adult",
            ),
        )
        self.db.flush()
        return household, member

    def _create_channel_account(self, *, household_id: str) -> ChannelPluginAccount:
        account = ChannelPluginAccount(
            id=new_uuid(),
            household_id=household_id,
            plugin_id="channel-telegram",
            platform_code="telegram",
            account_code="telegram-main",
            display_name="Telegram 主账号",
            connection_mode="webhook",
            config_json="{}",
            status="draft",
            last_probe_status=None,
            last_error_code=None,
            last_error_message=None,
            last_inbound_at=None,
            last_outbound_at=None,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        add_channel_plugin_account(self.db, account)
        return account

    def _create_conversation_fixture(self, *, household_id: str, member_id: str):
        now = utc_now_iso()
        session = ConversationSession(
            id=new_uuid(),
            household_id=household_id,
            requester_member_id=member_id,
            session_mode="family_chat",
            active_agent_id=None,
            current_request_id=None,
            last_event_seq=0,
            title="外部会话",
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(session)

        assistant_message = ConversationMessage(
            id=new_uuid(),
            session_id=session.id,
            request_id="req-001",
            seq=1,
            role="assistant",
            message_type="text",
            content="收到",
            status="completed",
            effective_agent_id=None,
            ai_provider_code=None,
            ai_trace_id=None,
            degraded=False,
            error_code=None,
            facts_json=None,
            suggestions_json=None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(assistant_message)
        return session, assistant_message

    def _reload_channel_account(self, account_id: str) -> ChannelPluginAccount:
        account = self.db.get(ChannelPluginAccount, account_id)
        assert account is not None
        return account


if __name__ == "__main__":
    unittest.main()
