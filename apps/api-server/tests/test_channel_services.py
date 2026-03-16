import json
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
from app.modules.channel.schemas import (
    ChannelAccountCreate,
    ChannelAccountUpdate,
    ChannelDeliveryCreate,
    ChannelInboundEventCreate,
    MemberChannelBindingCreate,
    MemberChannelBindingUpdate,
)
from app.modules.channel.service import (
    ChannelAccountServiceError,
    ChannelServiceError,
    MemberChannelBindingServiceError,
    create_channel_account,
    create_channel_delivery,
    create_member_binding,
    list_channel_accounts,
    list_channel_delivery_records,
    list_member_bindings,
    list_recorded_channel_inbound_events,
    record_channel_inbound_event,
    update_channel_account,
    update_member_binding,
)
from app.modules.conversation.models import ConversationMessage, ConversationSession
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class ChannelServiceTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        self._tempdir.cleanup()

    def test_create_and_update_channel_account_uses_channel_plugin_manifest(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Channel Service Home", city="Hangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_channel_plugin(Path(plugin_tempdir), plugin_id="telegram-channel-plugin")
            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path="python",
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.flush()

            created = create_channel_account(
                self.db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="telegram-channel-plugin",
                    display_name="Telegram 涓昏处鍙?,
                    connection_mode="webhook",
                    config={"token": "test-token"},
                    status="draft",
                ),
            )
            self.assertEqual("telegram", created.platform_code)
            self.assertEqual("telegram-channel-plugin", created.plugin_id)
            self.assertEqual({"token": "test-token"}, created.config)
            self.assertTrue(created.account_code.startswith("telegram-account-"))

            updated = update_channel_account(
                self.db,
                household_id=household.id,
                account_id=created.id,
                payload=ChannelAccountUpdate(
                    connection_mode="polling",
                    status="active",
                    last_probe_status="ok",
                ),
            )
            self.assertEqual("polling", updated.connection_mode)
            self.assertEqual("active", updated.status)
            self.assertEqual("ok", updated.last_probe_status)

            accounts = list_channel_accounts(self.db, household_id=household.id)
            self.assertEqual(1, len(accounts))
            self.assertEqual(created.id, accounts[0].id)
            self.assertEqual(created.account_code, accounts[0].account_code)

            with self.assertRaises(ChannelAccountServiceError):
                create_channel_account(
                    self.db,
                    household_id=household.id,
                    payload=ChannelAccountCreate(
                        plugin_id="telegram-channel-plugin",
                        account_code="telegram-invalid",
                        display_name="闈炴硶妯″紡璐﹀彿",
                        connection_mode="websocket",
                        config={},
                    ),
                )

    def test_binding_inbound_idempotency_and_delivery_use_unified_service(self) -> None:
        household = create_household(
            self.db,
            HouseholdCreate(name="Channel Binding Home", city="Suzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.flush()
        member = create_member(
            self.db,
            MemberCreate(
                household_id=household.id,
                name="鐖哥埜",
                role="adult",
            ),
        )
        self.db.flush()

        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_channel_plugin(Path(plugin_tempdir), plugin_id="telegram-channel-plugin")
            register_plugin_mount(
                self.db,
                household_id=household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path="python",
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.flush()

            account = create_channel_account(
                self.db,
                household_id=household.id,
                payload=ChannelAccountCreate(
                    plugin_id="telegram-channel-plugin",
                    account_code="telegram-main",
                    display_name="Telegram 涓昏处鍙?,
                    connection_mode="webhook",
                    config={"token": "token"},
                ),
            )

            binding = create_member_binding(
                self.db,
                member_id=member.id,
                payload=MemberChannelBindingCreate(
                    channel_account_id=account.id,
                    member_id=member.id,
                    external_user_id="tg-user-001",
                    external_chat_id="chat-001",
                    display_hint="鐖哥埜鐨?Telegram",
                ),
            )
            self.assertEqual("telegram", binding.platform_code)

            updated_binding = update_member_binding(
                self.db,
                member_id=member.id,
                binding_id=binding.id,
                payload=MemberChannelBindingUpdate(
                    display_hint="鏂扮殑澶囨敞",
                    binding_status="disabled",
                ),
            )
            self.assertEqual("鏂扮殑澶囨敞", updated_binding.display_hint)
            self.assertEqual("disabled", updated_binding.binding_status)

            bindings = list_member_bindings(self.db, member_id=member.id)
            self.assertEqual(1, len(bindings))

            session, assistant_message = self._create_conversation_fixture(
                household_id=household.id,
                member_id=member.id,
            )
            self.db.flush()

            first_event, created = record_channel_inbound_event(
                self.db,
                payload=ChannelInboundEventCreate(
                    household_id=household.id,
                    channel_account_id=account.id,
                    external_event_id="evt-001",
                    event_type="message",
                    external_user_id="tg-user-001",
                    external_conversation_key="chat:12345",
                    normalized_payload={"text": "浣犲ソ"},
                    status="received",
                    conversation_session_id=session.id,
                ),
            )
            self.assertTrue(created)

            second_event, created_again = record_channel_inbound_event(
                self.db,
                payload=ChannelInboundEventCreate(
                    household_id=household.id,
                    channel_account_id=account.id,
                    external_event_id="evt-001",
                    event_type="message",
                    external_user_id="tg-user-001",
                    external_conversation_key="chat:12345",
                    normalized_payload={"text": "閲嶅"},
                    status="matched",
                    conversation_session_id=session.id,
                ),
            )
            self.assertFalse(created_again)
            self.assertEqual(first_event.id, second_event.id)

            inbound_events = list_recorded_channel_inbound_events(self.db, household_id=household.id)
            self.assertEqual(1, len(inbound_events))

            delivery = create_channel_delivery(
                self.db,
                payload=ChannelDeliveryCreate(
                    household_id=household.id,
                    channel_account_id=account.id,
                    conversation_session_id=session.id,
                    assistant_message_id=assistant_message.id,
                    external_conversation_key="chat:12345",
                    delivery_type="reply",
                    request_payload={"text": "鏀跺埌"},
                    status="sent",
                    attempt_count=1,
                ),
            )
            self.assertEqual("telegram", delivery.platform_code)
            self.assertEqual("sent", delivery.status)

            deliveries = list_channel_delivery_records(self.db, household_id=household.id)
            self.assertEqual(1, len(deliveries))

            with self.assertRaises(MemberChannelBindingServiceError):
                create_member_binding(
                    self.db,
                    member_id=member.id,
                    payload=MemberChannelBindingCreate(
                        channel_account_id=account.id,
                        member_id=member.id,
                        external_user_id="tg-user-001",
                    ),
                )

            with self.assertRaises(ChannelServiceError):
                create_channel_delivery(
                    self.db,
                    payload=ChannelDeliveryCreate(
                        household_id=household.id,
                        channel_account_id=account.id,
                        conversation_session_id=session.id,
                        assistant_message_id=new_uuid(),
                        external_conversation_key="chat:12345",
                        delivery_type="reply",
                        request_payload={"text": "bad"},
                    ),
                )

    def _create_channel_plugin(self, root: Path, *, plugin_id: str) -> Path:
        plugin_root = root / plugin_id
        plugin_root.mkdir(parents=True)
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "Telegram 閫氶亾鎻掍欢",
                    "version": "0.1.0",
                    "types": ["channel"],
                    "permissions": ["channel.receive", "channel.send"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"channel": "plugin.channel.handle"},
                    "capabilities": {
                        "channel": {
                            "platform_code": "telegram",
                            "inbound_modes": ["webhook", "polling"],
                            "delivery_modes": ["reply", "push"],
                            "supports_member_binding": True,
                            "supports_group_chat": True,
                            "supports_threading": True,
                            "reserved": False,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return plugin_root

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
            title="娓犻亾浼氳瘽",
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
            content="鏀跺埌",
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


if __name__ == "__main__":
    unittest.main()

