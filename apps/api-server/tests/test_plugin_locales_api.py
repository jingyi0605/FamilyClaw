import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
import app.db.session as db_session_module
from app.core.config import settings
from app.main import app
from app.modules.account.schemas import BootstrapAccountCompleteRequest
from app.modules.account.service import authenticate_account, complete_bootstrap_account, create_account_session, ensure_pending_household_bootstrap_accounts
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.member.schemas import MemberCreate
from app.modules.member.service import create_member
from app.modules.plugin.schemas import PluginMountCreate, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, set_household_plugin_enabled


class PluginLocalesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
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
            HouseholdCreate(name="Locale Home", city="Taipei", timezone="Asia/Taipei", locale="zh-CN"),
        )
        self.member = create_member(
            self.db,
            MemberCreate(household_id=self.household.id, name="绠＄悊鍛?, role="admin"),
        )
        self.db.commit()

        bootstrap = authenticate_account(self.db, "user", "user")
        account = complete_bootstrap_account(
            self.db,
            actor=bootstrap,
            payload=BootstrapAccountCompleteRequest(
                household_id=self.household.id,
                member_id=self.member.id,
                username="locale_owner",
                password="owner123",
            ),
        )
        _, self.session_token = create_account_session(self.db, account.id)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_list_household_locales_returns_builtin_and_mounted_locale_packs(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_locale_pack_plugin(
                Path(plugin_tempdir),
                plugin_id="third-party-zh-hk-pack",
                locale_id="zh-HK",
            )
            register_plugin_mount(
                self.db,
                household_id=self.household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.commit()

            transport = httpx.ASGITransport(app=app)

            async def run_case() -> None:
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                    response = await client.get(f"/api/v1/ai-config/{self.household.id}/locales")
                    self.assertEqual(200, response.status_code)
                    payload = response.json()
                    self.assertEqual(self.household.id, payload["household_id"])

                    by_locale = {item["locale_id"]: item for item in payload["items"]}
                    self.assertIn("zh-TW", by_locale)
                    self.assertIn("zh-HK", by_locale)
                    self.assertEqual("locale-zh-tw", by_locale["zh-TW"]["plugin_id"])
                    self.assertEqual("third_party", by_locale["zh-HK"]["source_type"])
                    self.assertEqual("涓枃锛堥娓級", by_locale["zh-HK"]["native_label"])
                    self.assertEqual("鍎插瓨", by_locale["zh-HK"]["messages"]["common.save"])

            asyncio.run(run_case())

    def test_builtin_locale_pack_wins_when_locale_id_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_locale_pack_plugin(
                Path(plugin_tempdir),
                plugin_id="third-party-zh-tw-pack",
                locale_id="zh-TW",
                native_label="绗笁鏂圭箒楂斾腑鏂?,
                messages={"common.save": "绗笁鏂瑰劜瀛?},
            )
            register_plugin_mount(
                self.db,
                household_id=self.household.id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(plugin_root),
                    python_path=sys.executable,
                    working_dir=str(plugin_root),
                    timeout_seconds=20,
                ),
            )
            self.db.commit()

            transport = httpx.ASGITransport(app=app)

            async def run_case() -> None:
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                    response = await client.get(f"/api/v1/ai-config/{self.household.id}/locales")
                    self.assertEqual(200, response.status_code)
                    payload = response.json()
                    by_locale = {item["locale_id"]: item for item in payload["items"]}
                    zh_tw = by_locale["zh-TW"]
                    self.assertEqual("locale-zh-tw", zh_tw["plugin_id"])
                    self.assertIn("third-party-zh-tw-pack", zh_tw["overridden_plugin_ids"])
                    self.assertEqual("鍎插瓨", zh_tw["messages"]["common.save"])

            asyncio.run(run_case())

    def test_disabled_builtin_locale_pack_is_filtered_out(self) -> None:
        set_household_plugin_enabled(
            self.db,
            household_id=self.household.id,
            plugin_id="locale-zh-tw",
            payload=PluginStateUpdateRequest(enabled=False),
            updated_by="tester",
        )
        self.db.commit()

        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.get(f"/api/v1/ai-config/{self.household.id}/locales")
                self.assertEqual(200, response.status_code)
                payload = response.json()
                locale_ids = {item["locale_id"] for item in payload["items"]}
                self.assertNotIn("zh-TW", locale_ids)

        asyncio.run(run_case())

    def _create_locale_pack_plugin(
        self,
        root: Path,
        *,
        plugin_id: str,
        locale_id: str,
        native_label: str = "涓枃锛堥娓級",
        messages: dict[str, str] | None = None,
    ) -> Path:
        plugin_root = root / plugin_id
        locale_dir = plugin_root / "locales"
        locale_dir.mkdir(parents=True)
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "绗笁鏂硅瑷€鍖?,
                    "version": "0.1.0",
                    "types": ["locale-pack"],
                    "permissions": [],
                    "risk_level": "low",
                    "triggers": [],
                    "entrypoints": {},
                    "locales": [
                        {
                            "id": locale_id,
                            "label": "Chinese (Hong Kong)",
                            "native_label": native_label,
                            "resource": f"locales/{locale_id}.json",
                            "fallback": "zh-CN",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (locale_dir / f"{locale_id}.json").write_text(
            json.dumps(
                messages or {
                    "common.save": "鍎插瓨",
                    "common.cancel": "鍙栨秷",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()

