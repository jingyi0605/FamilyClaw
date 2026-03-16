"""
Tests for channel member binding service.
"""

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
from app.modules.channel import repository as channel_repository
from app.modules.channel.binding_service import (
    MemberChannelBindingServiceError,
    UNBOUND_DIRECT_REPLY_TEXT,
    create_channel_account_binding,
    delete_channel_account_binding,
    list_channel_account_binding_candidates,
    list_channel_account_bindings,
    resolve_member_binding_for_inbound,
    update_channel_account_binding,
)
from app.modules.channel.models import ChannelInboundEvent, ChannelPluginAccount
from app.modules.channel.schemas import MemberChannelBindingCreate, MemberChannelBindingUpdate
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.region.schemas import RegionCatalogImportItem
from app.modules.region.service import import_region_catalog


class ChannelBindingTests(unittest.TestCase):
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
            ],
            source_version="test-v1",
        )
        self.db.commit()

        self.household = create_household(
            self.db,
            HouseholdCreate(
                name="Test Household",
                city="Beijing",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.db.commit()

        self.member1 = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="成员 1", role="adult"),
        )
        self.member2 = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="成员 2", role="adult"),
        )
        self.db.commit()

        self.account_a = self._create_test_channel_account(
            platform_code="telegram",
            account_code="telegram-a",
            display_name="Telegram Bot A",
        )
        self.account_b = self._create_test_channel_account(
            platform_code="telegram",
            account_code="telegram-b",
            display_name="Telegram Bot B",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_create_binding_success(self) -> None:
        payload = MemberChannelBindingCreate(
            channel_account_id=self.account_a.id,
            member_id=self.member1.id,
            external_user_id="  telegram_user_123  ",
            external_chat_id=" chat_789 ",
            display_hint=" 妈妈的 Telegram ",
        )

        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        self.assertEqual(result.member_id, self.member1.id)
        self.assertEqual(result.channel_account_id, self.account_a.id)
        self.assertEqual(result.external_user_id, "telegram_user_123")
        self.assertEqual(result.external_chat_id, "chat_789")
        self.assertEqual(result.display_hint, "妈妈的 Telegram")
        self.assertEqual(result.binding_status, "active")

    def test_same_channel_account_rejects_duplicate_external_user(self) -> None:
        payload = MemberChannelBindingCreate(
            channel_account_id=self.account_a.id,
            member_id=self.member1.id,
            external_user_id="same-user",
        )
        create_channel_account_binding(self.db, household_id=self.household.id, payload=payload)
        self.db.commit()

        with self.assertRaises(MemberChannelBindingServiceError):
            create_channel_account_binding(
                self.db,
                household_id=self.household.id,
                payload=MemberChannelBindingCreate(
                    channel_account_id=self.account_a.id,
                    member_id=self.member2.id,
                    external_user_id="same-user",
                ),
            )

    def test_same_household_different_account_allows_same_external_user(self) -> None:
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="shared-user",
            ),
        )
        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_b.id,
                member_id=self.member2.id,
                external_user_id="shared-user",
            ),
        )
        self.db.commit()

        self.assertEqual(result.channel_account_id, self.account_b.id)
        self.assertEqual(result.member_id, self.member2.id)

    def test_list_channel_account_bindings_returns_only_current_account(self) -> None:
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="user-a",
            ),
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_b.id,
                member_id=self.member2.id,
                external_user_id="user-b",
            ),
        )
        self.db.commit()

        result = list_channel_account_bindings(
            self.db,
            household_id=self.household.id,
            account_id=self.account_a.id,
        )

        self.assertEqual(1, len(result))
        self.assertEqual("user-a", result[0].external_user_id)

    def test_update_binding_detects_conflict_within_same_account(self) -> None:
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="user-one",
            ),
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member2.id,
                external_user_id="user-two",
            ),
        )
        self.db.commit()

        with self.assertRaises(MemberChannelBindingServiceError):
            update_channel_account_binding(
                self.db,
                household_id=self.household.id,
                account_id=self.account_a.id,
                binding_id=binding.id,
                payload=MemberChannelBindingUpdate(external_user_id="user-one"),
            )

    def test_resolve_binding_uses_channel_account_id(self) -> None:
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="shared-user",
            ),
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_b.id,
                member_id=self.member2.id,
                external_user_id="shared-user",
            ),
        )
        self.db.commit()

        result_a = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account_a.id,
            external_user_id="shared-user",
            chat_type="direct",
        )
        result_b = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account_b.id,
            external_user_id="shared-user",
            chat_type="direct",
        )

        self.assertTrue(result_a.matched)
        self.assertTrue(result_b.matched)
        self.assertEqual(self.member1.id, result_a.member_id)
        self.assertEqual(self.member2.id, result_b.member_id)

    def test_resolve_binding_ignores_disabled_binding(self) -> None:
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="disabled-user",
            ),
        )
        self.db.commit()

        update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.account_a.id,
            binding_id=binding.id,
            payload=MemberChannelBindingUpdate(binding_status="disabled"),
        )
        self.db.commit()

        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account_a.id,
            external_user_id="disabled-user",
            chat_type="direct",
        )

        self.assertFalse(result.matched)
        self.assertEqual("direct_unbound_prompt", result.strategy)
        self.assertEqual(UNBOUND_DIRECT_REPLY_TEXT, result.reply_text)

    def test_delete_binding_removes_record_and_unbinds_future_message(self) -> None:
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="delete-user",
            ),
        )
        self.db.commit()

        delete_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.account_a.id,
            binding_id=binding.id,
        )
        self.db.commit()

        bindings = list_channel_account_bindings(
            self.db,
            household_id=self.household.id,
            account_id=self.account_a.id,
        )
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account_a.id,
            external_user_id="delete-user",
            chat_type="direct",
        )

        self.assertEqual([], bindings)
        self.assertFalse(result.matched)
        self.assertEqual("direct_unbound_prompt", result.strategy)

    def test_resolve_binding_for_unbound_group_chat(self) -> None:
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.account_a.id,
            external_user_id="unknown-user",
            chat_type="group",
        )

        self.assertFalse(result.matched)
        self.assertEqual("group_unbound_ignore", result.strategy)
        self.assertIsNone(result.reply_text)

    def test_binding_candidates_keep_latest_message_and_exclude_bound_user(self) -> None:
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=MemberChannelBindingCreate(
                channel_account_id=self.account_a.id,
                member_id=self.member1.id,
                external_user_id="bound-user",
            ),
        )
        self.db.flush()

        self._create_candidate_event(
            account=self.account_a,
            external_event_id="evt-001",
            external_user_id="candidate-user",
            received_at="2026-03-16T10:00:00Z",
            text="第一条消息",
            chat_id="chat-001",
            username="candidate_old",
            sender_display_name="候选人",
        )
        self._create_candidate_event(
            account=self.account_a,
            external_event_id="evt-002",
            external_user_id="candidate-user",
            received_at="2026-03-16T10:05:00Z",
            text="第二条消息",
            chat_id="chat-001",
            username="candidate_new",
            sender_display_name="候选人",
        )
        self._create_candidate_event(
            account=self.account_a,
            external_event_id="evt-003",
            external_user_id="bound-user",
            received_at="2026-03-16T10:06:00Z",
            text="已绑定用户消息",
            chat_id="chat-002",
            username="bound",
            sender_display_name="已绑定",
        )
        self._create_candidate_event(
            account=self.account_b,
            external_event_id="evt-004",
            external_user_id="candidate-user",
            received_at="2026-03-16T10:07:00Z",
            text="另一个账号的消息",
            chat_id="chat-003",
            username="account_b",
            sender_display_name="另一个账号候选",
        )
        self.db.commit()

        result_a = list_channel_account_binding_candidates(
            self.db,
            household_id=self.household.id,
            account_id=self.account_a.id,
        )
        result_b = list_channel_account_binding_candidates(
            self.db,
            household_id=self.household.id,
            account_id=self.account_b.id,
        )

        self.assertEqual(1, len(result_a))
        self.assertEqual("candidate-user", result_a[0].external_user_id)
        self.assertEqual("第二条消息", result_a[0].last_message_text)
        self.assertEqual("candidate_new", result_a[0].username)
        self.assertEqual("chat-001", result_a[0].external_chat_id)

        self.assertEqual(1, len(result_b))
        self.assertEqual("candidate-user", result_b[0].external_user_id)
        self.assertEqual("另一个账号的消息", result_b[0].last_message_text)
        self.assertEqual(self.account_b.id, result_b[0].channel_account_id)

    def _create_test_channel_account(
        self,
        *,
        platform_code: str,
        account_code: str,
        display_name: str,
    ) -> ChannelPluginAccount:
        now = utc_now_iso()
        account = ChannelPluginAccount(
            id=new_uuid(),
            household_id=self.household.id,
            plugin_id=f"builtin/channel_{platform_code}",
            platform_code=platform_code,
            account_code=account_code,
            display_name=display_name,
            connection_mode="webhook",
            config_json="{}",
            status="active",
            created_at=now,
            updated_at=now,
        )
        channel_repository.add_channel_plugin_account(self.db, account)
        return account

    def _create_candidate_event(
        self,
        *,
        account: ChannelPluginAccount,
        external_event_id: str,
        external_user_id: str,
        received_at: str,
        text: str,
        chat_id: str,
        username: str | None,
        sender_display_name: str | None,
    ) -> None:
        row = ChannelInboundEvent(
            id=new_uuid(),
            household_id=self.household.id,
            channel_account_id=account.id,
            platform_code=account.platform_code,
            external_event_id=external_event_id,
            event_type="message",
            external_user_id=external_user_id,
            external_conversation_key=f"chat:{chat_id}",
            normalized_payload_json=(
                "{"
                f"\"text\":\"{text}\","
                "\"chat_type\":\"direct\","
                f"\"sender_display_name\":{self._to_json_value(sender_display_name)},"
                f"\"metadata\":{{\"chat_id\":\"{chat_id}\",\"message_id\":\"{external_event_id}\",\"username\":{self._to_json_value(username)}}}"
                "}"
            ),
            status="ignored",
            conversation_session_id=None,
            error_code="channel_member_binding_not_found",
            error_message="direct member binding is missing",
            received_at=received_at,
            processed_at=received_at,
        )
        channel_repository.add_channel_inbound_event(self.db, row)

    def _to_json_value(self, value: str | None) -> str:
        if value is None:
            return "null"
        return f"\"{value}\""


if __name__ == "__main__":
    unittest.main()
