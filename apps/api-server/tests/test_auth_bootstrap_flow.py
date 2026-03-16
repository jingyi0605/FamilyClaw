import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, ensure_actor_can_access_household
from app.core.config import settings
from app.modules.account.models import AccountSession
from app.modules.account.schemas import BootstrapAccountCompleteRequest
from app.modules.account.service import (
    authenticate_account,
    complete_bootstrap_account,
    create_account_session,
    ensure_pending_household_bootstrap_accounts,
    resolve_authenticated_actor_by_session_token,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household, get_household_setup_status
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.region.schemas import RegionCatalogImportItem, RegionSelection
from app.modules.region.service import import_region_catalog
from app.modules.room.service import create_room
from tests.test_db_support import PostgresTestDatabase


class AuthBootstrapFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_bootstrap_username = os.environ.get("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME")
        self._previous_bootstrap_password = os.environ.get("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD")
        self._previous_auth_session_touch_interval_seconds = settings.auth_session_touch_interval_seconds
        os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME"] = "user"
        os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD"] = "user"

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
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
                    name="北京市",
                    full_name="北京市",
                    path_codes=["110000"],
                    path_names=["北京市"],
                ),
                RegionCatalogImportItem(
                    region_code="110100",
                    parent_region_code="110000",
                    admin_level="city",
                    name="北京市",
                    full_name="北京市 / 北京市",
                    path_codes=["110000", "110100"],
                    path_names=["北京市", "北京市"],
                ),
                RegionCatalogImportItem(
                    region_code="110105",
                    parent_region_code="110100",
                    admin_level="district",
                    name="朝阳区",
                    full_name="北京市 / 北京市 / 朝阳区",
                    path_codes=["110000", "110100", "110105"],
                    path_names=["北京市", "北京市", "朝阳区"],
                ),
            ],
            source_version="test-v1",
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()
        settings.auth_session_touch_interval_seconds = self._previous_auth_session_touch_interval_seconds
        self._tempdir.cleanup()

        if self._previous_bootstrap_username is None:
            os.environ.pop("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME", None)
        else:
            os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME"] = self._previous_bootstrap_username

        if self._previous_bootstrap_password is None:
            os.environ.pop("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD", None)
        else:
            os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD"] = self._previous_bootstrap_password

    def _create_bound_account_session(self) -> tuple[str, str, str, str]:
        ensure_pending_household_bootstrap_accounts(self.db)
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )
        self.db.flush()

        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=household.id,
                member_id=member.id,
                username="owner",
                password="owner123",
            ),
        )
        self.db.flush()

        session_record, token = create_account_session(self.db, account.id)
        self.db.commit()
        return household.id, member.id, session_record.id, token

    def test_create_household_creates_bootstrap_account(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        bootstrap = authenticate_account(self.db, "user", "user")
        self.assertEqual("bootstrap", bootstrap.account_type)
        self.assertIsNone(bootstrap.household_id)

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
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")

        self.assertEqual("bootstrap", bootstrap.account_type)
        self.assertTrue(bootstrap.must_change_password)
        self.assertIsNone(bootstrap.household_id)

    def test_global_bootstrap_can_list_and_access_pending_household(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        actor_context = ActorContext.from_authenticated_actor(bootstrap)

        ensure_actor_can_access_household(actor_context, household.id)

    def test_complete_bootstrap_account_disables_default_credentials(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )
        self.db.flush()

        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=household.id,
                member_id=member.id,
                username="owner",
                password="owner123",
            ),
        )
        self.db.commit()

        self.assertEqual("household", account.account_type)
        self.assertEqual("owner", account.username)
        self.assertFalse(account.must_change_password)

        owner = authenticate_account(self.db, "owner", "owner123")
        self.assertEqual(member.id, owner.member_id)
        self.assertEqual("admin", owner.role)

        with self.assertRaises(HTTPException) as context:
            authenticate_account(self.db, "user", "user")
        self.assertEqual(401, context.exception.status_code)

    def test_session_resolution_and_household_access_guard(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        another = create_household(
            self.db,
            HouseholdCreate(name="Another Home", city="Guangzhou", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )
        create_room(self.db, household_id=household.id, name="客厅", room_type="living_room", privacy_level="public")
        self.db.flush()

        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=household.id,
                member_id=member.id,
                username="owner",
                password="owner123",
            ),
        )
        self.db.flush()
        _session, token = create_account_session(self.db, account.id)
        self.db.commit()

        resolved = resolve_authenticated_actor_by_session_token(self.db, token)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(household.id, resolved.household_id)
        self.assertEqual(member.id, resolved.member_id)

        actor_context = ActorContext.from_authenticated_actor(resolved)
        ensure_actor_can_access_household(actor_context, household.id)

        with self.assertRaises(HTTPException) as context:
            ensure_actor_can_access_household(actor_context, another.id)
        self.assertEqual(403, context.exception.status_code)

    def test_session_resolution_does_not_touch_last_seen_within_refresh_interval(self) -> None:
        settings.auth_session_touch_interval_seconds = 3600
        _household_id, _member_id, session_id, token = self._create_bound_account_session()

        session_record = self.db.get(AccountSession, session_id)
        assert session_record is not None
        original_last_seen_at = session_record.last_seen_at

        resolved = resolve_authenticated_actor_by_session_token(self.db, token)

        self.assertIsNotNone(resolved)
        self.db.expire_all()
        refreshed_session = self.db.get(AccountSession, session_id)
        assert refreshed_session is not None
        self.assertEqual(original_last_seen_at, refreshed_session.last_seen_at)

    def test_session_resolution_refreshes_last_seen_after_interval(self) -> None:
        settings.auth_session_touch_interval_seconds = 60
        _household_id, _member_id, session_id, token = self._create_bound_account_session()

        stale_last_seen_at = "2020-01-01T00:00:00Z"
        session_record = self.db.get(AccountSession, session_id)
        assert session_record is not None
        session_record.last_seen_at = stale_last_seen_at
        self.db.add(session_record)
        self.db.commit()

        resolved = resolve_authenticated_actor_by_session_token(self.db, token)

        self.assertIsNotNone(resolved)
        self.db.expire_all()
        refreshed_session = self.db.get(AccountSession, session_id)
        assert refreshed_session is not None
        self.assertNotEqual(stale_last_seen_at, refreshed_session.last_seen_at)

    def test_session_resolution_skips_last_seen_write_when_database_is_locked(self) -> None:
        settings.auth_session_touch_interval_seconds = 60
        _household_id, _member_id, session_id, token = self._create_bound_account_session()

        session_record = self.db.get(AccountSession, session_id)
        assert session_record is not None
        session_record.last_seen_at = "2020-01-01T00:00:00Z"
        self.db.add(session_record)
        self.db.commit()

        with patch.object(
            self.db,
            "commit",
            side_effect=OperationalError(
                "UPDATE account_sessions SET last_seen_at=? WHERE account_sessions.id = ?",
                {},
                Exception("database is locked"),
            ),
        ):
            resolved = resolve_authenticated_actor_by_session_token(self.db, token)

        self.assertIsNotNone(resolved)
        self.db.expire_all()
        refreshed_session = self.db.get(AccountSession, session_id)
        assert refreshed_session is not None
        self.assertEqual("2020-01-01T00:00:00Z", refreshed_session.last_seen_at)

    def test_setup_status_advances_after_bootstrap_completion(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
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
        self.db.commit()

        before_status = get_household_setup_status(self.db, household.id)
        self.assertEqual("first_member", before_status.current_step)
        self.assertTrue(before_status.is_required)

        bootstrap = authenticate_account(self.db, "user", "user")
        member = create_member(
            self.db,
            MemberCreate(household_id=household.id, name="Owner", role="admin"),
        )
        self.db.flush()

        complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=household.id,
                member_id=member.id,
                username="owner",
                password="owner123",
            ),
        )
        self.db.commit()

        after_status = get_household_setup_status(self.db, household.id)
        self.assertEqual("provider_setup", after_status.current_step)
        self.assertTrue(after_status.is_required)


if __name__ == "__main__":
    unittest.main()
