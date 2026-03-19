import asyncio
import unittest

import httpx

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.core.config import settings
from app.main import app
from app.modules.account.schemas import BootstrapAccountCompleteRequest
from app.modules.account.service import (
    authenticate_account,
    complete_bootstrap_account,
    create_account_session,
    ensure_pending_household_bootstrap_accounts,
)
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member


class MemberGuideStatusApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_database_url = settings.database_url

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self._previous_session_local = db_session_module.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal

        with self.SessionLocal() as db:
            ensure_pending_household_bootstrap_accounts(db)
            household = create_household(
                db,
                HouseholdCreate(name="导览测试家庭", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            primary_member = create_member(
                db,
                MemberCreate(household_id=household.id, name="管理员", role="admin"),
            )
            second_member = create_member(
                db,
                MemberCreate(household_id=household.id, name="家人", role="adult"),
            )
            db.commit()

            self.household_id = household.id
            self.primary_member_id = primary_member.id
            self.second_member_id = second_member.id

            bootstrap = authenticate_account(db, "user", "user")
            account = complete_bootstrap_account(
                db,
                actor=bootstrap,
                payload=BootstrapAccountCompleteRequest(
                    household_id=self.household_id,
                    member_id=self.primary_member_id,
                    username="guide_owner",
                    password="owner123",
                ),
            )
            _, self.session_token = create_account_session(db, account.id)
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        self._db_helper.close()
        settings.database_url = self._previous_database_url

    def test_member_can_read_and_update_own_guide_status(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)

                get_response = await client.get(
                    f"/api/v1/member-preferences/{self.primary_member_id}/guide-status"
                )
                self.assertEqual(200, get_response.status_code)
                self.assertEqual(
                    {
                        "member_id": self.primary_member_id,
                        "user_app_guide_version": None,
                        "updated_at": None,
                    },
                    get_response.json(),
                )

                put_response = await client.put(
                    f"/api/v1/member-preferences/{self.primary_member_id}/guide-status",
                    json={"user_app_guide_version": 1},
                )
                self.assertEqual(200, put_response.status_code)
                self.assertEqual(1, put_response.json()["user_app_guide_version"])
                self.assertIsNotNone(put_response.json()["updated_at"])

                follow_up_response = await client.get(
                    f"/api/v1/member-preferences/{self.primary_member_id}/guide-status"
                )
                self.assertEqual(200, follow_up_response.status_code)
                self.assertEqual(1, follow_up_response.json()["user_app_guide_version"])

        asyncio.run(run_case())

    def test_member_cannot_rollback_guide_version(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)

                first_response = await client.put(
                    f"/api/v1/member-preferences/{self.primary_member_id}/guide-status",
                    json={"user_app_guide_version": 2},
                )
                self.assertEqual(200, first_response.status_code)

                rollback_response = await client.put(
                    f"/api/v1/member-preferences/{self.primary_member_id}/guide-status",
                    json={"user_app_guide_version": 1},
                )
                self.assertEqual(409, rollback_response.status_code)
                self.assertEqual("guide version cannot move backward", rollback_response.json()["detail"])

        asyncio.run(run_case())

    def test_member_cannot_update_another_member_guide_status(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)

                put_response = await client.put(
                    f"/api/v1/member-preferences/{self.second_member_id}/guide-status",
                    json={"user_app_guide_version": 1},
                )
                self.assertEqual(403, put_response.status_code)
                self.assertEqual("cannot update another member guide status", put_response.json()["detail"])

                get_response = await client.get(
                    f"/api/v1/member-preferences/{self.second_member_id}/guide-status"
                )
                self.assertEqual(200, get_response.status_code)
                self.assertEqual(None, get_response.json()["user_app_guide_version"])

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
