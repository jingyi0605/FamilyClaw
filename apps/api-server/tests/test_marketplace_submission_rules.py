import importlib.util
import unittest
from pathlib import Path

from app.modules.plugin_marketplace.schemas import MarketplaceEntry


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "marketplace"
    / "scripts"
    / "marketplace_submission_lib.py"
)
_SPEC = importlib.util.spec_from_file_location("marketplace_submission_lib_for_tests", SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def _build_entry_payload(*, versions: list[dict], latest_version: str) -> dict:
    return {
        "plugin_id": "demo-plugin",
        "name": "Demo Plugin",
        "summary": "A demo plugin for marketplace install tests.",
        "source_repo": "https://github.com/demo/demo-plugin",
        "manifest_path": "manifest.json",
        "readme_url": "https://github.com/demo/demo-plugin/blob/main/README.md",
        "publisher": {"name": "Demo Publisher", "url": "https://example.com"},
        "categories": ["demo"],
        "risk_level": "low",
        "permissions": ["device.read"],
        "latest_version": latest_version,
        "versions": versions,
        "install": {
            "package_root": "demo_plugin",
            "requirements_path": "requirements.txt",
            "readme_path": "README.md",
        },
        "maintainers": [{"name": "Maintainer"}],
    }


class MarketplaceSubmissionRuleTests(unittest.TestCase):
    def test_build_versions_normalizes_tags_and_sorts_desc(self) -> None:
        versions = _MODULE.build_versions(
            manifest_version="1.0.0",
            branch="main",
            source_repo_url="https://github.com/demo/demo-plugin",
            releases=[
                {
                    "tag_name": "v1.0.0",
                    "published_at": "2026-03-20T12:00:00Z",
                }
            ],
            tags=[
                {"name": "v0.9.0"},
                {"name": "v1.0.0"},
            ],
            min_app_version="0.1.0",
        )

        self.assertEqual(["1.0.0", "0.9.0"], [item["version"] for item in versions])
        self.assertEqual("refs/tags/v1.0.0", versions[0]["git_ref"])
        self.assertEqual("refs/tags/v0.9.0", versions[1]["git_ref"])
        self.assertEqual(
            "https://github.com/demo/demo-plugin/archive/refs/tags/v1.0.0.zip",
            versions[0]["artifact_url"],
        )

    def test_validate_generated_entry_rejects_multi_version_branch_ref(self) -> None:
        entry = _build_entry_payload(
            latest_version="1.0.0",
            versions=[
                {
                    "version": "1.0.0",
                    "git_ref": "main",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/main.zip",
                    "min_app_version": "0.1.0",
                },
                {
                    "version": "0.9.0",
                    "git_ref": "refs/tags/v0.9.0",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/refs/tags/v0.9.0.zip",
                    "min_app_version": "0.1.0",
                },
            ],
        )

        errors = _MODULE.validate_generated_entry(entry)

        self.assertTrue(any(item["field"] == "versions[0].git_ref" for item in errors))

    def test_validate_generated_entry_requires_latest_version_point_to_highest(self) -> None:
        entry = _build_entry_payload(
            latest_version="0.9.0",
            versions=[
                {
                    "version": "1.0.0",
                    "git_ref": "refs/tags/v1.0.0",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/refs/tags/v1.0.0.zip",
                    "min_app_version": "0.1.0",
                },
                {
                    "version": "0.9.0",
                    "git_ref": "refs/tags/v0.9.0",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/refs/tags/v0.9.0.zip",
                    "min_app_version": "0.1.0",
                },
            ],
        )

        errors = _MODULE.validate_generated_entry(entry)

        self.assertTrue(any(item["field"] == "latest_version" for item in errors))

    def test_marketplace_entry_model_rejects_multi_version_branch_ref(self) -> None:
        payload = _build_entry_payload(
            latest_version="1.0.0",
            versions=[
                {
                    "version": "1.0.0",
                    "git_ref": "main",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/main.zip",
                    "min_app_version": "0.1.0",
                },
                {
                    "version": "0.9.0",
                    "git_ref": "refs/tags/v0.9.0",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/refs/tags/v0.9.0.zip",
                    "min_app_version": "0.1.0",
                },
            ],
        )

        with self.assertRaises(ValueError):
            MarketplaceEntry.model_validate(payload)

    def test_marketplace_entry_model_accepts_single_version_branch_fallback(self) -> None:
        payload = _build_entry_payload(
            latest_version="0.1.0",
            versions=[
                {
                    "version": "0.1.0",
                    "git_ref": "main",
                    "artifact_type": "source_archive",
                    "artifact_url": "https://github.com/demo/demo-plugin/archive/main.zip",
                    "min_app_version": "0.1.0",
                }
            ],
        )

        entry = MarketplaceEntry.model_validate(payload)

        self.assertEqual("main", entry.versions[0].git_ref)
