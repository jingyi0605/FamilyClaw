from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


GITHUB_API_BASE_URL = "https://api.github.com"


@dataclass(slots=True)
class GitHubRepoRef:
    owner: str
    repo: str


class GitHubMarketplaceClientError(ValueError):
    def __init__(self, detail: str, *, error_code: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code


class GitHubMarketplaceClient:
    def __init__(self, *, token: str | None = None, timeout_seconds: float = 20.0) -> None:
        self._token = token
        self._timeout_seconds = timeout_seconds

    def parse_repo_url(self, repo_url: str) -> GitHubRepoRef:
        normalized = repo_url.strip().rstrip("/")
        prefix = "https://github.com/"
        if not normalized.startswith(prefix):
            raise GitHubMarketplaceClientError(
                "仓库地址必须是 GitHub 仓库地址。",
                error_code="invalid_market_repo",
            )
        segments = [segment for segment in normalized.removeprefix(prefix).split("/") if segment]
        if len(segments) < 2:
            raise GitHubMarketplaceClientError(
                "仓库地址缺少 owner 或 repo。",
                error_code="invalid_market_repo",
            )
        return GitHubRepoRef(owner=segments[0], repo=segments[1])

    def get_file_json(self, *, repo_url: str, path: str, ref: str) -> dict[str, Any]:
        payload = self.get_file_text(repo_url=repo_url, path=path, ref=ref)
        try:
            return json.loads(payload)
        except ValueError as exc:
            raise GitHubMarketplaceClientError(
                f"GitHub 文件不是合法 JSON: {path}",
                error_code="market_repo_structure_invalid",
            ) from exc

    def get_file_text(self, *, repo_url: str, path: str, ref: str) -> str:
        repo = self.parse_repo_url(repo_url)
        path_value = path.strip("/")
        url = f"{GITHUB_API_BASE_URL}/repos/{repo.owner}/{repo.repo}/contents/{path_value}"
        payload = self._request_json(url, params={"ref": ref}, error_code="market_sync_failed")
        if isinstance(payload, list):
            raise GitHubMarketplaceClientError(
                f"期望读取文件，但拿到的是目录: {path}",
                error_code="market_repo_structure_invalid",
            )
        content = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            raise GitHubMarketplaceClientError(
                f"GitHub 文件内容不可读取: {path}",
                error_code="market_sync_failed",
            )
        try:
            return base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubMarketplaceClientError(
                f"GitHub 文件解码失败: {path}",
                error_code="market_sync_failed",
            ) from exc

    def list_directory(self, *, repo_url: str, path: str, ref: str) -> list[dict[str, Any]]:
        repo = self.parse_repo_url(repo_url)
        path_value = path.strip("/")
        url = f"{GITHUB_API_BASE_URL}/repos/{repo.owner}/{repo.repo}/contents/{path_value}"
        payload = self._request_json(url, params={"ref": ref}, error_code="market_sync_failed")
        if not isinstance(payload, list):
            raise GitHubMarketplaceClientError(
                f"期望读取目录，但拿到的是文件: {path}",
                error_code="market_repo_structure_invalid",
            )
        return [item for item in payload if isinstance(item, dict)]

    def get_repository_metadata(self, *, repo_url: str) -> dict[str, Any]:
        repo = self.parse_repo_url(repo_url)
        url = f"{GITHUB_API_BASE_URL}/repos/{repo.owner}/{repo.repo}"
        payload = self._request_json(url, error_code="repository_metrics_unavailable", allow_404=True)
        if not isinstance(payload, dict):
            raise GitHubMarketplaceClientError(
                "GitHub 仓库元数据读取失败。",
                error_code="repository_metrics_unavailable",
            )
        return payload

    def get_repository_views(self, *, repo_url: str) -> dict[str, Any] | None:
        if not self._token:
            return None
        repo = self.parse_repo_url(repo_url)
        url = f"{GITHUB_API_BASE_URL}/repos/{repo.owner}/{repo.repo}/traffic/views"
        try:
            payload = self._request_json(
                url,
                error_code="repository_metrics_unavailable",
                require_auth=True,
                allow_404=True,
            )
        except GitHubMarketplaceClientError:
            return None
        return payload if isinstance(payload, dict) else None

    def download_binary(self, url: str) -> bytes:
        headers = self._build_headers(require_auth=False)
        try:
            response = httpx.get(url, headers=headers, timeout=self._timeout_seconds, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GitHubMarketplaceClientError(
                f"下载插件产物失败: {exc.response.status_code}",
                error_code="download_failed",
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            raise GitHubMarketplaceClientError(
                "下载插件产物失败，网络不可用。",
                error_code="download_failed",
                status_code=502,
            ) from exc
        return response.content

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        error_code: str,
        require_auth: bool = False,
        allow_404: bool = False,
    ) -> Any:
        headers = self._build_headers(require_auth=require_auth)
        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )
            if allow_404 and response.status_code == 404:
                return None
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                detail = "GitHub 仓库、分支或文件不存在。"
            elif status_code == 403:
                detail = "GitHub API 当前不可读，可能被限流或缺少权限。"
            else:
                detail = f"GitHub API 请求失败: {status_code}"
            raise GitHubMarketplaceClientError(detail, error_code=error_code, status_code=502) from exc
        except httpx.RequestError as exc:
            raise GitHubMarketplaceClientError(
                "GitHub API 请求失败，网络不可用。",
                error_code=error_code,
                status_code=502,
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubMarketplaceClientError(
                "GitHub API 返回了不可解析的 JSON。",
                error_code=error_code,
                status_code=502,
            ) from exc

    def _build_headers(self, *, require_auth: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "FamilyClaw-Plugin-Marketplace",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = (self._token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif require_auth:
            raise GitHubMarketplaceClientError(
                "当前没有配置 GitHub Token，无法读取需要授权的仓库指标。",
                error_code="repository_metrics_unavailable",
            )
        return headers


def build_github_marketplace_client() -> GitHubMarketplaceClient:
    return GitHubMarketplaceClient(token=settings.plugin_marketplace_github_token)
