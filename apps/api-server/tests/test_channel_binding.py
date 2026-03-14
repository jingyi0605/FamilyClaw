"""
Tests for channel member binding service.

Tests cover:
- Creating bindings from channel account perspective
- Updating bindings from channel account perspective
- Listing bindings for a channel account
- External user ID conflict detection
- Member household validation
- Binding resolution for inbound messages
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
from app.modules.channel import repository as channel_repository
from app.modules.channel.binding_service import (
    create_channel_account_binding,
    list_channel_account_bindings,
    update_channel_account_binding,
    resolve_member_binding_for_inbound,
    MemberChannelBindingServiceError,
    UNBOUND_DIRECT_REPLY_TEXT,
)
from app.modules.channel.models import ChannelPluginAccount
from app.modules.channel.schemas import (
    MemberChannelBindingCreate,
    MemberChannelBindingUpdate,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.region.schemas import RegionCatalogImportItem
from app.modules.region.service import import_region_catalog
from app.db.utils import new_uuid, utc_now_iso


class ChannelBindingTests(unittest.TestCase):
    """Tests for channel member binding operations."""

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

        # Import region catalog for household creation
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

        # Create test household (without region_selection to avoid provider dependency)
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

        # Create test members
        self.member1 = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Member 1", role="adult"),
        )
        self.member2 = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="Member 2", role="adult"),
        )
        self.db.commit()

        # Create test channel account
        self.channel_account = self._create_test_channel_account(
            platform_code="telegram",
            account_code="test-bot",
            display_name="Test Telegram Bot",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def _create_test_channel_account(
        self,
        platform_code: str = "telegram",
        account_code: str = "test-bot",
        display_name: str = "Test Bot",
    ) -> ChannelPluginAccount:
        """Helper to create a test channel account."""
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

    def test_create_binding_success(self) -> None:
        """Test creating a binding from channel account perspective."""
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_123",
            display_hint="John on Telegram",
        )

        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        self.assertEqual(result.member_id, self.member1.id)
        self.assertEqual(result.channel_account_id, self.channel_account.id)
        self.assertEqual(result.external_user_id, "telegram_user_123")
        self.assertEqual(result.display_hint, "John on Telegram")
        self.assertEqual(result.binding_status, "active")
        self.assertEqual(result.platform_code, "telegram")

    def test_create_binding_with_external_chat_id(self) -> None:
        """Test creating a binding with external_chat_id."""
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_456",
            external_chat_id="chat_789",
            display_hint="John in Group Chat",
        )

        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        self.assertEqual(result.external_chat_id, "chat_789")

    def test_create_binding_strips_whitespace(self) -> None:
        """Test that string fields are stripped of whitespace."""
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="  telegram_user_123  ",
            display_hint="  John on Telegram  ",
        )

        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        self.assertEqual(result.external_user_id, "telegram_user_123")
        self.assertEqual(result.display_hint, "John on Telegram")

    def test_create_binding_empty_external_chat_id_becomes_none(self) -> None:
        """Test that empty external_chat_id becomes None."""
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_123",
            external_chat_id="   ",  # Whitespace only
        )

        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        self.assertIsNone(result.external_chat_id)

    def test_create_binding_rejects_wrong_household_member(self) -> None:
        """Test that creating binding with member from different household fails."""
        # Create another household with a member
        other_household = create_household(
            self.db,
            HouseholdCreate(
                name="Other Household",
                city="Beijing",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        other_member = create_member(
            self.db,
            MemberCreate(household_id=other_household.id, name="Other Member", role="adult"),
        )
        self.db.commit()

        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=other_member.id,
            external_user_id="telegram_user_999",
        )

        with self.assertRaises(MemberChannelBindingServiceError) as ctx:
            create_channel_account_binding(
                self.db,
                household_id=self.household.id,
                payload=payload,
            )

        self.assertIn("does not belong to current household", str(ctx.exception))

    def test_create_binding_detects_external_user_conflict(self) -> None:
        """Test that duplicate external_user_id on same platform is rejected."""
        # Create first binding
        payload1 = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_duplicate",
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload1,
        )
        self.db.commit()

        # Try to create second binding with same external_user_id
        payload2 = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member2.id,
            external_user_id="telegram_user_duplicate",
        )

        with self.assertRaises(MemberChannelBindingServiceError) as ctx:
            create_channel_account_binding(
                self.db,
                household_id=self.household.id,
                payload=payload2,
            )

        self.assertIn("already bound", str(ctx.exception))

    def test_create_binding_allows_same_external_user_different_platform(self) -> None:
        """Test that same external_user_id on different platforms is allowed."""
        # Create binding on Telegram
        payload1 = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="user_123",
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload1,
        )
        self.db.commit()

        # Create another channel account on different platform
        discord_account = self._create_test_channel_account(
            platform_code="discord",
            account_code="test-discord-bot",
        )
        self.db.commit()

        # Should be able to bind same external_user_id on different platform
        payload2 = MemberChannelBindingCreate(
            channel_account_id=discord_account.id,
            member_id=self.member2.id,
            external_user_id="user_123",  # Same ID, different platform
        )
        result = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload2,
        )
        self.db.commit()

        self.assertEqual(result.external_user_id, "user_123")
        self.assertEqual(result.platform_code, "discord")

    def test_list_channel_account_bindings_empty(self) -> None:
        """Test listing bindings when none exist."""
        result = list_channel_account_bindings(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
        )

        self.assertEqual(result, [])

    def test_list_channel_account_bindings_returns_bindings(self) -> None:
        """Test listing bindings for a channel account."""
        # Create multiple bindings
        for i, member in enumerate([self.member1, self.member2]):
            payload = MemberChannelBindingCreate(
                channel_account_id=self.channel_account.id,
                member_id=member.id,
                external_user_id=f"telegram_user_{i}",
            )
            create_channel_account_binding(
                self.db,
                household_id=self.household.id,
                payload=payload,
            )
        self.db.commit()

        result = list_channel_account_bindings(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
        )

        self.assertEqual(len(result), 2)
        member_ids = {b.member_id for b in result}
        self.assertIn(self.member1.id, member_ids)
        self.assertIn(self.member2.id, member_ids)

    def test_update_binding_external_user_id(self) -> None:
        """Test updating binding's external_user_id."""
        # Create binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="old_user_id",
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Update external_user_id
        update_payload = MemberChannelBindingUpdate(
            external_user_id="new_user_id",
        )
        result = update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
            binding_id=binding.id,
            payload=update_payload,
        )
        self.db.commit()

        self.assertEqual(result.external_user_id, "new_user_id")

    def test_update_binding_status(self) -> None:
        """Test updating binding's status."""
        # Create binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_status",
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Disable binding
        update_payload = MemberChannelBindingUpdate(
            binding_status="disabled",
        )
        result = update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
            binding_id=binding.id,
            payload=update_payload,
        )
        self.db.commit()

        self.assertEqual(result.binding_status, "disabled")

    def test_update_binding_display_hint(self) -> None:
        """Test updating binding's display_hint."""
        # Create binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_hint",
            display_hint="Old hint",
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Update display_hint
        update_payload = MemberChannelBindingUpdate(
            display_hint="New hint",
        )
        result = update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
            binding_id=binding.id,
            payload=update_payload,
        )
        self.db.commit()

        self.assertEqual(result.display_hint, "New hint")

    def test_update_binding_detects_conflict(self) -> None:
        """Test that updating to conflicted external_user_id fails."""
        # Create two bindings
        payload1 = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="user_one",
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload1,
        )

        payload2 = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member2.id,
            external_user_id="user_two",
        )
        binding2 = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload2,
        )
        self.db.commit()

        # Try to update binding2 to use binding1's external_user_id
        update_payload = MemberChannelBindingUpdate(
            external_user_id="user_one",
        )

        with self.assertRaises(MemberChannelBindingServiceError) as ctx:
            update_channel_account_binding(
                self.db,
                household_id=self.household.id,
                account_id=self.channel_account.id,
                binding_id=binding2.id,
                payload=update_payload,
            )

        self.assertIn("already bound", str(ctx.exception))

    def test_update_binding_allows_same_external_user_id(self) -> None:
        """Test that updating with same external_user_id succeeds."""
        # Create binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="same_user_id",
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Update with same external_user_id should succeed
        update_payload = MemberChannelBindingUpdate(
            external_user_id="same_user_id",
        )
        result = update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
            binding_id=binding.id,
            payload=update_payload,
        )
        self.db.commit()

        self.assertEqual(result.external_user_id, "same_user_id")

    def test_update_binding_wrong_account_fails(self) -> None:
        """Test that updating binding from different account fails."""
        # Create binding on first account
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_user_cross",
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Create another account
        other_account = self._create_test_channel_account(
            platform_code="discord",
            account_code="other-bot",
        )
        self.db.commit()

        # Try to update binding using wrong account_id
        update_payload = MemberChannelBindingUpdate(
            display_hint="New hint",
        )

        with self.assertRaises(MemberChannelBindingServiceError) as ctx:
            update_channel_account_binding(
                self.db,
                household_id=self.household.id,
                account_id=other_account.id,
                binding_id=self.channel_account.id,  # Wrong binding_id (just using account id as example)
                payload=update_payload,
            )

        self.assertIn("not found", str(ctx.exception))

    def test_resolve_binding_for_bound_user(self) -> None:
        """Test resolving binding for a bound user."""
        # Create binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_resolved_user",
        )
        create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.channel_account.id,
            external_user_id="telegram_resolved_user",
            chat_type="direct",
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.strategy, "bound")
        self.assertEqual(result.member_id, self.member1.id)
        self.assertIsNone(result.reply_text)

    def test_resolve_binding_for_unbound_direct_chat(self) -> None:
        """Test resolving binding for unbound direct chat."""
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.channel_account.id,
            external_user_id="unknown_user",
            chat_type="direct",
        )

        self.assertFalse(result.matched)
        self.assertEqual(result.strategy, "direct_unbound_prompt")
        self.assertEqual(result.reply_text, UNBOUND_DIRECT_REPLY_TEXT)

    def test_resolve_binding_for_unbound_group_chat(self) -> None:
        """Test resolving binding for unbound group chat."""
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.channel_account.id,
            external_user_id="unknown_user",
            chat_type="group",
        )

        self.assertFalse(result.matched)
        self.assertEqual(result.strategy, "group_unbound_ignore")
        self.assertIsNone(result.reply_text)

    def test_resolve_binding_ignores_disabled_binding(self) -> None:
        """Test that disabled bindings are not matched."""
        # Create and then disable binding
        payload = MemberChannelBindingCreate(
            channel_account_id=self.channel_account.id,
            member_id=self.member1.id,
            external_user_id="telegram_disabled_user",
        )
        binding = create_channel_account_binding(
            self.db,
            household_id=self.household.id,
            payload=payload,
        )
        self.db.commit()

        # Disable the binding
        update_channel_account_binding(
            self.db,
            household_id=self.household.id,
            account_id=self.channel_account.id,
            binding_id=binding.id,
            payload=MemberChannelBindingUpdate(binding_status="disabled"),
        )
        self.db.commit()

        # Should not match disabled binding
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.channel_account.id,
            external_user_id="telegram_disabled_user",
            chat_type="direct",
        )

        self.assertFalse(result.matched)
        self.assertEqual(result.strategy, "direct_unbound_prompt")

    def test_resolve_binding_with_none_external_user_id(self) -> None:
        """Test resolving binding when external_user_id is None."""
        result = resolve_member_binding_for_inbound(
            self.db,
            household_id=self.household.id,
            channel_account_id=self.channel_account.id,
            external_user_id=None,
            chat_type="direct",
        )

        self.assertFalse(result.matched)
        self.assertEqual(result.strategy, "direct_unbound_prompt")
