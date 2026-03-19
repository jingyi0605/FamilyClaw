import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

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
from app.modules.plugin.schemas import PluginMountCreate, PluginStateUpdateRequest
from app.modules.plugin.service import register_plugin_mount, set_household_plugin_enabled
from app.modules.plugin.startup_sync_service import sync_persisted_plugins_on_startup


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
        with self.SessionLocal() as db:
            ensure_pending_household_bootstrap_accounts(db)
            household = create_household(
                db,
                HouseholdCreate(name="Locale Home", city="Taipei", timezone="Asia/Taipei", locale="zh-CN"),
            )
            member = create_member(
                db,
                MemberCreate(household_id=household.id, name="管理员", role="admin"),
            )
            sync_persisted_plugins_on_startup(db)
            db.commit()

            self.household_id = household.id
            self.member_id = member.id

            bootstrap = authenticate_account(db, "user", "user")
            account = complete_bootstrap_account(
                db,
                actor=bootstrap,
                payload=BootstrapAccountCompleteRequest(
                    household_id=self.household_id,
                    member_id=self.member_id,
                    username="locale_owner",
                    password="owner123",
                ),
            )
            _, self.session_token = create_account_session(db, account.id)
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()
        db_session_module.SessionLocal = self._previous_session_local
        settings.database_url = self._previous_database_url
        self._tempdir.cleanup()

    def test_list_household_locales_returns_builtin_locale_pack_and_weather_locale(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_locale_pack_plugin(
                Path(plugin_tempdir),
                plugin_id="third-party-zh-hk-pack",
                locale_id="zh-HK",
            )
            with self.SessionLocal() as db:
                register_plugin_mount(
                    db,
                    household_id=self.household_id,
                    payload=PluginMountCreate(
                        source_type="third_party",
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=20,
                    ),
                )
                db.commit()

            transport = httpx.ASGITransport(app=app)

            async def run_case() -> None:
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                    response = await client.get(f"/api/v1/ai-config/{self.household_id}/locales")
                    self.assertEqual(200, response.status_code)
                    payload = response.json()
                    self.assertEqual(self.household_id, payload["household_id"])

                    by_locale = {item["locale_id"]: item for item in payload["items"]}
                    self.assertIn("zh-TW", by_locale)
                    self.assertIn("zh-HK", by_locale)
                    self.assertIn("zh-CN", by_locale)
                    self.assertEqual("locale-zh-tw", by_locale["zh-TW"]["plugin_id"])
                    self.assertEqual("third_party", by_locale["zh-HK"]["source_type"])
                    self.assertEqual("中文（香港）", by_locale["zh-HK"]["native_label"])
                    self.assertEqual("储存", by_locale["zh-HK"]["messages"]["common.save"])
                    self.assertEqual("official-weather", by_locale["zh-CN"]["plugin_id"])
                    self.assertEqual("家庭天气", by_locale["zh-CN"]["messages"]["official_weather.dashboard.title"])

            asyncio.run(run_case())

    def test_locale_pack_keeps_owner_and_merges_plugin_owned_messages(self) -> None:
        with tempfile.TemporaryDirectory() as plugin_tempdir:
            plugin_root = self._create_plugin_with_locales(
                Path(plugin_tempdir),
                plugin_id="third-party-weather-copy",
                locale_id="zh-TW",
                messages={"official_weather.dashboard.title": "第三方天气标题"},
            )
            with self.SessionLocal() as db:
                register_plugin_mount(
                    db,
                    household_id=self.household_id,
                    payload=PluginMountCreate(
                        source_type="third_party",
                        plugin_root=str(plugin_root),
                        python_path=sys.executable,
                        working_dir=str(plugin_root),
                        timeout_seconds=20,
                    ),
                )
                db.commit()

            transport = httpx.ASGITransport(app=app)

            async def run_case() -> None:
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                    response = await client.get(f"/api/v1/ai-config/{self.household_id}/locales")
                    self.assertEqual(200, response.status_code)
                    payload = response.json()
                    zh_tw = {item["locale_id"]: item for item in payload["items"]}["zh-TW"]
                    self.assertEqual("locale-zh-tw", zh_tw["plugin_id"])
                    self.assertIn("third-party-weather-copy", zh_tw["overridden_plugin_ids"])
                    self.assertEqual("儲存", zh_tw["messages"]["common.save"])
                    self.assertEqual("第三方天气标题", zh_tw["messages"]["official_weather.dashboard.title"])

            asyncio.run(run_case())

    def test_disabled_builtin_locale_pack_is_filtered_out(self) -> None:
        with self.SessionLocal() as db:
            set_household_plugin_enabled(
                db,
                household_id=self.household_id,
                plugin_id="locale-zh-tw",
                payload=PluginStateUpdateRequest(enabled=False),
                updated_by="tester",
            )
            db.commit()

        transport = httpx.ASGITransport(app=app)

        async def run_case() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                client.cookies.set(settings.auth_session_cookie_name, self.session_token)
                response = await client.get(f"/api/v1/ai-config/{self.household_id}/locales")
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
        native_label: str = "中文（香港）",
        messages: dict[str, str] | None = None,
    ) -> Path:
        plugin_root = root / plugin_id
        locale_dir = plugin_root / "locales"
        locale_dir.mkdir(parents=True)
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "第三方语言包",
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
                    "common.save": "储存",
                    "common.cancel": "取消",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return plugin_root

    def _create_plugin_with_locales(
        self,
        root: Path,
        *,
        plugin_id: str,
        locale_id: str,
        messages: dict[str, str],
    ) -> Path:
        plugin_root = root / plugin_id
        locale_dir = plugin_root / "locales"
        locale_dir.mkdir(parents=True)
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": "带插件词典的集成",
                    "version": "0.1.0",
                    "types": ["integration"],
                    "permissions": ["device.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {
                        "integration": "app.plugins.builtin.health_basic.integration.sync"
                    },
                    "capabilities": {
                        "integration": {
                            "domains": ["demo"],
                            "instance_model": "single_instance",
                            "refresh_mode": "manual",
                            "supports_discovery": False,
                            "supports_actions": False,
                            "supports_cards": False,
                            "entity_types": [],
                            "default_cache_ttl_seconds": 60,
                            "max_stale_seconds": 60
                        }
                    },
                    "locales": [
                        {
                            "id": locale_id,
                            "label": "Traditional Chinese",
                            "native_label": "繁體中文",
                            "resource": f"locales/{locale_id}.json",
                            "fallback": "zh-CN"
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (locale_dir / f"{locale_id}.json").write_text(
            json.dumps(messages, ensure_ascii=False),
            encoding="utf-8",
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
