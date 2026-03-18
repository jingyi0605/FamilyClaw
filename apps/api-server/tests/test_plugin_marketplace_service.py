import io
import hashlib
import json
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
from app.core.config import settings
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.plugin.config_service import save_plugin_config_form
from app.modules.plugin.schemas import PluginConfigUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.service import get_household_plugin
from app.modules.plugin_marketplace.github_client import GitHubMarketplaceClientError
from app.modules.plugin_marketplace.repository import list_marketplace_entry_snapshots, list_marketplace_install_tasks
from app.modules.plugin_marketplace.schemas import (
    MarketplaceInstallTaskCreateRequest,
    MarketplaceSourceCreateRequest,
    PluginVersionOperationRequest,
)
from app.modules.plugin_marketplace.service import (
    PluginMarketplaceServiceError,
    add_marketplace_source,
    create_marketplace_install_task,
    get_marketplace_instance_for_household_plugin,
    list_marketplace_catalog,
    operate_marketplace_instance_version,
    resolve_marketplace_plugin_config_status,
    set_marketplace_instance_enabled,
    sync_marketplace_source,
)


MARKET_REPO_URL = "https://github.com/demo/marketplace"
GITLAB_MARKET_REPO_URL = "https://gitlab.com/demo/marketplace"
MIRROR_MARKET_REPO_URL = "https://git.example.com/demo/marketplace"
PLUGIN_REPO_URL = "https://github.com/demo/demo-plugin"
BROKEN_PLUGIN_REPO_URL = "https://github.com/demo/broken-plugin"


class FakeGitHubMarketplaceClient:
    def __init__(
        self,
        *,
        files: dict[tuple[str, str, str], dict],
        directories: dict[tuple[str, str, str], list[dict]],
        metadata: dict[str, dict | Exception],
        downloads: dict[str, bytes],
        views: dict[str, dict | None] | None = None,
    ) -> None:
        self._files = files
        self._directories = directories
        self._metadata = metadata
        self._downloads = downloads
        self._views = views or {}

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
        return deepcopy(self._files[key])

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
        return deepcopy(self._directories[key])

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
        return deepcopy(value)

    def get_repository_views(
        self,
        *,
        repo_url: str,
        repo_provider: str | None = None,
        api_base_url: str | None = None,
    ) -> dict | None:
        value = self._views.get(repo_url)
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

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
        if url not in self._downloads:
            raise GitHubMarketplaceClientError(
                f"下载地址不存在: {url}",
                error_code="download_failed",
                status_code=404,
            )
        return self._downloads[url]


class PluginMarketplaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_db_support import PostgresTestDatabase

        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        household = create_household(
            self.db,
            HouseholdCreate(
                name="Plugin Marketplace Home",
                city="Shanghai",
                timezone="Asia/Shanghai",
                locale="zh-CN",
            ),
        )
        self.household_id = household.id
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self._db_helper.close()

    def test_sync_marketplace_source_keeps_invalid_entry_and_metrics_degrade(self) -> None:
        client = self._build_client_with_valid_and_invalid_entries()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        result = sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        self.assertEqual(2, result.total_entries)
        self.assertEqual(1, result.ready_entries)
        self.assertEqual(1, result.invalid_entries)
        self.assertEqual(1, len(result.errors))

        snapshots = list_marketplace_entry_snapshots(self.db, source_id=source.source_id)
        self.assertEqual(2, len(snapshots))
        invalid_snapshot = next(item for item in snapshots if item.plugin_id == "broken-plugin")
        self.assertEqual("invalid", invalid_snapshot.sync_status)

        catalog = list_marketplace_catalog(self.db)
        self.assertEqual(1, len(catalog.items))
        self.assertEqual("demo-plugin", catalog.items[0].plugin_id)
        self.assertIsNone(catalog.items[0].repository_metrics.stargazers_count)
        self.assertIsNone(catalog.items[0].repository_metrics.forks_count)
        self.assertFalse(catalog.items[0].repository_metrics.availability.stargazers_count)

    def test_install_success_defaults_disabled_and_requires_manual_enable(self) -> None:
        client = self._build_client_for_install()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        task = create_marketplace_install_task(
            self.db,
            payload=MarketplaceInstallTaskCreateRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                version="1.0.0",
            ),
            client=client,
        )
        self.db.commit()

        self.assertEqual("installed", task.install_status)
        instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert instance is not None
        self.assertEqual("installed", instance.install_status)
        self.assertFalse(instance.enabled)
        self.assertEqual("unconfigured", instance.config_status)
        expected_marketplace_root = (Path(settings.plugin_marketplace_install_root).resolve() / "third_party" / "marketplace").resolve()
        self.assertTrue(Path(task.plugin_root).resolve().is_relative_to(expected_marketplace_root))
        self.assertTrue(Path(instance.plugin_root).resolve().is_relative_to(expected_marketplace_root))

        plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
        self.assertEqual("installed", plugin.install_status)
        self.assertEqual("unconfigured", plugin.config_status)
        self.assertIsNotNone(plugin.marketplace_instance_id)

        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            set_marketplace_instance_enabled(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
                payload=PluginStateUpdateRequest(enabled=True),
            )
        self.assertEqual("plugin_marketplace_not_configured", ctx.exception.error_code)

        save_plugin_config_form(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginConfigUpdateRequest(
                scope_type="plugin",
                scope_key="default",
                values={
                    "base_url": "https://example.com/api",
                    "api_key": "secret-token-001",
                },
            ),
            updated_by="test-suite",
        )
        self.db.commit()

        self.assertEqual(
            "configured",
            resolve_marketplace_plugin_config_status(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
            ),
        )
        enabled_instance = set_marketplace_instance_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
        )
        self.db.commit()

        self.assertTrue(enabled_instance.enabled)
        plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
        self.assertTrue(plugin.enabled)
        self.assertEqual("configured", plugin.config_status)

    def test_add_marketplace_source_supports_gitlab_repo_and_gitea_mirror(self) -> None:
        client = self._build_client_for_gitlab_mirror_source()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(
                repo_url=GITLAB_MARKET_REPO_URL,
                repo_provider="gitlab",
                mirror_repo_url=MIRROR_MARKET_REPO_URL,
                mirror_repo_provider="gitea",
                mirror_api_base_url="https://git.example.com/api/v1",
            ),
            client=client,
        )
        result = sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        self.assertEqual("gitlab", source.repo_provider)
        self.assertEqual(MIRROR_MARKET_REPO_URL, source.mirror_repo_url)
        self.assertEqual("gitea", source.mirror_repo_provider)
        self.assertEqual(MIRROR_MARKET_REPO_URL, result.source.effective_repo_url)
        catalog = list_marketplace_catalog(self.db)
        self.assertEqual(1, len(catalog.items))
        self.assertEqual("demo-plugin", catalog.items[0].plugin_id)

    def test_install_fails_when_artifact_checksum_mismatch(self) -> None:
        client = self._build_client_for_checksum_mismatch()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)

        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    version="1.0.0",
                ),
                client=client,
            )
        self.assertEqual("artifact_checksum_mismatch", ctx.exception.error_code)

        task = list_marketplace_install_tasks(self.db, household_id=self.household_id, plugin_id="demo-plugin")[0]
        self.assertEqual("install_failed", task.install_status)
        self.assertEqual("downloading", task.failure_stage)

    def test_install_fails_when_manifest_permissions_mismatch(self) -> None:
        client = self._build_client_for_permissions_mismatch()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)

        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    version="1.0.0",
                ),
                client=client,
            )
        self.assertEqual("manifest_mismatch", ctx.exception.error_code)

    def test_install_fails_when_archive_missing_readme_or_requirements(self) -> None:
        readme_client = self._build_client_for_missing_project_files(include_readme=False, include_requirements=True)
        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=readme_client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=readme_client)
        with self.assertRaises(PluginMarketplaceServiceError) as readme_ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    version="1.0.0",
                ),
                client=readme_client,
            )
        self.assertEqual("install_target_invalid", readme_ctx.exception.error_code)

        requirements_client = self._build_client_for_missing_project_files(
            include_readme=True,
            include_requirements=False,
            market_repo_url="https://github.com/demo/marketplace-2",
        )
        second_source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(
                repo_url="https://github.com/demo/marketplace-2",
            ),
            client=requirements_client,
        )
        sync_marketplace_source(self.db, source_id=second_source.source_id, client=requirements_client)
        with self.assertRaises(PluginMarketplaceServiceError) as requirements_ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=second_source.source_id,
                    plugin_id="demo-plugin",
                    version="1.0.0",
                ),
                client=requirements_client,
            )
        self.assertEqual("install_target_invalid", requirements_ctx.exception.error_code)

    def test_install_manifest_mismatch_records_failure(self) -> None:
        client = self._build_client_for_manifest_mismatch()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)

        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    version="1.0.0",
                ),
                client=client,
            )
        self.assertEqual("manifest_mismatch", ctx.exception.error_code)

        task = list_marketplace_install_tasks(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )[0]
        self.assertEqual("install_failed", task.install_status)
        self.assertEqual("manifest_mismatch", task.error_code)
        self.assertEqual("validating", task.failure_stage)

    def test_install_blocks_when_host_version_too_old(self) -> None:
        client = self._build_client_for_incompatible_install()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)

        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            create_marketplace_install_task(
                self.db,
                payload=MarketplaceInstallTaskCreateRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    version="2.0.0",
                ),
                client=client,
            )
        self.assertEqual("plugin_version_incompatible", ctx.exception.error_code)

    def test_upgrade_and_rollback_keep_enabled_state(self) -> None:
        client = self._build_client_for_version_switch()
        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        create_marketplace_install_task(
            self.db,
            payload=MarketplaceInstallTaskCreateRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                version="1.0.0",
            ),
            client=client,
        )
        save_plugin_config_form(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginConfigUpdateRequest(
                scope_type="plugin",
                scope_key="default",
                values={
                    "base_url": "https://example.com/api",
                    "api_key": "secret-token-001",
                },
            ),
            updated_by="test-suite",
        )
        set_marketplace_instance_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
        )
        self.db.commit()

        instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert instance is not None
        upgrade_result = operate_marketplace_instance_version(
            self.db,
            instance_id=instance.id,
            payload=PluginVersionOperationRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                target_version="1.1.0",
                operation="upgrade",
            ),
            client=client,
        )
        self.db.commit()

        self.assertEqual("1.1.0", upgrade_result.instance.installed_version)
        self.assertTrue(upgrade_result.instance.enabled)
        self.assertEqual("up_to_date", upgrade_result.governance.update_state)
        self.assertFalse(upgrade_result.state_changed)

        rollback_result = operate_marketplace_instance_version(
            self.db,
            instance_id=instance.id,
            payload=PluginVersionOperationRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                target_version="1.0.0",
                operation="rollback",
            ),
            client=client,
        )
        self.db.commit()

        self.assertEqual("1.0.0", rollback_result.instance.installed_version)
        self.assertTrue(rollback_result.instance.enabled)
        self.assertEqual("upgrade_available", rollback_result.governance.update_state)

    def test_upgrade_disables_plugin_when_new_config_schema_breaks_old_config(self) -> None:
        client = self._build_client_for_config_breaking_upgrade()
        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        create_marketplace_install_task(
            self.db,
            payload=MarketplaceInstallTaskCreateRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                version="1.0.0",
            ),
            client=client,
        )
        save_plugin_config_form(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginConfigUpdateRequest(
                scope_type="plugin",
                scope_key="default",
                values={
                    "base_url": "https://example.com/api",
                    "api_key": "secret-token-001",
                },
            ),
            updated_by="test-suite",
        )
        set_marketplace_instance_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
        )
        self.db.commit()

        instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert instance is not None
        result = operate_marketplace_instance_version(
            self.db,
            instance_id=instance.id,
            payload=PluginVersionOperationRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                target_version="2.0.0",
                operation="upgrade",
            ),
            client=client,
        )
        self.db.commit()

        self.assertEqual("2.0.0", result.instance.installed_version)
        self.assertFalse(result.instance.enabled)
        self.assertEqual("invalid", result.instance.config_status)
        self.assertTrue(result.state_changed)
        self.assertIsNotNone(result.state_change_reason)

    def test_version_switch_failure_keeps_previous_instance_state(self) -> None:
        client = self._build_client_for_switch_failure()
        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        create_marketplace_install_task(
            self.db,
            payload=MarketplaceInstallTaskCreateRequest(
                household_id=self.household_id,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                version="1.0.0",
            ),
            client=client,
        )
        save_plugin_config_form(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginConfigUpdateRequest(
                scope_type="plugin",
                scope_key="default",
                values={
                    "base_url": "https://example.com/api",
                    "api_key": "secret-token-001",
                },
            ),
            updated_by="test-suite",
        )
        set_marketplace_instance_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
        )
        self.db.commit()

        instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert instance is not None
        with self.assertRaises(PluginMarketplaceServiceError) as ctx:
            operate_marketplace_instance_version(
                self.db,
                instance_id=instance.id,
                payload=PluginVersionOperationRequest(
                    household_id=self.household_id,
                    source_id=source.source_id,
                    plugin_id="demo-plugin",
                    target_version="1.1.0",
                    operation="upgrade",
                ),
                client=client,
            )
        self.assertEqual("manifest_mismatch", ctx.exception.error_code)

        current = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert current is not None
        self.assertEqual("1.0.0", current.installed_version)
        self.assertTrue(current.enabled)
        self.assertEqual("configured", current.config_status)

    def _build_client_with_valid_and_invalid_entries(self) -> FakeGitHubMarketplaceClient:
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(),
            (MARKET_REPO_URL, "plugins/broken-plugin/entry.json", "main"): {
                "plugin_id": "broken-plugin",
                "name": "Broken Plugin",
                "summary": "broken",
                "source_repo": BROKEN_PLUGIN_REPO_URL,
                "readme_url": f"{BROKEN_PLUGIN_REPO_URL}#readme",
                "publisher": {"name": "Broken"},
                "risk_level": "medium",
                "permissions": [],
                "latest_version": "1.0.0",
                "versions": [],
            },
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [
                {"name": "demo-plugin", "type": "dir"},
                {"name": "broken-plugin", "type": "dir"},
            ],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: GitHubMarketplaceClientError(
                "指标不可用",
                error_code="repository_metrics_unavailable",
                status_code=502,
            ),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads={})

    def _build_client_for_install(self) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(manifest_version="1.0.0")
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [
                {"name": "demo-plugin", "type": "dir"},
            ],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": archive,
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_gitlab_mirror_source(self) -> FakeGitHubMarketplaceClient:
        files = {
            (MIRROR_MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(repo_url=GITLAB_MARKET_REPO_URL),
            (MIRROR_MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(),
        }
        directories = {
            (MIRROR_MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MIRROR_MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 5, "forks_count": 1},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads={})

    def _build_client_for_checksum_mismatch(self) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(manifest_version="1.0.0")
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=[
                    {
                        "version": "1.0.0",
                        "git_ref": "refs/tags/v1.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                        "checksum": "sha256:" + ("0" * 64),
                        "min_app_version": "0.1.0",
                    }
                ]
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": archive,
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_permissions_mismatch(self) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(manifest_version="1.0.0", permissions=["device.write"])
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=[
                    {
                        "version": "1.0.0",
                        "git_ref": "refs/tags/v1.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                        "checksum": self._sha256(archive),
                        "min_app_version": "0.1.0",
                    }
                ]
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": archive,
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_missing_project_files(
        self,
        *,
        include_readme: bool,
        include_requirements: bool,
        market_repo_url: str = MARKET_REPO_URL,
    ) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(
            manifest_version="1.0.0",
            include_readme=include_readme,
            include_requirements=include_requirements,
        )
        files = {
            (market_repo_url, "market.json", "main"): self._build_market_manifest(repo_url=market_repo_url),
            (market_repo_url, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=[
                    {
                        "version": "1.0.0",
                        "git_ref": "refs/tags/v1.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                        "checksum": self._sha256(archive),
                        "min_app_version": "0.1.0",
                    }
                ]
            ),
        }
        directories = {
            (market_repo_url, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            market_repo_url: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": archive,
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_incompatible_install(self) -> FakeGitHubMarketplaceClient:
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=[
                    {
                        "version": "2.0.0",
                        "git_ref": "refs/tags/v2.0.0",
                        "artifact_type": "source_archive",
                        "artifact_url": "https://example.com/demo-plugin-2.0.0.zip",
                        "min_app_version": "9.9.9",
                    }
                ],
                latest_version="2.0.0",
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-2.0.0.zip": self._build_plugin_archive(manifest_version="2.0.0"),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_version_switch(self) -> FakeGitHubMarketplaceClient:
        versions = [
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
        ]
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=versions,
                latest_version="1.1.0",
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(manifest_version="1.0.0"),
            "https://example.com/demo-plugin-1.1.0.zip": self._build_plugin_archive(manifest_version="1.1.0"),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_config_breaking_upgrade(self) -> FakeGitHubMarketplaceClient:
        versions = [
            {
                "version": "1.0.0",
                "git_ref": "refs/tags/v1.0.0",
                "artifact_type": "source_archive",
                "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                "min_app_version": "0.1.0",
            },
            {
                "version": "2.0.0",
                "git_ref": "refs/tags/v2.0.0",
                "artifact_type": "source_archive",
                "artifact_url": "https://example.com/demo-plugin-2.0.0.zip",
                "min_app_version": "0.1.0",
            },
        ]
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=versions,
                latest_version="2.0.0",
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(manifest_version="1.0.0"),
            "https://example.com/demo-plugin-2.0.0.zip": self._build_plugin_archive(
                manifest_version="2.0.0",
                extra_required_field=True,
            ),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_switch_failure(self) -> FakeGitHubMarketplaceClient:
        versions = [
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
        ]
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=versions,
                latest_version="1.1.0",
            ),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(manifest_version="1.0.0"),
            "https://example.com/demo-plugin-1.1.0.zip": self._build_plugin_archive(manifest_version="1.1.1"),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_manifest_mismatch(self) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(manifest_version="1.0.1")
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [
                {"name": "demo-plugin", "type": "dir"},
            ],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": archive,
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    @staticmethod
    def _build_market_manifest(repo_url: str = MARKET_REPO_URL) -> dict:
        return {
            "market_id": "demo-market",
            "name": "Demo Market",
            "owner": "demo",
            "repo_url": repo_url,
            "default_branch": "main",
            "entry_root": "plugins",
            "trusted_level": "third_party",
        }

    @staticmethod
    def _build_entry_payload(
        versions: list[dict] | None = None,
        latest_version: str = "1.0.0",
        source_repo: str = PLUGIN_REPO_URL,
        permissions: list[str] | None = None,
    ) -> dict:
        resolved_versions = versions or [
            {
                "version": "1.0.0",
                "git_ref": "refs/tags/v1.0.0",
                "artifact_type": "source_archive",
                "artifact_url": "https://example.com/demo-plugin-1.0.0.zip",
                "min_app_version": "0.1.0",
            }
        ]
        return {
            "plugin_id": "demo-plugin",
            "name": "Demo Plugin",
            "summary": "A demo plugin for marketplace install tests.",
            "source_repo": source_repo,
            "manifest_path": "manifest.json",
            "readme_url": f"{source_repo}#readme",
            "publisher": {"name": "Demo Publisher", "url": "https://example.com"},
            "categories": ["demo"],
            "risk_level": "low",
            "permissions": permissions or ["device.read"],
            "latest_version": latest_version,
            "versions": resolved_versions,
            "install": {
                "requirements_path": "requirements.txt",
                "readme_path": "README.md",
            },
            "maintainers": [{"name": "Maintainer"}],
        }

    @staticmethod
    def _build_plugin_archive(
        *,
        manifest_version: str,
        extra_required_field: bool = False,
        permissions: list[str] | None = None,
        include_readme: bool = True,
        include_requirements: bool = True,
    ) -> bytes:
        config_fields = [
            {"key": "base_url", "label": "Base URL", "type": "string", "required": True},
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
        ]
        ui_fields = ["base_url", "api_key"]
        if extra_required_field:
            config_fields.append({"key": "tenant_id", "label": "Tenant ID", "type": "string", "required": True})
            ui_fields.append("tenant_id")
        manifest = {
            "id": "demo-plugin",
            "name": "Demo Plugin",
            "version": manifest_version,
            "types": ["integration"],
            "permissions": permissions or ["device.read"],
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
                        "fields": config_fields
                    },
                    "ui_schema": {
                        "sections": [
                            {
                                "id": "basic",
                                "title": "Basic",
                                "fields": ui_fields,
                            }
                        ]
                    },
                }
            ],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive_root = f"demo-plugin-{manifest_version}"
            archive.writestr(f"{archive_root}/manifest.json", json.dumps(manifest, ensure_ascii=False))
            if include_readme:
                archive.writestr(f"{archive_root}/README.md", "# Demo Plugin\n")
            if include_requirements:
                archive.writestr(f"{archive_root}/requirements.txt", "httpx>=0.28\n")
            archive.writestr(f"{archive_root}/plugin/__init__.py", "")
            archive.writestr(
                f"{archive_root}/plugin/integration.py",
                "def sync(payload=None):\n    return {'ok': True, 'payload': payload or {}}\n",
            )
        return buffer.getvalue()

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    unittest.main()

