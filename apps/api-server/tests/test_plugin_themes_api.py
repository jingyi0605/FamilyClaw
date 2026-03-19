import asyncio
import unittest

import httpx
from sqlalchemy.orm import Session

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
from app.modules.plugin.schemas import PluginStateUpdateRequest
from app.modules.plugin.service import set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup


class PluginThemesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_database_url = settings.database_url
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal
        self._previous_session_local = db_session_module.SessionLocal
        db_session_module.SessionLocal = self.SessionLocal
        self.db: Session = self.SessionLocal()

        ensure_pending_household_bootstrap_accounts(self.db)
        self.household = create_household(
            self.db,
            HouseholdCreate(name="Theme Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="管理员", role="admin"),
        )
        self.household_id = self.household.id
        self.member_id = self.member.id
        sync_persisted_plugins_on_startup(self.db)
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=self.household_id,
                member_id=self.member_id,
                username="theme_owner",
                password="owner123",
            ),
        )
        _, self.session_token = create_account_session(self.db, account.id)
        self.db.commit()
        self.db.close()

    def tearDown(self) -> None:
        if self.db.is_active:
            self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
        self._db_helper.close()

    def test_list_household_themes_returns_registry_snapshot(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.get(f"/api/v1/ai-config/{self.household_id}/themes")
                self.assertEqual(200, response.status_code)
                payload = response.json()
                self.assertEqual(self.household_id, payload["household_id"])
                by_plugin_id = {item["plugin_id"]: item for item in payload["items"]}
                theme_item = by_plugin_id["builtin.theme.chun-he-jing-ming"]
                self.assertEqual("chun-he-jing-ming", theme_item["theme_id"])
                self.assertEqual("builtin_bundle", theme_item["resource_source"])
                self.assertEqual("1.0.0", theme_item["resource_version"])
                self.assertEqual(1, theme_item["theme_schema_version"])
                self.assertEqual(["h5", "rn"], theme_item["platform_targets"])
                self.assertNotIn("tokens", theme_item)

        asyncio.run(run_case())

    def test_get_theme_resource_returns_token_payload(self) -> None:
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.get(
                    f"/api/v1/ai-config/{self.household_id}/plugin-themes/builtin.theme.chun-he-jing-ming/chun-he-jing-ming"
                )
                self.assertEqual(200, response.status_code)
                payload = response.json()
                self.assertEqual("builtin.theme.chun-he-jing-ming", payload["plugin_id"])
                self.assertEqual("chun-he-jing-ming", payload["theme_id"])
                self.assertEqual("1.0.0", payload["resource_version"])
                self.assertEqual("#d97756", payload["tokens"]["brandPrimary"])
                self.assertEqual("#f7f5f2", payload["tokens"]["bgApp"])

        asyncio.run(run_case())

    def test_get_theme_resource_returns_409_when_plugin_disabled(self) -> None:
        self.db = self.SessionLocal()
        set_household_plugin_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="builtin.theme.chun-he-jing-ming",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="tester",
        )
        self.db.commit()
        self.db.close()
        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.get(
                    f"/api/v1/ai-config/{self.household_id}/plugin-themes/builtin.theme.chun-he-jing-ming/chun-he-jing-ming"
                )
                self.assertEqual(409, response.status_code)
                detail = response.json()["detail"]
                self.assertEqual("plugin_disabled", detail["error_code"])

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
