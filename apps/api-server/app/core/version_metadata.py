from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.modules.plugin.versioning import compare_plugin_versions

BuildChannel = Literal["stable", "preview", "development"]
UpdateStatus = Literal["up_to_date", "update_available", "check_unavailable"]

# GitHub Release 仓库地址集中收口在这里，后续切仓只改这一处。
BUILTIN_RELEASE_REPOSITORY_URL = "https://github.com/jingyi0605/FamilyClaw"
GITHUB_RELEASE_API_BASE_URL = "https://api.github.com"
GITHUB_RELEASE_CHECK_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SystemVersionInfo:
    current_version: str
    build_channel: BuildChannel
    build_time: str | None = None
    release_notes_url: str | None = None
    update_status: UpdateStatus = "check_unavailable"
    latest_version: str | None = None
    latest_release_notes_url: str | None = None
    latest_release_title: str | None = None
    latest_release_summary: str | None = None
    latest_release_published_at: str | None = None


@dataclass(frozen=True)
class ReleaseUpdateInfo:
    update_status: UpdateStatus
    latest_version: str | None = None
    latest_release_notes_url: str | None = None
    latest_release_title: str | None = None
    latest_release_summary: str | None = None
    latest_release_published_at: str | None = None


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_build_channel(value: Any) -> BuildChannel | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None

    lowered = normalized.lower()
    if lowered in {"stable", "release", "production"}:
        return "stable"
    if lowered in {"preview", "pre-release", "prerelease", "rc", "beta"}:
        return "preview"
    if lowered in {"development", "dev", "local"}:
        return "development"
    return None


def _load_release_manifest() -> dict[str, Any]:
    manifest_path = Path(settings.release_manifest_path)
    if not manifest_path.exists() or not manifest_path.is_file():
        return {}

    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return loaded if isinstance(loaded, dict) else {}


def _infer_build_channel(*, current_version: str, explicit_channel: Any) -> BuildChannel:
    normalized_channel = _normalize_build_channel(explicit_channel)
    if normalized_channel is not None:
        return normalized_channel

    version_lower = current_version.lower()
    if "rc" in version_lower or "beta" in version_lower or "alpha" in version_lower:
        return "preview"
    if settings.environment.lower() == "development":
        return "development"
    return "stable"


def _resolve_release_notes_url(*, manifest: dict[str, Any], current_version: str) -> str | None:
    explicit_release_url = _normalize_optional_text(manifest.get("release_url")) or _normalize_optional_text(settings.release_url)
    if explicit_release_url is not None:
        return explicit_release_url

    repository_url = BUILTIN_RELEASE_REPOSITORY_URL
    if repository_url is None:
        return None

    git_tag = _normalize_optional_text(manifest.get("git_tag")) or _normalize_optional_text(settings.git_tag)
    if git_tag is None:
        git_tag = f"v{current_version}"
    return f"{repository_url.rstrip('/')}/releases/tag/{git_tag}"


def _parse_github_repo_path(repository_url: str) -> tuple[str, str] | None:
    parsed = urlparse(repository_url)
    if parsed.netloc.lower() != "github.com":
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    return owner, repo


def _normalize_release_version(value: Any) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    return normalized[1:] if normalized.startswith("v") else normalized


def _normalize_release_title(release: dict[str, Any], latest_version: str | None) -> str | None:
    explicit_name = _normalize_optional_text(release.get("name"))
    if explicit_name is not None:
        return explicit_name
    if latest_version is not None:
        return f"版本 {latest_version}"
    return None


def _clean_release_body_line(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned)
    cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_release_summary(value: Any) -> str | None:
    body = _normalize_optional_text(value)
    if body is None:
        return None

    summary_lines: list[str] = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if summary_lines:
                break
            continue
        if stripped.startswith("#"):
            continue

        cleaned = _clean_release_body_line(stripped)
        if not cleaned:
            continue

        summary_lines.append(cleaned)
        if len(" ".join(summary_lines)) >= 180:
            break

    if not summary_lines:
        return None

    summary = " ".join(summary_lines)
    if len(summary) > 180:
        return f"{summary[:177].rstrip()}..."
    return summary


