import io
import json
import sys
import tempfile
import unittest
import zipfile
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
from app.modules.plugin.service import PluginServiceError, get_household_plugin, list_plugin_mounts


class PluginPackageApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_plugin_storage_root = settings.plugin_storage_root
        self._previous_plugin_dev_root = settings.plugin_dev_root
        settings.plugin_storage_root = self._tempdir.name
        settings.plugin_dev_root = str((Path(self._tempdir.name) / "plugins-dev").resolve())

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
                HouseholdCreate(name="Plugin Package API Home", city="Shanghai", timezone="Asia/Shanghai", locale="zh-CN"),
            )
            self.household_id = household.id
            db.commit()

    def tearDown(self) -> None:
        self.client.close()
        self._db_helper.close()
        settings.plugin_storage_root = self._previous_plugin_storage_root
        settings.plugin_dev_root = self._previous_plugin_dev_root
        self._tempdir.cleanup()

    def test_install_plugin_package_endpoint_accepts_zip_and_creates_release_mount(self) -> None:
        response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.0.0"), "application/zip")},
        )

        self.assertEqual(201, response.status_code)
        payload = response.json()
        self.assertEqual("demo-plugin", payload["plugin_id"])
        self.assertEqual("installed", payload["install_action"])
        self.assertEqual("third_party", payload["source_type"])
        self.assertEqual("subprocess_runner", payload["execution_backend"])
        self.assertFalse(payload["enabled"])
        self.assertIn("--", Path(payload["plugin_root"]).name)

        with self.SessionLocal() as db:
            mounts = list_plugin_mounts(db, household_id=self.household_id)
            self.assertEqual(1, len(mounts))
            self.assertEqual("subprocess_runner", mounts[0].execution_backend)
            self.assertFalse(mounts[0].enabled)

            plugin = get_household_plugin(db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("1.0.0", plugin.version)
            self.assertEqual("third_party", plugin.source_type)
            self.assertEqual("subprocess_runner", plugin.execution_backend)

    def test_install_plugin_package_endpoint_requires_overwrite_for_existing_plugin(self) -> None:
        first_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.0.0"), "application/zip")},
        )
        self.assertEqual(201, first_response.status_code)

        second_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.1.0"), "application/zip")},
        )

        self.assertEqual(409, second_response.status_code)
        self.assertEqual("plugin_package_conflict", second_response.json()["detail"]["error_code"])

    def test_install_plugin_package_endpoint_overwrite_switches_to_new_release(self) -> None:
        first_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.0.0"), "application/zip")},
        )
        self.assertEqual(201, first_response.status_code)
        first_payload = first_response.json()

        second_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "true"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.1.0"), "application/zip")},
        )

        self.assertEqual(201, second_response.status_code)
        second_payload = second_response.json()
        self.assertEqual("upgraded", second_payload["install_action"])
        self.assertTrue(second_payload["overwritten"])
        self.assertEqual("1.0.0", second_payload["previous_version"])
        self.assertNotEqual(first_payload["plugin_root"], second_payload["plugin_root"])

        with self.SessionLocal() as db:
            plugin = get_household_plugin(db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("1.1.0", plugin.version)
            mounts = list_plugin_mounts(db, household_id=self.household_id)
            self.assertEqual(second_payload["plugin_root"], mounts[0].plugin_root)

    def test_delete_plugin_endpoint_removes_installed_plugin(self) -> None:
        install_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.0.0"), "application/zip")},
        )
        self.assertEqual(201, install_response.status_code)

        delete_response = self.client.delete(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin",
        )
        self.assertEqual(204, delete_response.status_code)

        with self.SessionLocal() as db:
            self.assertEqual([], list_plugin_mounts(db, household_id=self.household_id))
            with self.assertRaises(PluginServiceError) as ctx:
                get_household_plugin(db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("plugin_not_visible_in_household", ctx.exception.error_code)

    def test_plugin_registry_api_lists_conflicting_variants_and_only_enables_one(self) -> None:
        install_response = self.client.post(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-packages",
            data={"overwrite": "false"},
            files={"file": ("demo-plugin.zip", self._build_plugin_archive(plugin_id="demo-plugin", version="1.0.0"), "application/zip")},
        )
        self.assertEqual(201, install_response.status_code)
        mount_update_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugin-mounts/demo-plugin",
            json={"enabled": True},
        )
        self.assertEqual(200, mount_update_response.status_code)

        dev_root = self._create_dev_plugin(plugin_id="demo-plugin", version="9.9.9", name="Demo Plugin Dev")

        collapsed_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins",
        )
        self.assertEqual(200, collapsed_response.status_code)
        collapsed_items = [item for item in collapsed_response.json()["items"] if item["id"] == "demo-plugin"]
        self.assertEqual(1, len(collapsed_items))
        self.assertEqual("plugins_dev", collapsed_items[0]["runtime_source"])
        self.assertTrue(collapsed_items[0]["enabled"])
        self.assertTrue(collapsed_items[0]["is_dev_active"])

        full_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins",
            params={"include_conflicting_variants": "true"},
        )
        self.assertEqual(200, full_response.status_code)
        variants = [item for item in full_response.json()["items"] if item["id"] == "demo-plugin"]
        self.assertEqual(2, len(variants))
        dev_variant = next(item for item in variants if item["runtime_source"] == "plugins_dev")
        installed_variant = next(item for item in variants if item["runtime_source"] == "installed")
        self.assertEqual("9.9.9", dev_variant["version"])
        self.assertTrue(dev_variant["enabled"])
        self.assertTrue(dev_variant["is_dev_active"])
        self.assertEqual("1.0.0", installed_variant["version"])
        self.assertFalse(installed_variant["enabled"])
        self.assertFalse(installed_variant["is_dev_active"])

        switch_response = self.client.put(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin/state",
            json={"enabled": True, "runtime_source": "installed"},
        )
        self.assertEqual(200, switch_response.status_code)
        switched_payload = switch_response.json()
        self.assertEqual("installed", switched_payload["runtime_source"])
        self.assertTrue(switched_payload["enabled"])
        self.assertFalse(switched_payload["is_dev_active"])

        switched_list_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins",
            params={"include_conflicting_variants": "true"},
        )
        self.assertEqual(200, switched_list_response.status_code)
        switched_variants = [item for item in switched_list_response.json()["items"] if item["id"] == "demo-plugin"]
        switched_dev_variant = next(item for item in switched_variants if item["runtime_source"] == "plugins_dev")
        switched_installed_variant = next(item for item in switched_variants if item["runtime_source"] == "installed")
        self.assertFalse(switched_dev_variant["enabled"])
        self.assertFalse(switched_dev_variant["is_dev_active"])
        self.assertTrue(switched_installed_variant["enabled"])

        delete_response = self.client.delete(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins/demo-plugin",
            params={"runtime_source": "installed"},
        )
        self.assertEqual(204, delete_response.status_code)

        remaining_response = self.client.get(
            f"{settings.api_v1_prefix}/ai-config/{self.household_id}/plugins",
            params={"include_conflicting_variants": "true"},
        )
        self.assertEqual(200, remaining_response.status_code)
        remaining_variants = [item for item in remaining_response.json()["items"] if item["id"] == "demo-plugin"]
        self.assertEqual(1, len(remaining_variants))
        self.assertEqual("plugins_dev", remaining_variants[0]["runtime_source"])
        self.assertTrue(remaining_variants[0]["enabled"])
        self.assertTrue(remaining_variants[0]["is_dev_active"])

        with self.SessionLocal() as db:
            self.assertEqual([], list_plugin_mounts(db, household_id=self.household_id))
            plugin = get_household_plugin(db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("9.9.9", plugin.version)
            self.assertEqual("plugins_dev", plugin.runtime_source)
            self.assertTrue(plugin.is_dev_active)
            assert plugin.runner_config is not None
            self.assertEqual(str(dev_root.resolve()), str(Path(plugin.runner_config.plugin_root).resolve()))

    @staticmethod
    def _build_plugin_archive(*, plugin_id: str, version: str) -> bytes:
        payload = {
            "id": plugin_id,
            "name": f"{plugin_id} Plugin",
            "version": version,
            "types": ["integration"],
            "permissions": ["health.read", "memory.write.observation"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive_root = f"{plugin_id}-{version}"
            archive.writestr(f"{archive_root}/manifest.json", json.dumps(payload, ensure_ascii=False))
            archive.writestr(f"{archive_root}/plugin/__init__.py", "")
            archive.writestr(
                f"{archive_root}/plugin/integration.py",
                "def sync(payload=None):\n    return {'records': []}\n",
            )
        return buffer.getvalue()

    def _create_dev_plugin(self, *, plugin_id: str, version: str, name: str) -> Path:
        plugin_root = Path(settings.plugin_dev_root) / plugin_id
        (plugin_root / "plugin").mkdir(parents=True, exist_ok=True)
        manifest = {
            "id": plugin_id,
            "name": name,
            "version": version,
            "types": ["integration"],
            "permissions": ["health.read", "memory.write.observation"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
        }
        (plugin_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (plugin_root / "plugin" / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "plugin" / "integration.py").write_text(
            "def sync(payload=None):\n    return {'records': []}\n",
            encoding="utf-8",
        )
        return plugin_root
