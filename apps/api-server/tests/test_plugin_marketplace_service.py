import io
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401
import app.modules.plugin_marketplace.service as marketplace_service
from app.core.config import settings
from app.db.utils import new_uuid, utc_now_iso
from app.modules.household.schemas import HouseholdCreate
from app.modules.household.service import create_household
from app.modules.integration.models import IntegrationInstance
from app.modules.plugin.config_service import save_plugin_config_form
from app.modules.plugin.models import PluginMount
from app.modules.plugin.schemas import PluginConfigUpdateRequest, PluginStateUpdateRequest
from app.modules.plugin.service import (
    delete_household_plugin_installation,
    get_household_plugin,
    list_plugin_mounts,
    set_household_plugin_enabled,
)
from app.modules.plugin_marketplace.github_client import GitHubMarketplaceClientError
from app.modules.plugin_marketplace.models import (
    PluginMarketplaceEntrySnapshot,
    PluginMarketplaceInstance,
    PluginMarketplaceInstallTask,
    PluginMarketplaceSource,
)
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
    ensure_builtin_marketplace_source,
    get_marketplace_instance_for_household_plugin,
    get_marketplace_version_options,
    list_marketplace_catalog,
    list_marketplace_sources,
    operate_marketplace_instance_version,
    set_marketplace_instance_enabled,
    sync_marketplace_source,
)


