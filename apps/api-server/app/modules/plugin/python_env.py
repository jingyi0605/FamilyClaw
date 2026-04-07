from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from subprocess import run as subprocess_run
import sys
import sysconfig


PLUGIN_ENV_DIRNAME = ".familyclaw-venv"
PLUGIN_REQUIREMENTS_SNAPSHOT_NAME = ".familyclaw-requirements.txt"
PLUGIN_REQUIREMENTS_HASH_NAME = ".requirements.sha256"
DEFAULT_ENV_PREPARE_TIMEOUT_SECONDS = 300


@dataclass(slots=True)
class PluginPythonEnvPrepareResult:
    plugin_root: str
    venv_dir: str
    python_path: str
    requirements_path: str
    requirements_hash: str
    created: bool
    installed: bool


@dataclass(slots=True)
class PluginPythonEnvError(RuntimeError):
    error_code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


def prepare_plugin_python_env(
    *,
    plugin_root: str | Path,
    requirements_path: str | Path | None = None,
    timeout_seconds: int = DEFAULT_ENV_PREPARE_TIMEOUT_SECONDS,
    recreate: bool = False,
) -> PluginPythonEnvPrepareResult:
    resolved_plugin_root = Path(plugin_root).resolve()
    if not resolved_plugin_root.is_dir():
        raise PluginPythonEnvError(
            error_code="plugin_env_prepare_failed",
            detail=f"插件目录不存在，无法准备运行环境：{resolved_plugin_root}",
        )

    snapshot_requirements_path = _materialize_requirements_snapshot(
        plugin_root=resolved_plugin_root,
        requirements_path=requirements_path,
    )
    requirements_hash = _sha256(snapshot_requirements_path.read_bytes())
    venv_dir = resolved_plugin_root / PLUGIN_ENV_DIRNAME
    python_path = _resolve_venv_python_path(venv_dir)
    marker_path = venv_dir / PLUGIN_REQUIREMENTS_HASH_NAME

    if not recreate and _is_prepared_env_valid(
        python_path=python_path,
        marker_path=marker_path,
        requirements_hash=requirements_hash,
    ):
        return PluginPythonEnvPrepareResult(
            plugin_root=str(resolved_plugin_root),
            venv_dir=str(venv_dir),
            python_path=str(python_path),
            requirements_path=str(snapshot_requirements_path),
            requirements_hash=requirements_hash,
            created=False,
            installed=False,
        )

    if venv_dir.exists():
        shutil.rmtree(venv_dir, ignore_errors=True)

    target_site_packages = _create_venv(venv_dir=venv_dir, timeout_seconds=timeout_seconds)
    _link_host_site_packages(target_site_packages)
    _install_requirements(
        target_site_packages=target_site_packages,
        requirements_path=snapshot_requirements_path,
        timeout_seconds=timeout_seconds,
    )
    marker_path.write_text(requirements_hash, encoding="utf-8")
    return PluginPythonEnvPrepareResult(
        plugin_root=str(resolved_plugin_root),
        venv_dir=str(venv_dir),
        python_path=str(python_path),
        requirements_path=str(snapshot_requirements_path),
        requirements_hash=requirements_hash,
        created=True,
        installed=True,
    )


def plugin_python_path_is_host_path(python_path: str | Path) -> bool:
    try:
        return Path(python_path).resolve() == Path(sys.executable).resolve()
    except OSError:
        return False


def plugin_python_env_needs_repair(
    *,
    plugin_root: str | Path,
    python_path: str | Path | None,
) -> bool:
    resolved_plugin_root = Path(plugin_root).resolve()
    if python_path is None:
        return True
    resolved_python_path = Path(python_path).resolve()
    if plugin_python_path_is_host_path(resolved_python_path):
        return True
    expected_venv_dir = resolved_plugin_root / PLUGIN_ENV_DIRNAME
    if not resolved_python_path.is_file():
        return True
    try:
        resolved_python_path.relative_to(expected_venv_dir)
    except ValueError:
        return True
    snapshot_requirements_path = _find_requirements_snapshot(resolved_plugin_root)
    if snapshot_requirements_path is None:
        return True
    marker_path = expected_venv_dir / PLUGIN_REQUIREMENTS_HASH_NAME
    return not _is_prepared_env_valid(
        python_path=resolved_python_path,
        marker_path=marker_path,
        requirements_hash=_sha256(snapshot_requirements_path.read_bytes()),
    )


def _materialize_requirements_snapshot(
    *,
    plugin_root: Path,
    requirements_path: str | Path | None,
) -> Path:
    source_requirements_path = _resolve_source_requirements_path(
        plugin_root=plugin_root,
        requirements_path=requirements_path,
    )
    snapshot_path = plugin_root / PLUGIN_REQUIREMENTS_SNAPSHOT_NAME
    if source_requirements_path is None or not source_requirements_path.is_file():
        snapshot_path.write_text("", encoding="utf-8")
        return snapshot_path
    snapshot_path.write_bytes(source_requirements_path.read_bytes())
    return snapshot_path


def _resolve_source_requirements_path(
    *,
    plugin_root: Path,
    requirements_path: str | Path | None,
) -> Path | None:
    if requirements_path is not None:
        candidate = Path(requirements_path).resolve()
        if candidate.is_file():
            return candidate
    snapshot_path = plugin_root / PLUGIN_REQUIREMENTS_SNAPSHOT_NAME
    if snapshot_path.is_file():
        return snapshot_path
    default_path = plugin_root / "requirements.txt"
    if default_path.is_file():
        return default_path
    return None


def _find_requirements_snapshot(plugin_root: Path) -> Path | None:
    snapshot_path = plugin_root / PLUGIN_REQUIREMENTS_SNAPSHOT_NAME
    if snapshot_path.is_file():
        return snapshot_path
    default_path = plugin_root / "requirements.txt"
    if default_path.is_file():
        return default_path
    return None


def _resolve_venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _is_prepared_env_valid(*, python_path: Path, marker_path: Path, requirements_hash: str) -> bool:
    if not python_path.is_file() or not marker_path.is_file():
        return False
    try:
        stored_hash = marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return stored_hash == requirements_hash


def _create_venv(*, venv_dir: Path, timeout_seconds: int) -> Path:
    completed = subprocess_run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode == 0:
        return _resolve_venv_site_packages_path(venv_dir)
    detail = (completed.stderr or completed.stdout or "unknown error").strip()
    raise PluginPythonEnvError(
        error_code="plugin_env_prepare_failed",
        detail=f"创建插件 Python venv 失败：{detail}",
    )


def _install_requirements(*, target_site_packages: Path, requirements_path: Path, timeout_seconds: int) -> None:
    if not _requirements_has_installable_lines(requirements_path):
        return
    completed = subprocess_run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(target_site_packages),
            "-r",
            str(requirements_path),
        ],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode == 0:
        return
    detail = (completed.stderr or completed.stdout or "unknown error").strip()
    raise PluginPythonEnvError(
        error_code="plugin_env_prepare_failed",
        detail=f"安装插件 Python 依赖失败：{detail}",
    )


def _requirements_has_installable_lines(requirements_path: Path) -> bool:
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        return True
    return False


def _link_host_site_packages(target_site_packages: Path) -> None:
    host_site_packages = Path(sysconfig.get_paths()["purelib"]).resolve()
    target_site_packages.mkdir(parents=True, exist_ok=True)
    (target_site_packages / "familyclaw_host_env.pth").write_text(
        f"{host_site_packages}\n",
        encoding="utf-8",
    )


def _resolve_venv_site_packages_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Lib" / "site-packages"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return venv_dir / "lib" / version / "site-packages"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
