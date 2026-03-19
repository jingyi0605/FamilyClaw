import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.ai_config import router as ai_config_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.schemas import PluginMountCreate
from app.modules.plugin.service import register_plugin_mount


class PluginConfigDynamicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()

        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
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
                HouseholdCreate(name="动态配置家庭", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
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
        self._tempdir.cleanup()

    def test_clear_fields_removes_plain_field_from_persisted_config(self) -> None:
        create_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "base_url": "https://example.com/api",
                    "notes": "第一版备注",
                    "mode": "strict",
                    "api_key": "secret-token-001",
                },
            },
        )
        self.assertEqual(200, create_response.status_code)

        clear_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            json={
                "scope_type": "plugin",
                "scope_key": "default",
                "values": {
                    "base_url": "https://example.com/v2",
                },
                "clear_fields": ["notes"],
            },
        )
        self.assertEqual(200, clear_response.status_code)
        payload = clear_response.json()
        self.assertEqual("https://example.com/v2", payload["view"]["values"]["base_url"])
        self.assertNotIn("notes", payload["view"]["values"])

        get_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin-config/config",
            params={"scope_type": "plugin", "scope_key": "default"},
        )
        self.assertEqual(200, get_response.status_code)
        get_payload = get_response.json()
        self.assertNotIn("notes", get_payload["view"]["values"])
        self.assertEqual("strict", get_payload["view"]["values"]["mode"])
        self.assertTrue(get_payload["view"]["secret_fields"]["api_key"]["has_value"])

    def _create_plugin_with_config_spec(self, root: Path) -> Path:
        plugin_root = root / "demo_plugin_config"
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True)

        manifest = {
            "id": "demo-plugin-config",
            "name": "演示插件配置",
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
                    "title": "演示插件配置",
                    "schema_version": 1,
                    "config_schema": {
                        "fields": [
                            {"key": "base_url", "label": "基础地址", "type": "string", "required": True},
                            {"key": "notes", "label": "备注", "type": "text", "required": False},
                            {
                                "key": "mode",
                                "label": "模式",
                                "type": "enum",
                                "required": True,
                                "enum_options": [
                                    {"value": "strict", "label": "严格"},
                                    {"value": "loose", "label": "宽松"},
                                ],
                                "default": "strict",
                            },
                            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
                        ]
                    },
                    "ui_schema": {
                        "sections": [
                            {
                                "id": "basic",
                                "title": "基础参数",
                                "fields": ["base_url", "notes", "mode", "api_key"],
                            }
                        ],
                        "submit_text": "保存演示配置",
                        "widgets": {
                            "notes": {"widget": "textarea"},
                            "mode": {"widget": "select"},
                            "api_key": {"widget": "password"},
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


if __name__ == "__main__":
    unittest.main()
