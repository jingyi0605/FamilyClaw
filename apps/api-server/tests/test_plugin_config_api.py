import json
import sys
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.ai_config import router as ai_config_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.channel.models import ChannelPluginAccount
from app.modules.channel.schemas import ChannelAccountCreate
from app.modules.channel.service import create_channel_account
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.models import PluginConfigInstance
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class PluginConfigApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_database_url = settings.database_url
        self._previous_secret_seed = settings.plugin_config_secret_seed

        from tests.test_db_support import PostgresTestDatabase
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.database_url = self._db_helper.database_url
        self.engine = self._db_helper.engine
        self.SessionLocal = self._db_helper.SessionLocal

        app = FastAPI()
        app.include_router(ai_config_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_id="admin-account-001",
            account_type="member",
            account_status="active",
            username="admin",
            household_id=self.household_id if hasattr(self, "household_id") else None,
            member_id="member-admin-001",
            is_authenticated=True,
        )
        self.client = TestClient(app)

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(name="鎻掍欢閰嶇疆瀹跺涵", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            self.household_id = household.id
            db.commit()

        self.plugin_root = self._create_plugin_with_config_spec(Path(self._tempdir.name))
        with self.SessionLocal() as db:
            register_plugin_mount(
                db,
                household_id=self.household_id,
                payload=PluginMountCreate(
                    source_type="third_party",
                    plugin_root=str(self.plugin_root),
                    python_path=sys.executable,
                    working_dir=str(self.plugin_root),
                    timeout_seconds=20,
                ),
            )
            db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        settings.plugin_config_secret_seed = self._previous_secret_seed
        self._tempdir.cleanup()

    def test_plugin_scope_endpoints_persist_mask_and_clear_secret(self) -> None:
        scopes_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config-scopes"
        )
        self.assertEqual(200, scopes_response.status_code)
        scopes_payload = scopes_response.json()
        self.assertEqual("demo-plugin-config", scopes_payload["plugin_id"])
        self.assertEqual("plugin", scopes_payload["items"][0]["scope_type"])
        self.assertEqual("default", scopes_payload["items"][0]["instances"][0]["scope_key"])
        self.assertFalse(scopes_payload["items"][0]["instances"][0]["configured"])

        save_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "base_url": "https://example.com/api",
                    "notes": "第一版说明",
                    "retry_limit": 5,
                    "temperature": 0.7,
                    "enabled": True,
                    "mode": "strict",
                    "tags": ["stable", "beta"],
                    "metadata": {"region": "cn"},
                    "api_key": "secret-token-001",
                },
            },
        )
        self.assertEqual(200, save_response.status_code)
        saved_payload = save_response.json()
        self.assertEqual("configured", saved_payload["view"]["state"])
        self.assertNotIn("api_key", saved_payload["view"]["values"])
        self.assertEqual("https://example.com/api", saved_payload["view"]["values"]["base_url"])
        self.assertEqual(["stable", "beta"], saved_payload["view"]["values"]["tags"])
        self.assertEqual({"region": "cn"}, saved_payload["view"]["values"]["metadata"])
        self.assertTrue(saved_payload["view"]["secret_fields"]["api_key"]["has_value"])
        self.assertEqual("******", saved_payload["view"]["secret_fields"]["api_key"]["masked"])

        get_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            params={"scope_type": "plugin", "scope_key": "default"},
        )
        self.assertEqual(200, get_response.status_code)
        get_payload = get_response.json()
        self.assertNotIn("api_key", get_payload["view"]["values"])
        self.assertTrue(get_payload["view"]["secret_fields"]["api_key"]["has_value"])
        self.assertEqual("demo.plugin.config.title", get_payload["config_spec"]["title_key"])
        self.assertEqual(
            "demo.plugin.config.fields.base_url.label",
            get_payload["config_spec"]["config_schema"]["fields"][0]["label_key"],
        )
        self.assertEqual(
            "demo.plugin.config.sections.basic.title",
            get_payload["config_spec"]["ui_schema"]["sections"][0]["title_key"],
        )
        self.assertEqual(
            "demo.plugin.config.submit",
            get_payload["config_spec"]["ui_schema"]["submit_text_key"],
        )

        keep_secret_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "base_url": "https://example.com/v2",
                    "notes": "第二版说明",
                },
            },
        )
        self.assertEqual(200, keep_secret_response.status_code)
        self.assertTrue(keep_secret_response.json()["view"]["secret_fields"]["api_key"]["has_value"])

        clear_secret_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "base_url": "https://example.com/v3",
                },
                "clear_secret_fields": ["api_key"],
            },
        )
        self.assertEqual(400, clear_secret_response.status_code)
        clear_payload = clear_secret_response.json()["detail"]
        self.assertEqual("plugin_config_validation_failed", clear_payload["error_code"])
        self.assertIn("api_key", clear_payload["field_errors"])

        with self.SessionLocal() as db:
            instance = db.query(PluginConfigInstance).filter_by(
                household_id=self.household_id,
                plugin_id="demo-plugin-config",
                scope_type="plugin",
                scope_key="default",
            ).one()
            self.assertIsNotNone(instance.secret_data_encrypted)
            assert instance.secret_data_encrypted is not None
            self.assertNotIn("secret-token-001", instance.secret_data_encrypted)
            self.assertEqual(1, instance.schema_version)

    def test_channel_account_scope_reads_legacy_config_and_syncs_runtime_copy(self) -> None:
        with self.SessionLocal() as db:
            account = create_channel_account(
                db,
                household_id=self.household_id,
                payload=ChannelAccountCreate(
                    plugin_id="channel-telegram",
                    account_code="telegram-main",
                    display_name="Telegram 主账号",
                    connection_mode="polling",
                    config={
                        "bot_token": "legacy-token-001",
                    },
                    status="draft",
                ),
            )
            self.account_id = account.id
            db.commit()

        scopes_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/channel-telegram/config-scopes"
        )
        self.assertEqual(200, scopes_response.status_code)
        channel_scope = next(item for item in scopes_response.json()["items"] if item["scope_type"] == "channel_account")
        self.assertEqual(self.account_id, channel_scope["instances"][0]["scope_key"])
        self.assertTrue(channel_scope["instances"][0]["configured"])

        get_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/channel-telegram/config",
            params={"scope_type": "channel_account", "scope_key": self.account_id},
        )
        self.assertEqual(200, get_response.status_code)
        payload = get_response.json()
        self.assertEqual("configured", payload["view"]["state"])
        self.assertNotIn("bot_token", payload["view"]["values"])
        self.assertTrue(payload["view"]["secret_fields"]["bot_token"]["has_value"])
        save_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/channel-telegram/config",
            json={
                "scope_type": "channel_account",
                "scope_key": self.account_id,
                "values": {},
            },
        )
        self.assertEqual(200, save_response.status_code)
        save_payload = save_response.json()
        self.assertTrue(save_payload["view"]["secret_fields"]["bot_token"]["has_value"])

        with self.SessionLocal() as db:
            account = db.get(ChannelPluginAccount, self.account_id)
            assert account is not None
            self.assertEqual({"bot_token": "legacy-token-001"}, json.loads(account.config_json))

            instance = db.query(PluginConfigInstance).filter_by(
                household_id=self.household_id,
                plugin_id="channel-telegram",
                scope_type="channel_account",
                scope_key=self.account_id,
            ).one()
            self.assertIsNotNone(instance.secret_data_encrypted)
            assert instance.secret_data_encrypted is not None
            self.assertNotIn("legacy-token-001", instance.secret_data_encrypted)

    def _create_plugin_with_config_spec(self, root: Path) -> Path:
        plugin_root = root / "demo_plugin_config"
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)

        manifest = {
            "id": "demo-plugin-config",
            "name": "婕旂ず鎻掍欢閰嶇疆",
            "version": "0.1.0",
            "types": ["integration"],
            "permissions": ["health.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
            "config_specs": [
                {
                    "scope_type": "plugin",
                    "title": "婕旂ず鎻掍欢閰嶇疆",
                    "title_key": "demo.plugin.config.title",
                    "description": "用来覆盖插件级配置协议的最小可用场景。",
                    "description_key": "demo.plugin.config.description",
                    "schema_version": 1,
                    "config_schema": {
                        "fields": [
                            {"key": "base_url", "label": "鍩虹鍦板潃", "label_key": "demo.plugin.config.fields.base_url.label", "type": "string", "required": True},
                            {"key": "notes", "label": "澶囨敞", "label_key": "demo.plugin.config.fields.notes.label", "type": "text", "required": False},
                            {"key": "retry_limit", "label": "閲嶈瘯娆℃暟", "label_key": "demo.plugin.config.fields.retry_limit.label", "type": "integer", "required": False, "default": 3},
                            {"key": "temperature", "label": "娓╁害", "label_key": "demo.plugin.config.fields.temperature.label", "type": "number", "required": False},
                            {"key": "enabled", "label": "鍚敤", "label_key": "demo.plugin.config.fields.enabled.label", "type": "boolean", "required": False, "default": True},
                            {
                                "key": "mode",
                                "label": "妯″紡",
                                "label_key": "demo.plugin.config.fields.mode.label",
                                "type": "enum",
                                "required": True,
                                "enum_options": [
                                    {"value": "strict", "label": "涓ユ牸", "label_key": "demo.plugin.config.fields.mode.options.strict"},
                                    {"value": "loose", "label": "瀹芥澗", "label_key": "demo.plugin.config.fields.mode.options.loose"},
                                ],
                                "default": "strict",
                            },
                            {
                                "key": "tags",
                                "label": "鏍囩",
                                "label_key": "demo.plugin.config.fields.tags.label",
                                "type": "multi_enum",
                                "required": False,
                                "enum_options": [
                                    {"value": "stable", "label": "绋冲畾", "label_key": "demo.plugin.config.fields.tags.options.stable"},
                                    {"value": "beta", "label": "娴嬭瘯", "label_key": "demo.plugin.config.fields.tags.options.beta"},
                                ],
                            },
                            {"key": "api_key", "label": "API Key", "label_key": "demo.plugin.config.fields.api_key.label", "type": "secret", "required": True},
                            {"key": "metadata", "label": "棰濆閰嶇疆", "label_key": "demo.plugin.config.fields.metadata.label", "type": "json", "required": False},
                        ]
                    },
                    "ui_schema": {
                        "sections": [
                            {
                                "id": "basic",
                                "title": "鍩虹鍙傛暟",
                                "title_key": "demo.plugin.config.sections.basic.title",
                                "fields": [
                                    "base_url",
                                    "notes",
                                    "retry_limit",
                                    "temperature",
                                    "enabled",
                                    "mode",
                                    "tags",
                                    "api_key",
                                    "metadata",
                                ],
                            }
                        ],
                        "submit_text": "保存演示配置",
                        "submit_text_key": "demo.plugin.config.submit",
                        "widgets": {
                            "notes": {"widget": "textarea", "help_text": "演示备注", "help_text_key": "demo.plugin.config.fields.notes.help_text"},
                            "enabled": {"widget": "switch"},
                            "mode": {"widget": "select", "help_text": "请选择模式", "help_text_key": "demo.plugin.config.fields.mode.help_text"},
                            "tags": {"widget": "multi_select"},
                            "api_key": {"widget": "password", "placeholder": "请输入 key", "placeholder_key": "demo.plugin.config.fields.api_key.placeholder"},
                            "metadata": {"widget": "json_editor"},
                        },
                    },
                }
            ],
        }

        (plugin_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n"
            "    return {'ok': True, 'payload': payload or {}}\n",
            encoding="utf-8",
        )
        return plugin_root


