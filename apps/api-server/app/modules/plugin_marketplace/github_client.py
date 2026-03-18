from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.modules.plugin_marketplace.schemas import MarketplaceRepoProvider


GITHUB_API_BASE_URL = "https://api.github.com"
GITLAB_API_BASE_URL = "https://gitlab.com/api/v4"
GITEE_API_BASE_URL = "https://gitee.com/api/v5"


@dataclass(slots=True)
class GitRepoRef:
    provider: MarketplaceRepoProvider
    repo_url: str
    api_base_url: str
    scheme: str
    host: str
    namespace: str
    repo: str
    project_path: str


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

    def parse_repo_url(
        self,
        repo_url: str,
        *,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> GitRepoRef:
        normalized_repo_url, parsed = self._normalize_repo_url(repo_url)
        provider = self._resolve_repo_provider(parsed=parsed, explicit_provider=repo_provider)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2:
            raise GitHubMarketplaceClientError(
                "仓库地址缺少 owner 或 repo。",
                error_code="invalid_market_repo",
            )

        if provider == "gitlab":
            namespace = "/".join(segments[:-1])
            repo = segments[-1]
            normalized_repo_url = f"{parsed.scheme}://{parsed.netloc}/{'/'.join(segments)}"
        else:
            namespace = segments[0]
            repo = segments[1]
            normalized_repo_url = f"{parsed.scheme}://{parsed.netloc}/{namespace}/{repo}"

        return GitRepoRef(
            provider=provider,
            repo_url=normalized_repo_url,
            api_base_url=self._resolve_api_base_url(parsed=parsed, provider=provider, explicit_api_base_url=api_base_url),
            scheme=parsed.scheme,
            host=parsed.netloc,
            namespace=namespace,
            repo=repo,
            project_path=f"{namespace}/{repo}" if provider != "gitlab" else f"{namespace}/{repo}",
        )

    def get_file_json(
        self,
        *,
        repo_url: str,
        path: str,
        ref: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> dict[str, Any]:
        payload = self.get_file_text(
            repo_url=repo_url,
            path=path,
            ref=ref,
            repo_provider=repo_provider,
            api_base_url=api_base_url,
        )
        try:
            return json.loads(payload)
        except ValueError as exc:
            raise GitHubMarketplaceClientError(
                f"仓库文件不是合法 JSON: {path}",
                error_code="market_repo_structure_invalid",
            ) from exc

    def get_file_text(
        self,
        *,
        repo_url: str,
        path: str,
        ref: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> str:
        repo = self.parse_repo_url(repo_url, repo_provider=repo_provider, api_base_url=api_base_url)
        path_value = path.strip("/")
        if repo.provider == "gitlab":
            url = (
                f"{repo.api_base_url}/projects/{quote(repo.project_path, safe='')}"
                f"/repository/files/{quote(path_value, safe='')}/raw"
            )
            response = self._request(
                "GET",
                url,
                params={"ref": ref},
                error_code="market_sync_failed",
            )
            return response.text

        payload = self._request_json(
            f"{repo.api_base_url}/repos/{repo.namespace}/{repo.repo}/contents/{path_value}",
            params={"ref": ref},
            error_code="market_sync_failed",
        )
        if isinstance(payload, list):
            raise GitHubMarketplaceClientError(
                f"期望读取文件，但拿到的是目录: {path}",
                error_code="market_repo_structure_invalid",
            )
        content = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            raise GitHubMarketplaceClientError(
                f"仓库文件内容不可读取: {path}",
                error_code="market_sync_failed",
            )
        try:
            return base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubMarketplaceClientError(
                f"仓库文件解码失败: {path}",
                error_code="market_sync_failed",
            ) from exc

    def list_directory(
        self,
        *,
        repo_url: str,
        path: str,
        ref: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> list[dict[str, Any]]:
        repo = self.parse_repo_url(repo_url, repo_provider=repo_provider, api_base_url=api_base_url)
        path_value = path.strip("/")
        if repo.provider == "gitlab":
            return self._list_gitlab_directory(repo=repo, path=path_value, ref=ref)

        payload = self._request_json(
            f"{repo.api_base_url}/repos/{repo.namespace}/{repo.repo}/contents/{path_value}",
            params={"ref": ref},
            error_code="market_sync_failed",
        )
        if not isinstance(payload, list):
            raise GitHubMarketplaceClientError(
                f"期望读取目录，但拿到的是文件: {path}",
                error_code="market_repo_structure_invalid",
            )
        return [self._normalize_directory_item(item) for item in payload if isinstance(item, dict)]

    def get_repository_metadata(
        self,
        *,
        repo_url: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> dict[str, Any]:
        repo = self.parse_repo_url(repo_url, repo_provider=repo_provider, api_base_url=api_base_url)
        if repo.provider == "gitlab":
            url = f"{repo.api_base_url}/projects/{quote(repo.project_path, safe='')}"
        else:
            url = f"{repo.api_base_url}/repos/{repo.namespace}/{repo.repo}"
        payload = self._request_json(url, error_code="repository_metrics_unavailable", allow_404=True)
        if not isinstance(payload, dict):
            raise GitHubMarketplaceClientError(
                "仓库元数据读取失败。",
                error_code="repository_metrics_unavailable",
            )
        return payload

    def get_repository_views(
        self,
        *,
        repo_url: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> dict[str, Any] | None:
        repo = self.parse_repo_url(repo_url, repo_provider=repo_provider, api_base_url=api_base_url)
        if repo.provider != "github" or not self._token:
            return None
        url = f"{repo.api_base_url}/repos/{repo.namespace}/{repo.repo}/traffic/views"
        try:
            payload = self._request_json(
                url,
                error_code="repository_metrics_unavailable",
                require_auth=True,
                allow_404=True,
                provider=repo.provider,
            )
        except GitHubMarketplaceClientError:
            return None
        return payload if isinstance(payload, dict) else None

    def build_source_archive_url(
        self,
        *,
        repo_url: str,
        git_ref: str,
        repo_provider: MarketplaceRepoProvider | None = None,
        api_base_url: str | None = None,
    ) -> str:
        repo = self.parse_repo_url(repo_url, repo_provider=repo_provider, api_base_url=api_base_url)
        normalized_ref = git_ref.strip().strip("/")
        if not normalized_ref:
            raise GitHubMarketplaceClientError(
                "source_archive 必须提供 git_ref。",
                error_code="market_repo_structure_invalid",
            )
        encoded_ref = quote(normalized_ref, safe="")
        if repo.provider == "gitlab":
            return f"{repo.repo_url}/-/archive/{encoded_ref}/{repo.repo}-{encoded_ref}.zip"
        if repo.provider == "gitee":
            return f"{repo.repo_url}/repository/archive/{encoded_ref}.zip"
        return f"{repo.repo_url}/archive/{normalized_ref}.zip"

    def download_binary(self, url: str) -> bytes:
        headers = self._build_headers(require_auth=False, provider="github")
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

    def _normalize_repo_url(self, repo_url: str) -> tuple[str, Any]:
        normalized = repo_url.strip()
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise GitHubMarketplaceClientError(
                "仓库地址必须是合法的 http/https 地址。",
                error_code="invalid_market_repo",
            )
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        normalized_repo_url = f"{parsed.scheme}://{parsed.netloc}{path}"
        return normalized_repo_url, urlparse(normalized_repo_url)

    def _resolve_repo_provider(
        self,
        *,
        parsed,
        explicit_provider: MarketplaceRepoProvider | None,
    ) -> MarketplaceRepoProvider:
        if explicit_provider is not None:
            return explicit_provider
        host = parsed.netloc.lower()
        if host == "github.com":
            return "github"
        if host == "gitlab.com":
            return "gitlab"
        if host == "gitee.com":
            return "gitee"
        raise GitHubMarketplaceClientError(
            "无法从仓库地址自动识别仓库类型，请显式提供 repo_provider。",
            error_code="invalid_market_repo",
        )

    def _resolve_api_base_url(
        self,
        *,
        parsed,
        provider: MarketplaceRepoProvider,
        explicit_api_base_url: str | None,
    ) -> str:
        if explicit_api_base_url is not None:
            return explicit_api_base_url.strip().rstrip("/")
        if provider == "github":
            if parsed.netloc.lower() == "github.com":
                return GITHUB_API_BASE_URL
            return f"{parsed.scheme}://{parsed.netloc}/api/v3"
        if provider == "gitlab":
            if parsed.netloc.lower() == "gitlab.com":
                return GITLAB_API_BASE_URL
            return f"{parsed.scheme}://{parsed.netloc}/api/v4"
        if provider == "gitee":
            return GITEE_API_BASE_URL if parsed.netloc.lower() == "gitee.com" else f"{parsed.scheme}://{parsed.netloc}/api/v5"
        return f"{parsed.scheme}://{parsed.netloc}/api/v1"

    def _normalize_directory_item(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_type = str(item.get("type") or "").strip().lower()
        normalized_type = "dir" if raw_type in {"dir", "tree"} else "file"
        return {
            **item,
            "type": normalized_type,
        }

    def _list_gitlab_directory(self, *, repo: GitRepoRef, path: str, ref: str) -> list[dict[str, Any]]:
        base_url = f"{repo.api_base_url}/projects/{quote(repo.project_path, safe='')}/repository/tree"
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            payload = self._request_json(
                base_url,
                params={"path": path, "ref": ref, "per_page": 100, "page": page},
                error_code="market_sync_failed",
            )
            if not isinstance(payload, list):
                raise GitHubMarketplaceClientError(
                    f"期望读取目录，但仓库 API 返回了非法结构: {path}",
                    error_code="market_repo_structure_invalid",
                )
            if not payload:
                break
            items.extend(
                {
                    **item,
                    "type": "dir" if item.get("type") == "tree" else "file",
                }
                for item in payload
                if isinstance(item, dict)
            )
            if len(payload) < 100:
                break
            page += 1
        return items

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        error_code: str,
        require_auth: bool = False,
        allow_404: bool = False,
        provider: MarketplaceRepoProvider = "github",
    ) -> Any:
        response = self._request(
            "GET",
            url,
            params=params,
            error_code=error_code,
            require_auth=require_auth,
            allow_404=allow_404,
            provider=provider,
        )
        if allow_404 and response.status_code == 404:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise GitHubMarketplaceClientError(
                "仓库 API 返回了不可解析的 JSON。",
                error_code=error_code,
                status_code=502,
            ) from exc

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        error_code: str,
        require_auth: bool = False,
        allow_404: bool = False,
        provider: MarketplaceRepoProvider = "github",
    ) -> httpx.Response:
        headers = self._build_headers(require_auth=require_auth, provider=provider)
        try:
            response = httpx.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds,
            )
            if allow_404 and response.status_code == 404:
                return response
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                detail = "仓库、分支或文件不存在。"
            elif status_code == 403:
                detail = "仓库 API 当前不可读，可能被限流或缺少权限。"
            else:
                detail = f"仓库 API 请求失败: {status_code}"
            raise GitHubMarketplaceClientError(detail, error_code=error_code, status_code=502) from exc
        except httpx.RequestError as exc:
            raise GitHubMarketplaceClientError(
                "仓库 API 请求失败，网络不可用。",
                error_code=error_code,
                status_code=502,
            ) from exc
        return response

    def _build_headers(self, *, require_auth: bool, provider: MarketplaceRepoProvider) -> dict[str, str]:
        headers = {
            "User-Agent": "FamilyClaw-Plugin-Marketplace",
        }
        token = (self._token or "").strip()
        if provider == "github":
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if token:
                headers["Authorization"] = f"Bearer {token}"
            elif require_auth:
                raise GitHubMarketplaceClientError(
                    "当前没有配置 GitHub Token，无法读取需要授权的仓库指标。",
                    error_code="repository_metrics_unavailable",
                )
            return headers
        if require_auth:
            raise GitHubMarketplaceClientError(
                "当前仓库类型没有配置鉴权支持。",
                error_code="repository_metrics_unavailable",
            )
        return headers


def build_github_marketplace_client() -> GitHubMarketplaceClient:
    return GitHubMarketplaceClient(token=settings.plugin_marketplace_github_token)
