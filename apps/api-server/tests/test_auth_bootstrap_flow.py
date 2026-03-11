import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, ensure_actor_can_access_household
from app.core.config import settings
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
from app.modules.room.service import create_room


class AuthBootstrapFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_bootstrap_username = os.environ.get("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME")
        self._previous_bootstrap_password = os.environ.get("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD")
        self._previous_database_url = settings.database_url
        os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME"] = "user"
        os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD"] = "user"

        db_path = os.path.join(self._tempdir.name, "test.db")
        settings.database_url = f"sqlite:///{db_path}"
        project_root = Path(__file__).resolve().parents[1]
        alembic_config = Config(str(project_root / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(project_root / "migrations"))
        alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_config, "head")

        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db: Session = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

        if self._previous_bootstrap_username is None:
            os.environ.pop("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME", None)
        else:
            os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_USERNAME"] = self._previous_bootstrap_username

        if self._previous_bootstrap_password is None:
            os.environ.pop("FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD", None)
        else:
            os.environ["FAMILYCLAW_BOOTSTRAP_HOUSEHOLD_PASSWORD"] = self._previous_bootstrap_password

    def test_create_household_creates_bootstrap_account(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        bootstrap = authenticate_account(self.db, "user", "user")
        self.assertEqual("bootstrap", bootstrap.account_type)
        self.assertIsNone(bootstrap.household_id)

        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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

    def test_setup_status_advances_after_bootstrap_completion(self) -> None:
        ensure_pending_household_bootstrap_accounts(self.db)
        household = create_household(
            self.db,
            HouseholdCreate(name="Test Home", city="Shenzhen", timezone="Asia/Shanghai", locale="zh-CN"),
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
