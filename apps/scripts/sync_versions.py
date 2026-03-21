#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1].parent
VERSION_FILE = PROJECT_ROOT / "VERSION"


def read_root_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError(f"{VERSION_FILE} 为空，不能同步版本。")
    return version


def _replace_once(content: str, pattern: str, replacement: str, *, file_path: Path) -> str:
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"{file_path} 没找到唯一可替换的版本字段。")
    return updated


def sync_text_line(file_path: Path, pattern: str, replacement: str) -> bool:
    original = file_path.read_text(encoding="utf-8")
    updated = _replace_once(original, pattern, replacement, file_path=file_path)
    if updated == original:
        return False
    file_path.write_text(updated, encoding="utf-8")
    return True


def sync_package_json(file_path: Path, version: str) -> bool:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if payload.get("version") == version:
        return False
    payload["version"] = version
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def sync_root_package_lock(file_path: Path, version: str) -> bool:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    packages = payload.get("packages", {})
    changed = False

    for package_key in (
        "apps/user-app",
        "packages/user-core",
        "packages/user-platform",
        "packages/user-ui",
    ):
        package_entry = packages.get(package_key)
        if not isinstance(package_entry, dict):
            continue
        if package_entry.get("version") == version:
            continue
        package_entry["version"] = version
        changed = True

    if not changed:
        return False
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def sync_user_app_package_lock(file_path: Path, version: str) -> bool:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    changed = False

    if payload.get("version") != version:
        payload["version"] = version
        changed = True

    packages = payload.get("packages", {})
    for package_key in (
        "",
        "../../packages/user-core",
        "../../packages/user-platform",
        "../../packages/user-ui",
    ):
        package_entry = packages.get(package_key)
        if not isinstance(package_entry, dict):
            continue
        if package_entry.get("version") == version:
            continue
        package_entry["version"] = version
        changed = True

    if not changed:
        return False
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


@dataclass(frozen=True)
class SyncTarget:
    label: str
    path: Path
    updater: Callable[[Path, str], bool]


def build_sync_targets() -> list[SyncTarget]:
    return [
        SyncTarget(
            label="Docker 构建默认版本",
            path=PROJECT_ROOT / "Dockerfile",
            updater=lambda path, version: sync_text_line(path, r"^ARG APP_VERSION=.*$", f"ARG APP_VERSION={version}"),
        ),
        SyncTarget(
            label="api-server Python 包版本",
            path=PROJECT_ROOT / "apps/api-server/pyproject.toml",
            updater=lambda path, version: sync_text_line(path, r'^version = ".*"$', f'version = "{version}"'),
        ),
        SyncTarget(
            label="open-xiaoai-gateway Python 包版本",
            path=PROJECT_ROOT / "apps/open-xiaoai-gateway/pyproject.toml",
            updater=lambda path, version: sync_text_line(path, r'^version = ".*"$', f'version = "{version}"'),
        ),
        SyncTarget(
            label="user-app npm 包版本",
            path=PROJECT_ROOT / "apps/user-app/package.json",
            updater=sync_package_json,
        ),
        SyncTarget(
            label="user-app lockfile 本地版本",
            path=PROJECT_ROOT / "apps/user-app/package-lock.json",
            updater=sync_user_app_package_lock,
        ),
        SyncTarget(
            label="workspace lockfile 本地版本",
            path=PROJECT_ROOT / "package-lock.json",
            updater=sync_root_package_lock,
        ),
        SyncTarget(
            label="user-core npm 包版本",
            path=PROJECT_ROOT / "packages/user-core/package.json",
            updater=sync_package_json,
        ),
        SyncTarget(
            label="user-platform npm 包版本",
            path=PROJECT_ROOT / "packages/user-platform/package.json",
            updater=sync_package_json,
        ),
        SyncTarget(
            label="user-ui npm 包版本",
            path=PROJECT_ROOT / "packages/user-ui/package.json",
            updater=sync_package_json,
        ),
    ]


def check_targets(version: str, targets: list[SyncTarget]) -> int:
    drifted: list[str] = []
    for target in targets:
        before = target.path.read_text(encoding="utf-8")
        after = before
        try:
            changed = target.updater(target.path, version)
        finally:
            current = target.path.read_text(encoding="utf-8")
            if current != before:
                target.path.write_text(before, encoding="utf-8")
        if changed:
            drifted.append(f"{target.label}: {target.path}")
        else:
            after = before
        _ = after

    if not drifted:
        print(f"版本已同步：{version}")
        return 0

    print("以下文件版本未同步，请先执行写入模式：", file=sys.stderr)
    for item in drifted:
        print(f"- {item}", file=sys.stderr)
    return 1


def write_targets(version: str, targets: list[SyncTarget]) -> int:
    changed_items: list[str] = []
    unchanged_items: list[str] = []

    for target in targets:
        changed = target.updater(target.path, version)
        line = f"{target.label}: {target.path}"
        if changed:
            changed_items.append(line)
        else:
            unchanged_items.append(line)

    print(f"已按 VERSION={version} 同步版本。")
    if changed_items:
        print("已更新：")
        for item in changed_items:
            print(f"- {item}")
    if unchanged_items:
        print("本来就一致：")
        for item in unchanged_items:
            print(f"- {item}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从仓库根目录 VERSION 同步各子项目版本。")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查是否漂移，不写回文件。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = read_root_version()
    targets = build_sync_targets()
    if args.check:
        return check_targets(version, targets)
    return write_targets(version, targets)


if __name__ == "__main__":
    raise SystemExit(main())
