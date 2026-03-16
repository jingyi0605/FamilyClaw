import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.channel.models import ChannelInboundEvent, ChannelPluginAccount
from app.modules.conversation.models import ConversationSession
from app.modules.conversation.repository import list_turn_sources
from app.modules.conversation.service import record_conversation_turn_source
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.voice.repository import list_voice_terminal_conversation_bindings
from app.modules.voice.service import bind_voice_terminal_conversation, get_active_voice_terminal_conversation_binding


class NonWebConversationDataTests(unittest.TestCase):
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

        self.household = create_household(
            self.db,
            HouseholdCreate(name="Data Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="婵″牆顩?, role="adult"),
        )
        now = utc_now_iso()
        self.session_one = ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=None,
            current_request_id=None,
            last_event_seq=0,
            title="閸︾儤娅欐稉鈧?,
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session_two = ConversationSession(
            id=new_uuid(),
            household_id=self.household.id,
            requester_member_id=self.member.id,
            session_mode="family_chat",
            active_agent_id=None,
            current_request_id=None,
            last_event_seq=0,
            title="閸︾儤娅欐禍?",
            status="active",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        self.account = ChannelPluginAccount(
            id=new_uuid(),
            household_id=self.household.id,
            plugin_id="channel-telegram",
            platform_code="telegram",
            account_code="telegram-main",
            display_name="Telegram 娑撴槒澶勯崣?",
            connection_mode="polling",
            config_json="{}",
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.inbound_event = ChannelInboundEvent(
            id=new_uuid(),
            household_id=self.household.id,
            channel_account_id=self.account.id,
            platform_code="telegram",
            external_event_id="evt-data-001",
            event_type="message",
            external_user_id="tg-user-001",
            external_conversation_key="chat:data",
            normalized_payload_json='{"text":"娴ｇ姴銈?}',
            status="received",
            conversation_session_id=None,
            error_code=None,
            error_message=None,
            received_at=now,
            processed_at=None,
        )
        self.db.add_all([self.session_one, self.session_two, self.account, self.inbound_event])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_record_conversation_turn_source_is_idempotent_per_turn(self) -> None:
        first = record_conversation_turn_source(
            self.db,
            conversation_session_id=self.session_one.id,
            conversation_turn_id="turn-001",
            source_kind="channel",
            platform_code="telegram",
            channel_account_id=self.account.id,
            external_conversation_key="chat:data",
            thread_key="9",
            channel_inbound_event_id=self.inbound_event.id,
        )
        second = record_conversation_turn_source(
            self.db,
            conversation_session_id=self.session_one.id,
            conversation_turn_id="turn-001",
            source_kind="channel",
            platform_code="telegram",
            channel_account_id=self.account.id,
            external_conversation_key="chat:data",
            thread_key="9",
            channel_inbound_event_id=self.inbound_event.id,
        )
        self.db.commit()

        self.assertEqual(first.id, second.id)
        rows = list_turn_sources(self.db, session_id=self.session_one.id)
        self.assertEqual(1, len(rows))
        self.assertEqual("channel", rows[0].source_kind)
        self.assertEqual("telegram", rows[0].platform_code)
        self.assertEqual("9", rows[0].thread_key)

    def test_bind_voice_terminal_conversation_updates_existing_binding(self) -> None:
        first = bind_voice_terminal_conversation(
            self.db,
            household_id=self.household.id,
            terminal_type="open_xiaoai",
            terminal_code="living-room-speaker",
            conversation_session_id=self.session_one.id,
            member_id=self.member.id,
            last_message_at="2026-03-16T10:00:00+08:00",
        )
        second = bind_voice_terminal_conversation(
            self.db,
            household_id=self.household.id,
            terminal_type="open_xiaoai",
            terminal_code="living-room-speaker",
            conversation_session_id=self.session_two.id,
            member_id=None,
            last_message_at="2026-03-16T10:05:00+08:00",
        )
        self.db.commit()

        self.assertEqual(first.id, second.id)
        active = get_active_voice_terminal_conversation_binding(
            self.db,
            household_id=self.household.id,
            terminal_type="open_xiaoai",
            terminal_code="living-room-speaker",
        )
        assert active is not None
        self.assertEqual(self.session_two.id, active.conversation_session_id)
        self.assertEqual(self.member.id, active.member_id)
        self.assertEqual("2026-03-16T10:05:00+08:00", active.last_message_at)
        rows = list_voice_terminal_conversation_bindings(self.db, household_id=self.household.id)
        self.assertEqual(1, len(rows))


if __name__ == "__main__":
    unittest.main()

