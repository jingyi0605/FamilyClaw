from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Iterable

from .schemas import PluginRegistryItem


_PACKAGE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def collect_plugin_import_roots(plugin: PluginRegistryItem) -> list[str]:
    roots: set[str] = set()
    for entrypoint in plugin.entrypoints.model_dump(mode="json", exclude_none=True).values():
        if not isinstance(entrypoint, str):
            continue
        module_path, separator, _ = entrypoint.rpartition(".")
        if not separator or not module_path:
            continue
        root = module_path.split(".", 1)[0].strip()
        if _PACKAGE_NAME_PATTERN.fullmatch(root):
            roots.add(root)
    return sorted(roots)


@contextmanager
def plugin_runtime_paths(
    plugin_root: str | Path | None,
    *,
    package_names: Iterable[str] | None = None,
):
    if not plugin_root:
        yield []
        return

    resolved_root = Path(plugin_root).resolve()
    candidate_paths = [str(resolved_root.parent), str(resolved_root)]
    shim_root = _build_package_shim_root(resolved_root, package_names=package_names)
    if shim_root is not None:
        candidate_paths.insert(0, str(shim_root))

    try:
        yield candidate_paths
    finally:
        if shim_root is not None:
            shutil.rmtree(shim_root, ignore_errors=True)


@contextmanager
def plugin_runtime_import_path(
    plugin_root: str | Path | None,
    *,
    package_names: Iterable[str] | None = None,
):
    with plugin_runtime_paths(plugin_root, package_names=package_names) as candidate_paths:
        inserted_paths: list[str] = []
        for candidate in candidate_paths:
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
                inserted_paths.append(candidate)
        try:
            yield
        finally:
            for candidate in reversed(inserted_paths):
                try:
                    sys.path.remove(candidate)
                except ValueError:
                    pass


def _build_package_shim_root(plugin_root: Path, *, package_names: Iterable[str] | None) -> Path | None:
    normalized_package_names = _normalize_package_names(package_names)
    shim_targets = [
        package_name
        for package_name in normalized_package_names
        if _requires_package_shim(plugin_root, package_name)
    ]
    if not shim_targets:
        return None

    shim_root = Path(tempfile.mkdtemp(prefix="plugin-import-shim-")).resolve()
    for package_name in shim_targets:
        package_dir = shim_root / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        init_path = package_dir / "__init__.py"
        # 市场安装当前会把包目录内容直接摊平到版本目录，这里补一个轻量包壳，
        # 让 `official_weather.xxx` 这类导入还能落到真实插件目录。
        init_path.write_text(
            "from __future__ import annotations\n"
            f"__path__ = [{str(plugin_root)!r}]\n",
            encoding="utf-8",
        )
    return shim_root


def _normalize_package_names(package_names: Iterable[str] | None) -> list[str]:
    if package_names is None:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for package_name in package_names:
        value = str(package_name or "").strip()
        if not value or value in seen:
            continue
        if not _PACKAGE_NAME_PATTERN.fullmatch(value):
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _requires_package_shim(plugin_root: Path, package_name: str) -> bool:
    if plugin_root.name == package_name and (plugin_root / "__init__.py").is_file():
        return False
    return not (plugin_root / package_name).is_dir()