MARKET_REPO_URL = "https://github.com/demo/marketplace"
OFFICIAL_MARKET_REPO_URL = "https://github.com/demo/official-marketplace"
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
        self.file_json_calls: dict[tuple[str, str, str], int] = {}

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
        self.file_json_calls[key] = self.file_json_calls.get(key, 0) + 1
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

        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_plugin_dev_root = settings.plugin_dev_root
        settings.plugin_dev_root = str((Path(self._tempdir.name) / "plugins-dev").resolve())
        self._db_helper = PostgresTestDatabase(test_id=self.id())
        self._db_helper.setup()
        self.db: Session = self._db_helper.SessionLocal()
        self._market_env_patch = patch(
            "app.modules.plugin_marketplace.service.prepare_plugin_python_env",
            side_effect=self._fake_prepare_plugin_python_env,
        )
        self._market_env_patch.start()
        self._service_env_patch = patch(
            "app.modules.plugin.service.prepare_plugin_python_env",
            side_effect=self._fake_prepare_plugin_python_env,
        )
        self._service_env_patch.start()
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
        self._service_env_patch.stop()
        self._market_env_patch.stop()
        self._db_helper.close()
        settings.plugin_dev_root = self._previous_plugin_dev_root
        self._tempdir.cleanup()

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

    def test_list_marketplace_sources_exposes_is_system_flag(self) -> None:
        sources = list_marketplace_sources(self.db)
        builtin_source = next(
            source
            for source in sources
            if source.source_id == marketplace_service.BUILTIN_MARKETPLACE_SOURCE_ID
        )
        self.assertTrue(builtin_source.is_system)

        client = self._build_client_for_install()
        new_source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=new_source.source_id, client=client)
        self.db.commit()

        refreshed_sources = list_marketplace_sources(self.db)
        third_party_source = next(item for item in refreshed_sources if item.repo_url == MARKET_REPO_URL)
        self.assertFalse(third_party_source.is_system)

    def test_ensure_builtin_marketplace_source_merges_legacy_official_duplicate_rows(self) -> None:
        client = self._build_client_for_official_version_switch()
        previous_repo = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL
        previous_branch = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH
        previous_entry_root = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL = OFFICIAL_MARKET_REPO_URL
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH = "main"
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT = "plugins"

        try:
            now = utc_now_iso()
            legacy_source = PluginMarketplaceSource(
                source_id="builtin-official-marketplace",
                market_id="legacy-market",
                name="旧官方市场",
                owner="legacy-owner",
                repo_url=OFFICIAL_MARKET_REPO_URL,
                repo_provider="github",
                api_base_url=None,
                mirror_repo_url=None,
                mirror_repo_provider=None,
                mirror_api_base_url=None,
                branch="main",
                entry_root="plugins",
                is_system=True,
                enabled=True,
                last_sync_status="success",
                last_sync_error_json=None,
                last_synced_at=now,
                created_at=now,
                updated_at=now,
            )
            builtin_source = PluginMarketplaceSource(
                source_id=marketplace_service.BUILTIN_MARKETPLACE_SOURCE_ID,
                market_id=None,
                name="内置插件市场",
                owner=None,
                repo_url=OFFICIAL_MARKET_REPO_URL,
                repo_provider="github",
                api_base_url=None,
                mirror_repo_url=None,
                mirror_repo_provider=None,
                mirror_api_base_url=None,
                branch="main",
                entry_root="plugins",
                is_system=True,
                enabled=True,
                last_sync_status="idle",
                last_sync_error_json=None,
                last_synced_at=None,
                created_at=now,
                updated_at=now,
            )
            legacy_snapshot = PluginMarketplaceEntrySnapshot(
                id=new_uuid(),
                source_id=legacy_source.source_id,
                plugin_id="demo-plugin",
                name="Demo Plugin",
                summary="legacy ready",
                source_repo=PLUGIN_REPO_URL,
                manifest_path="manifest.json",
                readme_url=f"{PLUGIN_REPO_URL}#readme",
                publisher_json="{}",
                categories_json="[]",
                permissions_json='["device.read"]',
                maintainers_json="[]",
                versions_json="[]",
                install_json="{}",
                repository_metrics_json=None,
                raw_entry_json="{}",
                risk_level="low",
                latest_version="1.1.0",
                manifest_digest="legacy-digest",
                sync_status="ready",
                sync_error_json=None,
                synced_at=now,
                created_at=now,
                updated_at=now,
            )
            builtin_snapshot = PluginMarketplaceEntrySnapshot(
                id=new_uuid(),
                source_id=builtin_source.source_id,
                plugin_id="demo-plugin",
                name="Demo Plugin",
                summary="builtin invalid",
                source_repo=PLUGIN_REPO_URL,
                manifest_path="manifest.json",
                readme_url=f"{PLUGIN_REPO_URL}#readme",
                publisher_json="{}",
                categories_json="[]",
                permissions_json="[]",
                maintainers_json="[]",
                versions_json="[]",
                install_json="{}",
                repository_metrics_json=None,
                raw_entry_json="{}",
                risk_level="low",
                latest_version="1.0.0",
                manifest_digest="builtin-digest",
                sync_status="invalid",
                sync_error_json='{"detail":"broken"}',
                synced_at=now,
                created_at=now,
                updated_at=now,
            )
            task = PluginMarketplaceInstallTask(
                id=new_uuid(),
                household_id=self.household_id,
                source_id=legacy_source.source_id,
                plugin_id="demo-plugin",
                requested_version="1.0.0",
                installed_version="1.0.0",
                install_status="installed",
                failure_stage=None,
                error_code=None,
                error_message=None,
                source_repo=PLUGIN_REPO_URL,
                market_repo=OFFICIAL_MARKET_REPO_URL,
                artifact_url="https://example.com/demo-plugin-1.0.0.zip",
                plugin_root="/tmp/demo-plugin",
                manifest_path="/tmp/demo-plugin/manifest.json",
                created_at=now,
                updated_at=now,
                started_at=now,
                finished_at=now,
            )
            instance = PluginMarketplaceInstance(
                id=new_uuid(),
                household_id=self.household_id,
                source_id=legacy_source.source_id,
                plugin_id="demo-plugin",
                installed_version="1.0.0",
                install_status="installed",
                enabled=False,
                config_status="configured",
                source_repo=PLUGIN_REPO_URL,
                market_repo=OFFICIAL_MARKET_REPO_URL,
                plugin_root="/tmp/demo-plugin",
                manifest_path="/tmp/demo-plugin/manifest.json",
                python_path="python",
                working_dir="/tmp/demo-plugin",
                installed_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(legacy_source)
            self.db.add(builtin_source)
            self.db.add(legacy_snapshot)
            self.db.add(builtin_snapshot)
            self.db.add(task)
            self.db.add(instance)
            self.db.commit()

            source = ensure_builtin_marketplace_source(self.db, client=client)
            self.db.commit()

            self.assertEqual(marketplace_service.BUILTIN_MARKETPLACE_SOURCE_ID, source.source_id)
            system_sources = [
                item
                for item in list_marketplace_sources(self.db, client=client)
                if item.repo_url == OFFICIAL_MARKET_REPO_URL and item.is_system
            ]
            self.assertEqual(1, len(system_sources))

            snapshots = list_marketplace_entry_snapshots(self.db, source_id=source.source_id)
            self.assertEqual(1, len(snapshots))
            self.assertEqual("ready", snapshots[0].sync_status)
            self.assertEqual("legacy-digest", snapshots[0].manifest_digest)

            tasks = list_marketplace_install_tasks(self.db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual(1, len(tasks))
            self.assertEqual(source.source_id, tasks[0].source_id)

            instance = get_marketplace_instance_for_household_plugin(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
            )
            assert instance is not None
            self.assertEqual(source.source_id, instance.source_id)
        finally:
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL = previous_repo
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH = previous_branch
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT = previous_entry_root

    def test_sync_marketplace_source_can_run_twice_without_duplicate_snapshot_conflict(self) -> None:
        client = self._build_client_for_install()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        first_result = sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        second_result = sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        self.assertEqual(1, first_result.ready_entries)
        self.assertEqual(1, second_result.ready_entries)

        snapshots = list_marketplace_entry_snapshots(self.db, source_id=source.source_id)
        self.assertEqual(1, len(snapshots))
        self.assertEqual("demo-plugin", snapshots[0].plugin_id)
        self.assertEqual("ready", snapshots[0].sync_status)

    def test_sync_marketplace_source_skips_unchanged_entries_when_digest_matches(self) -> None:
        client = self._build_client_for_incremental_sync()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        snapshots = list_marketplace_entry_snapshots(self.db, source_id=source.source_id)
        self.assertEqual(1, len(snapshots))
        first_snapshot_updated_at = snapshots[0].updated_at
        self.assertEqual("tree-demo-plugin-v1", snapshots[0].manifest_digest)

        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        refreshed_snapshots = list_marketplace_entry_snapshots(self.db, source_id=source.source_id)
        self.assertEqual(1, len(refreshed_snapshots))
        self.assertEqual(first_snapshot_updated_at, refreshed_snapshots[0].updated_at)
        self.assertEqual(
            1,
            client.file_json_calls[(MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main")],
        )

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
        expected_marketplace_root = Path(settings.plugin_marketplace_install_root).resolve()
        self.assertTrue(Path(task.plugin_root).resolve().is_relative_to(expected_marketplace_root))
        self.assertTrue(Path(instance.plugin_root).resolve().is_relative_to(expected_marketplace_root))

        plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
        self.assertEqual("installed", plugin.install_status)
        self.assertIsNotNone(plugin.marketplace_instance_id)
        self.assertEqual("subprocess_runner", plugin.execution_backend)

        enabled_instance = set_marketplace_instance_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
        )
        self.db.commit()

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

        self.assertTrue(enabled_instance.enabled)
        plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
        self.assertTrue(plugin.enabled)
        self.assertEqual("subprocess_runner", plugin.execution_backend)

    def test_plugins_dev_overrides_marketplace_runtime_but_preserves_marketplace_state(self) -> None:
        client = self._build_client_for_install()

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
        self.db.commit()

        dev_root = self._create_dev_plugin_fixture(plugin_id="demo-plugin", version="9.9.9", name="Dev Demo Plugin")

        plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
        self.assertEqual("9.9.9", plugin.version)
        self.assertEqual("marketplace", plugin.install_method)
        self.assertEqual("installed", plugin.install_status)
        self.assertIsNotNone(plugin.marketplace_instance_id)
        assert plugin.runner_config is not None
        self.assertEqual(str(dev_root.resolve()), str(Path(plugin.runner_config.plugin_root).resolve()))
        self.assertEqual(str((dev_root / "manifest.json").resolve()), str(Path(plugin.manifest_path).resolve()))

    def test_enabling_plugins_dev_disables_marketplace_variant_for_same_plugin(self) -> None:
        client = self._build_client_for_default_enabled_integration_install()

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
        self.db.commit()

        self._create_dev_plugin_fixture(plugin_id="demo-plugin", version="9.9.9", name="Dev Demo Plugin")

        installed_plugin = set_household_plugin_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True, runtime_source="installed"),
            updated_by="test-suite",
        )
        self.db.commit()

        self.assertTrue(installed_plugin.enabled)
        self.assertEqual("installed", installed_plugin.runtime_source)
        self.assertEqual(
            "installed",
            get_household_plugin(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
            ).runtime_source,
        )

        dev_plugin = set_household_plugin_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True, runtime_source="plugins_dev"),
            updated_by="test-suite",
        )
        self.db.commit()

        self.assertTrue(dev_plugin.enabled)
        self.assertEqual("plugins_dev", dev_plugin.runtime_source)

        active_plugin = get_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        installed_variant = get_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            runtime_source="installed",
        )
        dev_variant = get_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            runtime_source="plugins_dev",
        )
        marketplace_instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )

        self.assertEqual("plugins_dev", active_plugin.runtime_source)
        self.assertTrue(dev_variant.enabled)
        self.assertFalse(installed_variant.enabled)
        assert marketplace_instance is not None
        self.assertFalse(marketplace_instance.enabled)

    def test_marketplace_plugin_with_defaults_can_enable_and_create_default_instance(self) -> None:
        client = self._build_client_for_default_enabled_integration_install()

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
        self.db.commit()

        plugin = set_household_plugin_enabled(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
            payload=PluginStateUpdateRequest(enabled=True),
            updated_by="test-suite",
        )
        self.db.commit()

        self.assertTrue(plugin.enabled)

        marketplace_instance = get_marketplace_instance_for_household_plugin(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        assert marketplace_instance is not None
        self.assertTrue(marketplace_instance.enabled)

        integration_instance = self.db.scalar(
            select(IntegrationInstance).where(
                IntegrationInstance.household_id == self.household_id,
                IntegrationInstance.plugin_id == "demo-plugin",
            )
        )
        assert integration_instance is not None
        self.assertEqual("active", integration_instance.status)

    def test_install_accepts_repo_root_relative_manifest_and_dependency_paths(self) -> None:
        archive = self._build_plugin_archive(
            manifest_version="1.0.0",
            package_root="demo_plugin",
            repo_root_readme=True,
            repo_root_requirements=True,
        )
        client = FakeGitHubMarketplaceClient(
            files={
                (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
                (
                    MARKET_REPO_URL,
                    "plugins/demo-plugin/entry.json",
                    "main",
                ): self._build_entry_payload(
                    manifest_path="demo_plugin/manifest.json",
                    package_root="demo_plugin",
                    readme_path="README.md",
                    requirements_path="requirements.txt",
                ),
            },
            directories={
                (MARKET_REPO_URL, "plugins", "main"): [
                    {"name": "demo-plugin", "type": "dir"},
                ],
            },
            metadata={
                MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
                PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
            },
            downloads={
                "https://example.com/demo-plugin-1.0.0.zip": archive,
            },
        )

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
        self.assertTrue(Path(task.manifest_path).resolve().is_file())
        self.assertEqual("manifest.json", Path(task.manifest_path).name)

    def test_install_accepts_repo_root_manifest_with_nested_plugin_package(self) -> None:
        archive = self._build_plugin_archive(
            manifest_version="1.0.0",
            package_root="plugin",
            repo_root_manifest=True,
            repo_root_readme=True,
            repo_root_requirements=True,
        )
        client = FakeGitHubMarketplaceClient(
            files={
                (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
                (
                    MARKET_REPO_URL,
                    "plugins/demo-plugin/entry.json",
                    "main",
                ): self._build_entry_payload(
                    manifest_path="manifest.json",
                    package_root="plugin",
                    readme_path="README.md",
                    requirements_path="requirements.txt",
                ),
            },
            directories={
                (MARKET_REPO_URL, "plugins", "main"): [
                    {"name": "demo-plugin", "type": "dir"},
                ],
            },
            metadata={
                MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
                PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
            },
            downloads={
                "https://example.com/demo-plugin-1.0.0.zip": archive,
            },
        )

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

        installed_root = Path(task.plugin_root).resolve()
        self.assertEqual("installed", task.install_status)
        self.assertEqual(installed_root / "manifest.json", Path(task.manifest_path).resolve())
        self.assertTrue((installed_root / "plugin" / "__init__.py").is_file())
        self.assertTrue((installed_root / "requirements.txt").is_file())

    def test_version_options_mark_installable_versions_for_uninstalled_plugin(self) -> None:
        client = self._build_client_for_version_options()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        result = get_marketplace_version_options(
            self.db,
            source_id=source.source_id,
            plugin_id="demo-plugin",
            household_id=self.household_id,
        )

        self.assertEqual(["2.0.0", "1.2.0", "1.1.0", "1.0.0", "0.9.0"], [item.version for item in result.items])
        self.assertEqual("2.0.0", result.latest_version)
        self.assertEqual("1.1.0", result.latest_compatible_version)

        action_map = {item.version: item for item in result.items}
        self.assertEqual("install", action_map["1.1.0"].action)
        self.assertTrue(action_map["1.1.0"].can_install)
        self.assertFalse(action_map["1.1.0"].can_switch)
        self.assertTrue(action_map["1.1.0"].is_latest_compatible)

        self.assertEqual("unavailable", action_map["2.0.0"].action)
        self.assertEqual("host_too_old", action_map["2.0.0"].compatibility_status)
        self.assertIn("至少", action_map["2.0.0"].blocked_reason or "")

        self.assertEqual("unavailable", action_map["1.2.0"].action)
        self.assertEqual("unknown", action_map["1.2.0"].compatibility_status)
        self.assertIn("min_app_version", action_map["1.2.0"].blocked_reason or "")

    def test_version_options_mark_upgrade_rollback_current_and_unavailable_versions_for_installed_plugin(self) -> None:
        client = self._build_client_for_version_options()

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
        self.db.commit()

        result = get_marketplace_version_options(
            self.db,
            source_id=source.source_id,
            plugin_id="demo-plugin",
            household_id=self.household_id,
        )

        action_map = {item.version: item for item in result.items}

        self.assertEqual("upgrade", action_map["1.1.0"].action)
        self.assertTrue(action_map["1.1.0"].can_switch)
        self.assertFalse(action_map["1.1.0"].can_install)

        self.assertEqual("rollback", action_map["0.9.0"].action)
        self.assertTrue(action_map["0.9.0"].can_switch)

        self.assertEqual("current", action_map["1.0.0"].action)
        self.assertTrue(action_map["1.0.0"].is_installed)
        self.assertFalse(action_map["1.0.0"].can_switch)

        self.assertEqual("unavailable", action_map["2.0.0"].action)
        self.assertEqual("host_too_old", action_map["2.0.0"].compatibility_status)

        self.assertEqual("unavailable", action_map["1.2.0"].action)
        self.assertEqual("unknown", action_map["1.2.0"].compatibility_status)

    def test_version_options_mark_compatible_versions_unavailable_when_local_plugin_exists(self) -> None:
        client = self._build_client_for_version_options()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.add(
            PluginMount(
                id=new_uuid(),
                household_id=self.household_id,
                plugin_id="demo-plugin",
                source_type="third_party",
                install_method="local",
                execution_backend="subprocess_runner",
                manifest_path="C:/temp/demo-plugin/manifest.json",
                plugin_root="C:/temp/demo-plugin",
                python_path="python",
                working_dir="C:/temp/demo-plugin",
                enabled=False,
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
            )
        )
        self.db.commit()

        result = get_marketplace_version_options(
            self.db,
            source_id=source.source_id,
            plugin_id="demo-plugin",
            household_id=self.household_id,
        )

        action_map = {item.version: item for item in result.items}
        self.assertEqual("unavailable", action_map["1.1.0"].action)
        self.assertFalse(action_map["1.1.0"].can_install)
        self.assertIn("本地安装方式", action_map["1.1.0"].blocked_reason or "")

    def test_version_options_mark_compatible_versions_unavailable_when_builtin_conflicts(self) -> None:
        client = self._build_client_for_version_options()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        with patch(
            "app.modules.plugin_marketplace.service.list_registered_plugins",
            return_value=SimpleNamespace(items=[SimpleNamespace(id="demo-plugin")]),
        ):
            result = get_marketplace_version_options(
                self.db,
                source_id=source.source_id,
                plugin_id="demo-plugin",
                household_id=self.household_id,
            )

        action_map = {item.version: item for item in result.items}
        self.assertEqual("unavailable", action_map["1.1.0"].action)
        self.assertFalse(action_map["1.1.0"].can_install)
        self.assertIn("内置插件冲突", action_map["1.1.0"].blocked_reason or "")

    def test_create_marketplace_install_task_rejects_builtin_conflict_before_installing(self) -> None:
        client = self._build_client_for_install()

        source = add_marketplace_source(
            self.db,
            payload=MarketplaceSourceCreateRequest(repo_url=MARKET_REPO_URL),
            client=client,
        )
        sync_marketplace_source(self.db, source_id=source.source_id, client=client)
        self.db.commit()

        with patch(
            "app.modules.plugin_marketplace.service.list_registered_plugins",
            return_value=SimpleNamespace(items=[SimpleNamespace(id="demo-plugin")]),
        ):
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

        self.assertEqual("plugin_id_conflict", ctx.exception.error_code)

    def test_delete_household_plugin_installation_clears_marketplace_install_state(self) -> None:
        client = self._build_client_for_install()

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
        self.db.flush()

        delete_household_plugin_installation(
            self.db,
            household_id=self.household_id,
            plugin_id="demo-plugin",
        )
        self.db.commit()

        self.assertIsNone(
            get_marketplace_instance_for_household_plugin(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
            )
        )
        self.assertEqual([], list_marketplace_install_tasks(self.db, household_id=self.household_id, plugin_id="demo-plugin"))
        self.assertEqual([], list_plugin_mounts(self.db, household_id=self.household_id))

        catalog = list_marketplace_catalog(self.db, household_id=self.household_id)
        entry = next(item for item in catalog.items if item.plugin_id == "demo-plugin")
        self.assertEqual("not_installed", entry.install_state.install_status)
        self.assertIsNone(entry.install_state.instance_id)

    def test_builtin_marketplace_source_install_and_upgrade_keep_subprocess_runner_backend(self) -> None:
        client = self._build_client_for_official_version_switch()
        previous_repo = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL
        previous_branch = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH
        previous_entry_root = marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL = OFFICIAL_MARKET_REPO_URL
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH = "main"
        marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT = "plugins"

        try:
            source = ensure_builtin_marketplace_source(self.db, client=client)
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
            self.db.commit()

            installed_plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("third_party", installed_plugin.source_type)
            self.assertEqual("marketplace", installed_plugin.install_method)
            self.assertEqual("subprocess_runner", installed_plugin.execution_backend)
            self.assertEqual("1.0.0", installed_plugin.version)
            assert installed_plugin.runner_config is not None
            self.assertNotEqual(sys.executable, installed_plugin.runner_config.python_path)

            instance = get_marketplace_instance_for_household_plugin(
                self.db,
                household_id=self.household_id,
                plugin_id="demo-plugin",
            )
            assert instance is not None
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
            self.db.commit()

            upgraded_plugin = get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin")
            self.assertEqual("third_party", upgraded_plugin.source_type)
            self.assertEqual("marketplace", upgraded_plugin.install_method)
            self.assertEqual("subprocess_runner", upgraded_plugin.execution_backend)
            self.assertEqual("1.1.0", upgraded_plugin.version)
            assert upgraded_plugin.runner_config is not None
            self.assertNotEqual(sys.executable, upgraded_plugin.runner_config.python_path)
        finally:
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_REPO_URL = previous_repo
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_BRANCH = previous_branch
            marketplace_service.SYSTEM_PLUGIN_MARKETPLACE_ENTRY_ROOT = previous_entry_root

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
        self.assertEqual(
            "subprocess_runner",
            get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin").execution_backend,
        )

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
        self.assertEqual(
            "subprocess_runner",
            get_household_plugin(self.db, household_id=self.household_id, plugin_id="demo-plugin").execution_backend,
        )

    def test_version_switch_accepts_repo_root_manifest_with_nested_plugin_package(self) -> None:
        client = self._build_client_for_repo_root_manifest_version_switch()
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

        upgraded_root = Path(upgrade_result.instance.plugin_root).resolve()
        self.assertEqual("1.1.0", upgrade_result.instance.installed_version)
        self.assertEqual(upgraded_root / "manifest.json", Path(upgrade_result.instance.manifest_path).resolve())
        self.assertTrue((upgraded_root / "plugin" / "__init__.py").is_file())

    def test_upgrade_keeps_plugin_enabled_even_when_new_config_schema_breaks_old_config(self) -> None:
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
        self.assertTrue(result.instance.enabled)
        self.assertFalse(result.state_changed)
        self.assertIsNone(result.state_change_reason)

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

    def _build_client_for_default_enabled_integration_install(self) -> FakeGitHubMarketplaceClient:
        archive = self._build_plugin_archive(
            manifest_version="1.0.0",
            plugin_scope_uses_defaults=True,
            auto_create_default_instance=True,
            include_integration_instance_scope=True,
        )
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

    def _build_client_for_incremental_sync(self) -> FakeGitHubMarketplaceClient:
        files = {
            (MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(),
            (MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(),
        }
        directories = {
            (MARKET_REPO_URL, "plugins", "main"): [
                {"name": "demo-plugin", "type": "dir", "sha": "tree-demo-plugin-v1"},
            ],
        }
        metadata = {
            MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads={})

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

    def _build_client_for_official_version_switch(self) -> FakeGitHubMarketplaceClient:
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
            (OFFICIAL_MARKET_REPO_URL, "market.json", "main"): self._build_market_manifest(
                repo_url=OFFICIAL_MARKET_REPO_URL,
                is_system=True,
            ),
            (OFFICIAL_MARKET_REPO_URL, "plugins/demo-plugin/entry.json", "main"): self._build_entry_payload(
                versions=versions,
                latest_version="1.1.0",
            ),
        }
        directories = {
            (OFFICIAL_MARKET_REPO_URL, "plugins", "main"): [{"name": "demo-plugin", "type": "dir"}],
        }
        metadata = {
            OFFICIAL_MARKET_REPO_URL: {"default_branch": "main", "stargazers_count": 10, "forks_count": 2},
            PLUGIN_REPO_URL: {"default_branch": "main", "stargazers_count": 8, "forks_count": 1},
        }
        downloads = {
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(manifest_version="1.0.0"),
            "https://example.com/demo-plugin-1.1.0.zip": self._build_plugin_archive(manifest_version="1.1.0"),
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

    def _build_client_for_repo_root_manifest_version_switch(self) -> FakeGitHubMarketplaceClient:
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
                manifest_path="manifest.json",
                package_root="plugin",
                readme_path="README.md",
                requirements_path="requirements.txt",
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
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(
                manifest_version="1.0.0",
                package_root="plugin",
                repo_root_manifest=True,
                repo_root_readme=True,
                repo_root_requirements=True,
            ),
            "https://example.com/demo-plugin-1.1.0.zip": self._build_plugin_archive(
                manifest_version="1.1.0",
                package_root="plugin",
                repo_root_manifest=True,
                repo_root_readme=True,
                repo_root_requirements=True,
            ),
        }
        return FakeGitHubMarketplaceClient(files=files, directories=directories, metadata=metadata, downloads=downloads)

    def _build_client_for_version_options(self) -> FakeGitHubMarketplaceClient:
        versions = [
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
            "https://example.com/demo-plugin-0.9.0.zip": self._build_plugin_archive(manifest_version="0.9.0"),
            "https://example.com/demo-plugin-1.0.0.zip": self._build_plugin_archive(manifest_version="1.0.0"),
            "https://example.com/demo-plugin-1.1.0.zip": self._build_plugin_archive(manifest_version="1.1.0"),
            "https://example.com/demo-plugin-1.2.0.zip": self._build_plugin_archive(manifest_version="1.2.0"),
            "https://example.com/demo-plugin-2.0.0.zip": self._build_plugin_archive(manifest_version="2.0.0"),
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
    def _build_market_manifest(
        repo_url: str = MARKET_REPO_URL,
        legacy_trusted_level: str | None = None,
        is_system: bool | None = None,
    ) -> dict:
        payload = {
            "market_id": "demo-market",
            "name": "Demo Market",
            "owner": "demo",
            "repo_url": repo_url,
            "default_branch": "main",
            "entry_root": "plugins",
        }
        if legacy_trusted_level is None and is_system is not None:
            legacy_trusted_level = "official" if is_system else "third_party"
        if legacy_trusted_level is not None:
            payload["trusted_level"] = legacy_trusted_level
        return payload

    @staticmethod
    def _build_entry_payload(
        versions: list[dict] | None = None,
        latest_version: str = "1.0.0",
        source_repo: str = PLUGIN_REPO_URL,
        permissions: list[str] | None = None,
        manifest_path: str = "manifest.json",
        package_root: str | None = None,
        readme_path: str = "README.md",
        requirements_path: str = "requirements.txt",
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
            "manifest_path": manifest_path,
            "readme_url": f"{source_repo}#readme",
            "publisher": {"name": "Demo Publisher", "url": "https://example.com"},
            "categories": ["demo"],
            "risk_level": "low",
            "permissions": permissions or ["device.read"],
            "latest_version": latest_version,
            "versions": resolved_versions,
            "install": {
                "package_root": package_root,
                "requirements_path": requirements_path,
                "readme_path": readme_path,
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
        package_root: str | None = None,
        repo_root_manifest: bool = False,
        repo_root_readme: bool = False,
        repo_root_requirements: bool = False,
        plugin_scope_uses_defaults: bool = False,
        auto_create_default_instance: bool = False,
        include_integration_instance_scope: bool = False,
    ) -> bytes:
        if plugin_scope_uses_defaults:
            config_fields = [
                {"key": "provider_type", "label": "Provider Type", "type": "string", "required": True, "default": "demo"},
                {"key": "refresh_interval", "label": "Refresh Interval", "type": "integer", "required": False, "default": 30},
            ]
            ui_fields = ["provider_type", "refresh_interval"]
        else:
            config_fields = [
                {"key": "base_url", "label": "Base URL", "type": "string", "required": True},
                {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            ]
            ui_fields = ["base_url", "api_key"]
            if extra_required_field:
                config_fields.append({"key": "tenant_id", "label": "Tenant ID", "type": "string", "required": True})
                ui_fields.append("tenant_id")

        config_specs = [
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
        ]
        if include_integration_instance_scope:
            config_specs.append(
                {
                    "scope_type": "integration_instance",
                    "title": "Instance Config",
                    "schema_version": 1,
                    "config_schema": {
                        "fields": [
                            {
                                "key": "binding_type",
                                "label": "Binding Type",
                                "type": "string",
                                "required": True,
                                "default": "default_household",
                            }
                        ]
                    },
                    "ui_schema": {
                        "sections": [
                            {
                                "id": "instance",
                                "title": "Instance",
                                "fields": ["binding_type"],
                            }
                        ]
                    },
                }
            )
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
            "config_specs": config_specs,
        }
        if auto_create_default_instance:
            manifest["capabilities"] = {
                "integration": {
                    "domains": ["demo"],
                    "instance_model": "multi_instance",
                    "refresh_mode": "manual",
                    "supports_discovery": False,
                    "supports_actions": False,
                    "supports_cards": False,
                    "auto_create_default_instance": True,
                    "default_instance_display_name": "Demo Default",
                    "default_instance_config": {"binding_type": "default_household"},
                }
            }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive_root = f"demo-plugin-{manifest_version}"
            package_root_path = f"{archive_root}/{package_root}" if package_root else archive_root
            manifest_archive_path = f"{archive_root}/manifest.json" if repo_root_manifest else f"{package_root_path}/manifest.json"
            runtime_package_path = package_root_path if repo_root_manifest and package_root else f"{package_root_path}/plugin"
            archive.writestr(manifest_archive_path, json.dumps(manifest, ensure_ascii=False))
            if include_readme:
                readme_archive_path = f"{archive_root}/README.md" if repo_root_readme else f"{package_root_path}/README.md"
                archive.writestr(readme_archive_path, "# Demo Plugin\n")
            if include_requirements:
                requirements_archive_path = (
                    f"{archive_root}/requirements.txt" if repo_root_requirements else f"{package_root_path}/requirements.txt"
                )
                archive.writestr(requirements_archive_path, "httpx>=0.28\n")
            archive.writestr(f"{runtime_package_path}/__init__.py", "")
            archive.writestr(
                f"{runtime_package_path}/integration.py",
                "def sync(payload=None):\n    return {'ok': True, 'payload': payload or {}}\n",
            )
        return buffer.getvalue()

    def _create_dev_plugin_fixture(self, *, plugin_id: str, version: str, name: str) -> Path:
        plugin_root = Path(settings.plugin_dev_root) / plugin_id
        package_dir = plugin_root / "plugin"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (plugin_root / "manifest.json").write_text(
            json.dumps(
                {
                    "id": plugin_id,
                    "name": name,
                    "version": version,
                    "types": ["integration"],
                    "permissions": ["device.read"],
                    "risk_level": "low",
                    "triggers": ["manual"],
                    "entrypoints": {"integration": "plugin.integration.sync"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (plugin_root / "requirements.txt").write_text("", encoding="utf-8")
        (package_dir / "integration.py").write_text(
            "def sync(payload=None):\n    return {'ok': True}\n",
            encoding="utf-8",
        )
        return plugin_root

    @staticmethod
    def _fake_prepare_plugin_python_env(*, plugin_root, requirements_path=None, timeout_seconds=300, recreate=False):
        resolved_root = Path(plugin_root).resolve()
        venv_dir = resolved_root / ".familyclaw-venv"
        python_path = venv_dir / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
        python_path.parent.mkdir(parents=True, exist_ok=True)
        python_path.write_text("", encoding="utf-8")
        return SimpleNamespace(
            plugin_root=str(resolved_root),
            venv_dir=str(venv_dir),
            python_path=str(python_path),
            requirements_path=str(requirements_path or (resolved_root / "requirements.txt")),
            requirements_hash="test-hash",
            created=True,
            installed=True,
        )

    @staticmethod
    def _sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    unittest.main()

