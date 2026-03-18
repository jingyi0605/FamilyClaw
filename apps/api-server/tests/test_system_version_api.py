import json
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.system import router as system_router
from app.core.config import settings
from app.core.version_metadata import get_system_version_info


class SystemVersionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._previous_app_version = settings.app_version
        self._previous_environment = settings.environment
        self._previous_build_channel = settings.build_channel
        self._previous_build_time = settings.build_time
        self._previous_git_tag = settings.git_tag
        self._previous_release_url = settings.release_url
        self._previous_project_repository_url = settings.project_repository_url
        self._previous_release_manifest_path = settings.release_manifest_path

    def tearDown(self) -> None:
        settings.app_version = self._previous_app_version
        settings.environment = self._previous_environment
        settings.build_channel = self._previous_build_channel
        settings.build_time = self._previous_build_time
        settings.git_tag = self._previous_git_tag
        settings.release_url = self._previous_release_url
        settings.project_repository_url = self._previous_project_repository_url
        settings.release_manifest_path = self._previous_release_manifest_path
        self._tempdir.cleanup()

    @patch("app.core.version_metadata.httpx.get")
    def test_get_system_version_info_falls_back_to_development_defaults(self, get_mock) -> None:
        get_mock.side_effect = httpx.RequestError("network down")
        settings.app_version = "0.1.0"
        settings.environment = "development"
        settings.build_channel = None
        settings.build_time = None
        settings.release_url = None
        settings.project_repository_url = None
        settings.release_manifest_path = f"{self._tempdir.name}/missing-release-manifest.json"

        version_info = get_system_version_info()

        self.assertEqual("0.1.0", version_info.current_version)
        self.assertEqual("development", version_info.build_channel)
        self.assertIsNone(version_info.build_time)
        self.assertEqual(
            "https://github.com/familyclaw/FamilyClaw/releases/tag/v0.1.0",
            version_info.release_notes_url,
        )
        self.assertEqual("check_unavailable", version_info.update_status)
        self.assertIsNone(version_info.latest_version)
        self.assertIsNone(version_info.latest_release_notes_url)
        self.assertIsNone(version_info.latest_release_title)
        self.assertIsNone(version_info.latest_release_summary)
        self.assertIsNone(version_info.latest_release_published_at)

    @patch("app.core.version_metadata.httpx.get")
    def test_system_version_endpoint_prefers_release_manifest_metadata(self, get_mock) -> None:
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None
        response_mock.json.return_value = [
            {
                "tag_name": "v0.4.0",
                "name": "春季体验优化",
                "body": "家庭首页更清楚了，升级后的关键变化会直接告诉你。\n\n- 修复若干问题",
                "html_url": "https://github.com/familyclaw/FamilyClaw/releases/tag/v0.4.0",
                "published_at": "2026-03-18T18:30:00Z",
                "draft": False,
                "prerelease": False,
            },
            {
                "tag_name": "v0.3.0",
                "html_url": "https://github.com/familyclaw/FamilyClaw/releases/tag/v0.3.0",
                "draft": False,
                "prerelease": False,
            },
        ]
        get_mock.return_value = response_mock
        manifest_path = f"{self._tempdir.name}/release-manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "app_version": "0.3.0",
                    "git_tag": "v0.3.0",
                    "built_at": "2026-03-18T12:00:00Z",
                    "build_channel": "release",
                },
                handle,
                ensure_ascii=False,
            )

        settings.app_version = "0.1.0"
        settings.environment = "production"
        settings.build_channel = None
        settings.build_time = None
        settings.release_url = None
        settings.project_repository_url = None
        settings.release_manifest_path = manifest_path

        app = FastAPI()
        app.include_router(system_router, prefix=settings.api_v1_prefix)
        client = TestClient(app)

        response = client.get(f"{settings.api_v1_prefix}/system/version")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "current_version": "0.3.0",
                "build_channel": "stable",
                "build_time": "2026-03-18T12:00:00Z",
                "release_notes_url": "https://github.com/familyclaw/FamilyClaw/releases/tag/v0.3.0",
                "update_status": "update_available",
                "latest_version": "0.4.0",
                "latest_release_notes_url": "https://github.com/familyclaw/FamilyClaw/releases/tag/v0.4.0",
                "latest_release_title": "春季体验优化",
                "latest_release_summary": "家庭首页更清楚了，升级后的关键变化会直接告诉你。",
                "latest_release_published_at": "2026-03-18T18:30:00Z",
            },
            response.json(),
        )
        client.close()
