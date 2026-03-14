from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.modules.plugin import repository as plugin_repository
from app.modules.plugin.models import PluginMount
from app.modules.plugin.runner_protocol import RunnerExecutionRequest
from app.modules.plugin.schemas import PluginManifest, PluginManifestRegionProviderSpec
from app.modules.region.providers import RegionProvider, RegionProviderExecutionError, region_provider_registry
from app.modules.region.schemas import RegionNodeRead

RUNNER_MODULE = "app.modules.plugin.runner_protocol"


class MountedPluginRegionProvider(RegionProvider):
    source_type = "third_party"

    def __init__(
        self,
        *,
        household_id: str,
        plugin_id: str,
        plugin_name: str,
        provider_code: str,
        country_code: str,
        entrypoint: str,
        mount: PluginMount,
    ) -> None:
        self.household_id = household_id
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.provider_code = provider_code
        self.country_code = country_code
        self.entrypoint = entrypoint
        self.mount = mount

    def list_children(
        self,
        db: Session,
        *,
        parent_region_code: str | None = None,
        admin_level: str | None = None,
    ) -> list[RegionNodeRead]:
        payload = self._invoke(
            operation="list_children",
            args={
                "parent_region_code": parent_region_code,
                "admin_level": admin_level,
            },
        )
        if not isinstance(payload, list):
            raise RegionProviderExecutionError(f"地区 provider {self.provider_code} 返回了非法 children 列表")
        return [self._to_region_node_read(item) for item in payload]

    def search(
        self,
        db: Session,
        *,
        keyword: str,
        admin_level: str | None = None,
        parent_region_code: str | None = None,
    ) -> list[RegionNodeRead]:
        payload = self._invoke(
            operation="search",
            args={
                "keyword": keyword,
                "admin_level": admin_level,
                "parent_region_code": parent_region_code,
            },
        )
        if not isinstance(payload, list):
            raise RegionProviderExecutionError(f"地区 provider {self.provider_code} 返回了非法 search 结果")
        return [self._to_region_node_read(item) for item in payload]

    def resolve(self, db: Session, *, region_code: str) -> RegionNodeRead | None:
        payload = self._invoke(operation="resolve", args={"region_code": region_code})
        if payload is None:
            return None
        return self._to_region_node_read(payload)

    def build_snapshot(self, node: RegionNodeRead) -> dict[str, object]:
        payload = self._invoke(operation="build_snapshot", args={"node": node.model_dump(mode="json")})
        if not isinstance(payload, dict):
            raise RegionProviderExecutionError(f"地区 provider {self.provider_code} 返回了非法 snapshot")
        payload.setdefault("provider_code", self.provider_code)
        payload.setdefault("country_code", self.country_code)
        return payload

    def _invoke(self, *, operation: str, args: dict[str, object]) -> object:
        runner_request = RunnerExecutionRequest(
            plugin_id=self.plugin_id,
            plugin_type="region-provider",
            entrypoint=self.entrypoint,
            payload={
                "operation": operation,
                "provider_code": self.provider_code,
                "country_code": self.country_code,
                **args,
            },
            trigger="region-provider",
            plugin_root=self.mount.plugin_root,
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = _build_pythonpath(self.mount.plugin_root)
        command = [self.mount.python_path, "-m", RUNNER_MODULE]
        cwd = self.mount.working_dir or self.mount.plugin_root

        try:
            completed = subprocess.run(
                command,
                input=runner_request.model_dump_json(),
                text=True,
                capture_output=True,
                timeout=self.mount.timeout_seconds,
                cwd=cwd,
                env=env,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RegionProviderExecutionError(f"地区 provider runner 启动失败: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RegionProviderExecutionError(f"地区 provider 执行超时: {self.provider_code}") from exc
        except OSError as exc:
            raise RegionProviderExecutionError(f"地区 provider runner 启动失败: {exc}") from exc

        stdout = _trim_output(completed.stdout, self.mount.stdout_limit_bytes)
        stderr = _trim_output(completed.stderr, self.mount.stderr_limit_bytes)
        if completed.returncode != 0:
            message = stderr or stdout or f"地区 provider 执行失败，退出码: {completed.returncode}"
            raise RegionProviderExecutionError(message)

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RegionProviderExecutionError(f"地区 provider 返回了非法 JSON: {exc.msg}") from exc

    def _to_region_node_read(self, payload: object) -> RegionNodeRead:
        if not isinstance(payload, dict):
            raise RegionProviderExecutionError(f"地区 provider {self.provider_code} 返回了非法节点")
        normalized_payload = dict(payload)
        normalized_payload.setdefault("provider_code", self.provider_code)
        normalized_payload.setdefault("country_code", self.country_code)
        try:
            return RegionNodeRead.model_validate(normalized_payload)
        except ValidationError as exc:
            raise RegionProviderExecutionError(f"地区 provider {self.provider_code} 节点结构不合法") from exc


def sync_household_plugin_region_providers(db: Session, household_id: str) -> None:
    region_provider_registry.clear_scope(household_id)
    for mount in plugin_repository.list_plugin_mounts(db, household_id=household_id):
        if not mount.enabled:
            continue
        manifest = _load_plugin_manifest(mount.manifest_path)
        spec = get_runtime_region_provider_spec(manifest)
        if spec is None:
            continue
        for provider in build_mounted_region_providers(
            household_id=household_id,
            mount=mount,
            manifest=manifest,
            spec=spec,
        ):
            region_provider_registry.register(provider, household_id=household_id)


def get_runtime_region_provider_spec(manifest: PluginManifest) -> PluginManifestRegionProviderSpec | None:
    spec = manifest.capabilities.region_provider
    if spec is None or spec.reserved:
        return None
    if "region-provider" not in manifest.types:
        return None
    return spec


def build_mounted_region_providers(
    *,
    household_id: str,
    mount: PluginMount,
    manifest: PluginManifest,
    spec: PluginManifestRegionProviderSpec,
) -> list[MountedPluginRegionProvider]:
    if spec.provider_code is None or spec.entrypoint is None or not spec.country_codes:
        raise RegionProviderExecutionError(f"地区 provider 插件声明不完整: {manifest.id}")
    return [
        MountedPluginRegionProvider(
            household_id=household_id,
            plugin_id=manifest.id,
            plugin_name=manifest.name,
            provider_code=spec.provider_code,
            country_code=country_code,
            entrypoint=spec.entrypoint,
            mount=mount,
        )
        for country_code in spec.country_codes
    ]


def _load_plugin_manifest(manifest_path: str | Path) -> PluginManifest:
    path = Path(manifest_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PluginManifest.model_validate(payload)


def _build_pythonpath(plugin_root: str) -> str:
    path_items = [str(BASE_DIR), str(Path(plugin_root).resolve())]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        path_items.append(existing)
    return os.pathsep.join(path_items)


def _trim_output(content: str, byte_limit: int) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= byte_limit:
        return content
    return encoded[:byte_limit].decode("utf-8", errors="ignore")
