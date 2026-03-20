import io
import json
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.api.dependencies import ActorContext, require_admin_actor
from app.api.v1.endpoints.plugin_marketplace import router as plugin_marketplace_router
from app.core.config import settings
from app.db.session import get_db
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin_marketplace.github_client import GitHubMarketplaceClientError
import app.modules.plugin_marketplace.service as marketplace_service


OFFICIAL_MARKET_REPO_URL = "https://github.com/demo/official-marketplace"
THIRD_PARTY_MARKET_REPO_URL = "https://github.com/demo/third-marketplace"
PLUGIN_REPO_URL = "https://github.com/demo/demo-plugin"


class FakeGitHubMarketplaceClient:
    def __init__(
        self,
        *,
        files: dict[tuple[str, str, str], dict],
        directories: dict[tuple[str, str, str], list[dict]],
        metadata: dict[str, dict | Exception],
        downloads: dict[str, bytes],
    ) -> None:
        self._files = files
        self._directories = directories
        self._metadata = metadata
        self._downloads = downloads

    def parse_repo_url(
        self,
        repo_url: str,
        *,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ):
        provider = repo_provider
        if provider is None:
            host = urlparse(repo_url).netloc.lower()
            if host == "github.com":
                provider = "github"
            elif host == "gitlab.com":
                provider = "gitlab"
            elif host == "gitee.com":
                provider = "gitee"
            else:
                raise GitHubMarketplaceClientError(
                    "无法自动识别仓库类型",
                    error_code="invalid_market_repo",
                    status_code=400,
                )
        return SimpleNamespace(provider=provider, api_base_url=api_base_url, repo_url=repo_url)

    def get_file_json(
        self,
        *,
        repo_url: str,
        path: str,
        ref: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> dict:
        key = (repo_url, path.strip("/"), ref)
        if key not in self._files:
            raise GitHubMarketplaceClientError(
                f"文件不存在: {path}",
                error_code="market_sync_failed",
                status_code=404,
            )
        return json.loads(json.dumps(self._files[key]))

    def list_directory(
        self,
        *,
        repo_url: str,
        path: str,
        ref: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> list[dict]:
        key = (repo_url, path.strip("/"), ref)
        if key not in self._directories:
            raise GitHubMarketplaceClientError(
                f"目录不存在: {path}",
                error_code="market_sync_failed",
                status_code=404,
            )
        return json.loads(json.dumps(self._directories[key]))

    def get_repository_metadata(
        self,
        *,
        repo_url: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> dict:
        value = self._metadata.get(repo_url)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise GitHubMarketplaceClientError(
                "仓库元数据不存在",
                error_code="repository_metrics_unavailable",
                status_code=404,
            )
        return json.loads(json.dumps(value))

    def get_repository_views(
        self,
        *,
        repo_url: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> dict | None:
        return None

    def build_source_archive_url(
        self,
        *,
        repo_url: str,
        git_ref: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> str:
        return f"{repo_url}/archive/{git_ref}.zip"

    def download_binary(self, url: str) -> bytes:
        return self._downloads[url]


class PluginMarketplaceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.SessionLocal = self._db_helper.SessionLocal
        self._previous_official_repo = marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_REPO_URL
        self._previous_official_branch = marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_BRANCH
        self._previous_entry_root = marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_ENTRY_ROOT
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_REPO_URL = OFFICIAL_MARKET_REPO_URL
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_BRANCH = "main"
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_ENTRY_ROOT = "plugins"

        self.fake_client = self._build_fake_client()
        self._patcher = patch(
            "app.modules.plugin_marketplace.service.build_github_marketplace_client",
            return_value=self.fake_client,
        )
        self._patcher.start()

        app = FastAPI()
        app.include_router(plugin_marketplace_router, prefix=settings.api_v1_prefix)

        def _override_get_db():
            db: Session = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        with self.SessionLocal() as db:
            household = create_household(
                db,
                HouseholdCreate(
                    name="Plugin Marketplace API Home",
                    city="Shanghai",
                    timezone="Asia/Shanghai",
                    locale="zh-CN",
                ),
            )
            self.household_id = household.id
            db.commit()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[require_admin_actor] = lambda: ActorContext(
            role="admin",
            actor_type="admin",
            actor_id="admin-001",
            account_id="admin-account-001",
            account_type="member",
            account_status="active",
            username="admin",
            household_id=self.household_id,
            member_id="member-admin-001",
            is_authenticated=True,
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self._patcher.stop()
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_REPO_URL = self._previous_official_repo
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_BRANCH = self._previous_official_branch
        marketplace_service.OFFICIAL_PLUGIN_MARKETPLACE_ENTRY_ROOT = self._previous_entry_root
        self._db_helper.close()

    def test_add_sync_install_and_enable_endpoint_flow(self) -> None:
        add_response = self.client.post(
            f"{settings.api_v1_prefix}/plugin-marketplace/sources",
            json={"repo_url": THIRD_PARTY_MARKET_REPO_URL},
        )
        self.assertEqual(200, add_response.status_code)
        source_id = add_response.json()["source_id"]

        sync_response = self.client.post(f"{settings.api_v1_prefix}/plugin-marketplace/sources/{source_id}/sync")
        self.assertEqual(200, sync_response.status_code)
        self.assertEqual(1, sync_response.json()["ready_entries"])

        catalog_response = self.client.get(
            f"{settings.api_v1_prefix}/plugin-marketplace/catalog",
            params={"household_id": self.household_id},
        )
        self.assertEqual(200, catalog_response.status_code)
        self.assertEqual(1, len(catalog_response.json()["items"]))

        install_response = self.client.post(
            f"{settings.api_v1_prefix}/plugin-marketplace/install-tasks",
            json={
                "household_id": self.household_id,
                "source_id": source_id,
                "plugin_id": "demo-plugin",
                "version": "1.0.0",
            },
        )
        self.assertEqual(200, install_response.status_code)
        self.assertEqual("installed", install_response.json()["install_status"])

        catalog_after_install = self.client.get(
            f"{settings.api_v1_prefix}/plugin-marketplace/catalog",
            params={"household_id": self.household_id},
        )
        instance_id = catalog_after_install.json()["items"][0]["install_state"]["instance_id"]
        self.assertIsNotNone(instance_id)
        self.assertFalse(catalog_after_install.json()["items"][0]["install_state"]["enabled"])

        enable_response = self.client.post(
            f"{settings.api_v1_prefix}/plugin-marketplace/instances/{instance_id}/enable",
            json={"enabled": True},
        )
        self.assertEqual(409, enable_response.status_code)
        self.assertEqual(
            "plugin_marketplace_not_configured",
            enable_response.json()["detail"]["error_code"],
        )

    def test_version_options_endpoint_returns_backend_computed_actions(self) -> None:
        add_response = self.client.post(
            f"{settings.api_v1_prefix}/plugin-marketplace/sources",
            json={"repo_url": THIRD_PARTY_MARKET_REPO_URL},
        )
        self.assertEqual(200, add_response.status_code)
        source_id = add_response.json()["source_id"]

        sync_response = self.client.post(f"{settings.api_v1_prefix}/plugin-marketplace/sources/{source_id}/sync")
        self.assertEqual(200, sync_response.status_code)

        options_before_install = self.client.get(
            f"{settings.api_v1_prefix}/plugin-marketplace/catalog/{source_id}/demo-plugin/version-options",
            params={"household_id": self.household_id},
        )
        self.assertEqual(200, options_before_install.status_code)
        before_items = {item["version"]: item for item in options_before_install.json()["items"]}
        self.assertEqual(["2.0.0", "1.2.0", "1.1.0", "1.0.0", "0.9.0"], [item["version"] for item in options_before_install.json()["items"]])
        self.assertEqual("install", before_items["1.1.0"]["action"])
        self.assertEqual("unavailable", before_items["2.0.0"]["action"])
        self.assertEqual("host_too_old", before_items["2.0.0"]["compatibility_status"])
        self.assertEqual("unavailable", before_items["1.2.0"]["action"])
        self.assertEqual("unknown", before_items["1.2.0"]["compatibility_status"])

        install_response = self.client.post(
            f"{settings.api_v1_prefix}/plugin-marketplace/install-tasks",
            json={
                "household_id": self.household_id,
                "source_id": source_id,
                "plugin_id": "demo-plugin",
                "version": "1.0.0",
            },
        )
        self.assertEqual(200, install_response.status_code)

        options_after_install = self.client.get(
            f"{settings.api_v1_prefix}/plugin-marketplace/catalog/{source_id}/demo-plugin/version-options",
            params={"household_id": self.household_id},
        )
        self.assertEqual(200, options_after_install.status_code)
        after_items = {item["version"]: item for item in options_after_install.json()["items"]}
        self.assertEqual("upgrade", after_items["1.1.0"]["action"])
        self.assertEqual("rollback", after_items["0.9.0"]["action"])
        self.assertEqual("current", after_items["1.0.0"]["action"])

    @staticmethod
    def _build_fake_client() -> FakeGitHubMarketplaceClient:
        files = {
            (OFFICIAL_MARKET_REPO_URL, "market.json", "main"): {
                "market_id": "official-market",
                "name": "Official Market",
                "owner": "demo",
                "repo_url": OFFICIAL_MARKET_REPO_URL,
                "default_branch": "main",
                "entry_root": "plugins",
                "is_system": True,
            },
            (THIRD_PARTY_MARKET_REPO_URL, "market.json", "main"): {
                "market_id": "third-party-market",
                "name": "Third Party Market",
                "owner": "demo",
                "repo_url": THIRD_PARTY_MARKET_REPO_URL,
                "default_branch": "main",
                "entry_root": "plugins",
                "is_system": False,
            },
            (THIRD_PARTY_MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): {
                "plugin_id": "demo-plugin",
                "name": "Demo Plugin",
                "summary": "Demo plugin from third party market.",
                "source_repo": PLUGIN_REPO_URL,
                "manifest_path": "manifest.json",
                "readme_url": f"{PLUGIN_REPO_URL}#readme",
                "publisher": {"name": "Demo Publisher"},
                "categories": ["demo"],
                "risk_level": "low",
                "permissions": ["device.read"],
                "latest_version": "2.0.0",
                "versions": [
                    {
                        "version": "0.9.0",
                        "git_ref": "refs/tags/v0.9.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-0.9.0.zip",
                        "min_app_version": "0.1.0",
                    },
                    {
                        "version": "1.0.0",
                        "git_ref": "refs/tags/v1.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                        "min_app_version": "0.1.0",
                    },
                    {
                        "version": "1.1.0",
                        "git_ref": "refs/tags/v1.1.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.1.0.zip",
                        "min_app_version": "0.1.0",
                    },
                    {
                        "version": "1.2.0",
                        "git_ref": "refs/tags/v1.2.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.2.0.zip",
                        "min_app_version": None,
                    },
                    {
                        "version": "2.0.0",
                        "git_ref": "refs/tags/v2.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-2.0.0.zip",
                        "min_app_version": "9.9.9",
                    }
                ],
                "install": {
                    "requirements_path": "requirements.txt",
                    "readme_path": "README.md",
                },
                "maintainers": [{"name": "Maintainer"}],
            },
        }
        directories = {
            (OFFICIAL_MARKET_REPO_URL, "plugins", "main"): [],
            (THIRD_PARTY_MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            OFFICIAL_MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 1},
            THIRD_PARTY_MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 5, "forks_count": 1},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 3, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-0.9.0.zip": PluginMarketplaceApiTests._build_plugin_archive("0.9.0"),
            "https://example.com/demo-plugin-1.0.0.zip": PluginMarketplaceApiTests._build_plugin_archive(),
            "https://example.com/demo-plugin-1.1.0.zip": PluginMarketplaceApiTests._build_plugin_archive("1.1.0"),
            "https://example.com/demo-plugin-1.2.0.zip": PluginMarketplaceApiTests._build_plugin_archive("1.2.0"),
            "https://example.com/demo-plugin-2.0.0.zip": PluginMarketplaceApiTests._build_plugin_archive("2.0.0"),
        }
        return FakeGitHubMarketplaceClient(
            files=files,
            directories=directories,
            metadata=metadata,
            downloads=downloads,
        )

    @staticmethod
    def _build_plugin_archive(version: str = "1.0.0") -> bytes:
        manifest = {
            "id": "demo-plugin",
            "name": "Demo Plugin",
            "version": version,
            "types": ["integration"],
            "permissions": ["device.read"],
            "risk_level": "low",
            "triggers": ["manual"],
            "entrypoints": {
                "integration": "plugin.integration.sync",
            },
            "config_specs": [
                {
                    "scope_type": "plugin",
                    "title": "Demo Config",
                    "schema_version": 1,
                    "config_schema": {
                        "fields": [
                            {"key": "base_url", "label": "Base URL", "type": "string", "required": True},
                            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
                        ]
                    },
                    "ui_schema": {
                        "sections": [
                            {
                                "id": "basic",
                                "title": "Basic",
                                "fields": ["base_url", "api_key"],
                            }
                        ]
                    },
                }
            ],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive_root = f"demo-plugin-{version}"
            archive.writestr(f"{archive_root}/manifest.json", json.dumps(manifest, ensure_ascii=False))
            archive.writestr(f"{archive_root}/README.md", "# Demo Plugin\n")
            archive.writestr(f"{archive_root}/requirements.txt", "httpx>=0.28\n")
            archive.writestr(f"{archive_root}/plugin/__init__.py", "")
            archive.writestr(
                f"{archive_root}/plugin/integration.py",
                "def sync(payload=None):\n    return {'ok': True, 'payload': payload or {}}\n",
            )
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()