def _pick_latest_release(
    releases: list[dict[str, Any]],
    *,
    build_channel: BuildChannel,
) -> dict[str, Any] | None:
    for release in releases:
        if not isinstance(release, dict):
            continue
        if bool(release.get("draft")):
            continue
        if build_channel == "stable" and bool(release.get("prerelease")):
            continue
        return release
    return None


def _fetch_release_update_info(*, current_version: str, build_channel: BuildChannel) -> ReleaseUpdateInfo:
    repo_path = _parse_github_repo_path(BUILTIN_RELEASE_REPOSITORY_URL)
    if repo_path is None:
        return ReleaseUpdateInfo(update_status="check_unavailable")

    owner, repo = repo_path
    api_url = f"{GITHUB_RELEASE_API_BASE_URL}/repos/{owner}/{repo}/releases?per_page=10"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FamilyClaw-VersionChecker",
    }
    if settings.plugin_marketplace_github_token:
        headers["Authorization"] = f"Bearer {settings.plugin_marketplace_github_token}"

    try:
        response = httpx.get(
            api_url,
            headers=headers,
            timeout=GITHUB_RELEASE_CHECK_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        releases = response.json()
    except (httpx.HTTPError, ValueError):
        return ReleaseUpdateInfo(update_status="check_unavailable")

    if not isinstance(releases, list):
        return ReleaseUpdateInfo(update_status="check_unavailable")

    latest_release = _pick_latest_release(releases, build_channel=build_channel)
    if latest_release is None:
        return ReleaseUpdateInfo(update_status="check_unavailable")

    latest_version = _normalize_release_version(latest_release.get("tag_name") or latest_release.get("name"))
    latest_release_url = _normalize_optional_text(latest_release.get("html_url"))
    latest_release_title = _normalize_release_title(latest_release, latest_version)
    latest_release_summary = _extract_release_summary(latest_release.get("body"))
    latest_release_published_at = _normalize_optional_text(latest_release.get("published_at"))
    if latest_version is None:
        return ReleaseUpdateInfo(
            update_status="check_unavailable",
            latest_release_notes_url=latest_release_url,
            latest_release_title=latest_release_title,
            latest_release_summary=latest_release_summary,
            latest_release_published_at=latest_release_published_at,
        )

    try:
        comparison = compare_plugin_versions(current_version, latest_version)
    except ValueError:
        return ReleaseUpdateInfo(
            update_status="check_unavailable",
            latest_version=latest_version,
            latest_release_notes_url=latest_release_url,
            latest_release_title=latest_release_title,
            latest_release_summary=latest_release_summary,
            latest_release_published_at=latest_release_published_at,
        )

    if comparison < 0:
        return ReleaseUpdateInfo(
            update_status="update_available",
            latest_version=latest_version,
            latest_release_notes_url=latest_release_url,
            latest_release_title=latest_release_title,
            latest_release_summary=latest_release_summary,
            latest_release_published_at=latest_release_published_at,
        )
    return ReleaseUpdateInfo(
        update_status="up_to_date",
        latest_version=latest_version,
        latest_release_notes_url=latest_release_url,
        latest_release_title=latest_release_title,
        latest_release_summary=latest_release_summary,
        latest_release_published_at=latest_release_published_at,
    )


def get_system_version_info() -> SystemVersionInfo:
    manifest = _load_release_manifest()
    current_version = (
        _normalize_optional_text(manifest.get("app_version"))
        or _normalize_optional_text(settings.app_version)
        or "0.0.0-dev"
    )
    build_channel = _infer_build_channel(
        current_version=current_version,
        explicit_channel=manifest.get("build_channel") or settings.build_channel,
    )
    release_update_info = _fetch_release_update_info(
        current_version=current_version,
        build_channel=build_channel,
    )

    return SystemVersionInfo(
        current_version=current_version,
        build_channel=build_channel,
        build_time=_normalize_optional_text(manifest.get("built_at")) or _normalize_optional_text(settings.build_time),
        release_notes_url=_resolve_release_notes_url(manifest=manifest, current_version=current_version),
        update_status=release_update_info.update_status,
        latest_version=release_update_info.latest_version,
        latest_release_notes_url=release_update_info.latest_release_notes_url,
        latest_release_title=release_update_info.latest_release_title,
        latest_release_summary=release_update_info.latest_release_summary,
        latest_release_published_at=release_update_info.latest_release_published_at,
    )
