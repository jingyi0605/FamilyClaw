from __future__ import annotations

from dataclasses import dataclass
import re

from app.modules.plugin.schemas import (
    PluginVersionCompatibilityStatus,
    PluginVersionGovernanceRead,
    PluginVersionGovernanceSourceType,
    PluginVersionUpdateState,
)


_VERSION_PATTERN = re.compile(
    r"^v?(?P<release>\d+(?:\.\d+)*)"
    r"(?:(?:[-_.]?)(?P<pre_label>alpha|a|beta|b|rc|pre|preview)(?P<pre_number>\d*)?)?"
    r"(?:\+.*)?$",
    re.IGNORECASE,
)
_PRE_RELEASE_ORDER = {
    "alpha": 0,
    "a": 0,
    "beta": 1,
    "b": 1,
    "pre": 2,
    "preview": 2,
    "rc": 2,
}


@dataclass(frozen=True, slots=True)
class MarketplaceVersionFact:
    version: str
    min_app_version: str | None = None


@dataclass(frozen=True, slots=True)
class HostCompatibilityResult:
    status: PluginVersionCompatibilityStatus
    blocked_reason: str | None


@dataclass(frozen=True, slots=True, order=True)
class _ParsedVersion:
    release: tuple[int, ...]
    pre_rank: int
    pre_number: int
    is_final: bool


def _normalize_version_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_version(value: str) -> _ParsedVersion:
    normalized = value.strip()
    match = _VERSION_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValueError(f"当前版本比较规则不支持 {value!r}")
    release = tuple(int(part) for part in match.group("release").split("."))
    pre_label = match.group("pre_label")
    if pre_label is None:
        return _ParsedVersion(release=release, pre_rank=99, pre_number=0, is_final=True)
    return _ParsedVersion(
        release=release,
        pre_rank=_PRE_RELEASE_ORDER[pre_label.lower()],
        pre_number=int(match.group("pre_number") or "0"),
        is_final=False,
    )


def compare_plugin_versions(left: str, right: str) -> int:
    parsed_left = _parse_version(left)
    parsed_right = _parse_version(right)
    if parsed_left < parsed_right:
        return -1
    if parsed_left > parsed_right:
        return 1
    return 0


def resolve_host_compatibility(
    *,
    host_version: str | None,
    min_app_version: str | None,
    target_version: str | None = None,
) -> HostCompatibilityResult:
    normalized_host_version = _normalize_version_text(host_version)
    normalized_min_app_version = _normalize_version_text(min_app_version)
    normalized_target_version = _normalize_version_text(target_version)
    if normalized_min_app_version is None:
        detail = "市场条目没有提供 min_app_version，当前不能安全判断宿主兼容性。"
        if normalized_target_version is not None:
            detail = f"版本 {normalized_target_version} 没有提供 min_app_version，当前不能安全判断宿主兼容性。"
        return HostCompatibilityResult(status="unknown", blocked_reason=detail)
    if normalized_host_version is None:
        return HostCompatibilityResult(
            status="unknown",
            blocked_reason="当前宿主版本缺失，不能安全判断插件兼容性。",
        )
    try:
        if compare_plugin_versions(normalized_host_version, normalized_min_app_version) >= 0:
            return HostCompatibilityResult(status="compatible", blocked_reason=None)
    except ValueError as exc:
        return HostCompatibilityResult(
            status="unknown",
            blocked_reason=str(exc),
        )
    detail = f"当前宿主版本 {normalized_host_version} 低于最低要求 {normalized_min_app_version}。"
    if normalized_target_version is not None:
        detail = (
            f"版本 {normalized_target_version} 要求宿主版本至少为 {normalized_min_app_version}，"
            f"当前只有 {normalized_host_version}。"
        )
    return HostCompatibilityResult(status="host_too_old", blocked_reason=detail)


def resolve_non_market_version_governance(
    *,
    source_type: PluginVersionGovernanceSourceType,
    declared_version: str | None,
    installed_version: str | None,
) -> PluginVersionGovernanceRead:
    if source_type == "manual":
        source_type = "local"
    normalized_declared_version = _normalize_version_text(declared_version)
    normalized_installed_version = _normalize_version_text(installed_version) or normalized_declared_version
    blocked_reason = None
    update_state: PluginVersionUpdateState = "not_market_managed"
    if normalized_declared_version and normalized_installed_version and normalized_declared_version != normalized_installed_version:
        update_state = "unknown"
        blocked_reason = "当前落盘 manifest.version 和已安装版本记录不一致。"
    return PluginVersionGovernanceRead(
        source_type=source_type,
        installed_version=normalized_installed_version,
        declared_version=normalized_declared_version,
        latest_version=None,
        latest_compatible_version=None,
        compatibility_status="unknown",
        update_state=update_state,
        blocked_reason=blocked_reason,
    )


def _pick_highest_version(versions: list[str]) -> tuple[str | None, str | None]:
    if not versions:
        return None, None
    highest = versions[0]
    try:
        for version in versions[1:]:
            if compare_plugin_versions(version, highest) > 0:
                highest = version
    except ValueError as exc:
        return None, str(exc)
    return highest, None


def resolve_marketplace_version_governance(
    *,
    host_version: str | None,
    declared_version: str | None,
    installed_version: str | None,
    latest_version: str | None,
    versions: list[MarketplaceVersionFact],
) -> PluginVersionGovernanceRead:
    normalized_declared_version = _normalize_version_text(declared_version)
    normalized_installed_version = _normalize_version_text(installed_version)
    normalized_latest_version = _normalize_version_text(latest_version)
    if normalized_installed_version and normalized_declared_version and normalized_installed_version != normalized_declared_version:
        return PluginVersionGovernanceRead(
            source_type="marketplace",
            installed_version=normalized_installed_version,
            declared_version=normalized_declared_version,
            latest_version=normalized_latest_version,
            latest_compatible_version=None,
            compatibility_status="unknown",
            update_state="unknown",
            blocked_reason="实例记录的已安装版本和当前落盘 manifest.version 不一致。",
        )

    version_map = {item.version: item for item in versions if _normalize_version_text(item.version) is not None}
    latest_version_fact = version_map.get(normalized_latest_version or "")
    if normalized_latest_version is None or latest_version_fact is None:
        return PluginVersionGovernanceRead(
            source_type="marketplace",
            installed_version=normalized_installed_version,
            declared_version=normalized_declared_version,
            latest_version=normalized_latest_version,
            latest_compatible_version=None,
            compatibility_status="unknown",
            update_state="unknown",
            blocked_reason="市场条目的 latest_version 和 versions 列表不一致。",
        )

    latest_version_compatibility = resolve_host_compatibility(
        host_version=host_version,
        min_app_version=latest_version_fact.min_app_version,
        target_version=latest_version_fact.version,
    )
    compatible_versions: list[str] = []
    unknown_compatibility_detected = False
    for item in versions:
        compatibility = resolve_host_compatibility(
            host_version=host_version,
            min_app_version=item.min_app_version,
            target_version=item.version,
        )
        if compatibility.status == "compatible":
            compatible_versions.append(item.version)
        elif compatibility.status == "unknown":
            unknown_compatibility_detected = True

    latest_compatible_version, compare_error = _pick_highest_version(compatible_versions)
    if compare_error is not None:
        return PluginVersionGovernanceRead(
            source_type="marketplace",
            installed_version=normalized_installed_version,
            declared_version=normalized_declared_version,
            latest_version=normalized_latest_version,
            latest_compatible_version=None,
            compatibility_status="unknown",
            update_state="unknown",
            blocked_reason=compare_error,
        )

    if normalized_installed_version is None:
        update_state: PluginVersionUpdateState = "unknown"
    elif normalized_installed_version not in version_map:
        update_state = "installed_newer_than_market"
    elif latest_compatible_version is None:
        update_state = "upgrade_blocked" if latest_version_compatibility.status == "host_too_old" else "unknown"
    elif normalized_installed_version == latest_compatible_version:
        if normalized_latest_version != latest_compatible_version and latest_version_compatibility.status == "host_too_old":
            update_state = "upgrade_blocked"
        else:
            update_state = "up_to_date"
    else:
        try:
            compare_result = compare_plugin_versions(normalized_installed_version, latest_compatible_version)
        except ValueError as exc:
            return PluginVersionGovernanceRead(
                source_type="marketplace",
                installed_version=normalized_installed_version,
                declared_version=normalized_declared_version,
                latest_version=normalized_latest_version,
                latest_compatible_version=latest_compatible_version,
                compatibility_status="unknown",
                update_state="unknown",
                blocked_reason=str(exc),
            )
        if compare_result < 0:
            update_state = "upgrade_available"
        elif compare_result > 0:
            update_state = "installed_newer_than_market"
        elif normalized_latest_version != latest_compatible_version and latest_version_compatibility.status == "host_too_old":
            update_state = "upgrade_blocked"
        else:
            update_state = "up_to_date"

    blocked_reason = latest_version_compatibility.blocked_reason
    if update_state == "upgrade_available":
        blocked_reason = None
    elif update_state == "up_to_date" and latest_version_compatibility.status == "compatible":
        blocked_reason = None
    elif update_state == "installed_newer_than_market":
        blocked_reason = "当前已安装版本不在市场目录里，不能直接按市场版本判断升级关系。"
    elif update_state == "unknown" and blocked_reason is None and unknown_compatibility_detected:
        blocked_reason = "市场版本缺少完整兼容性信息，当前只能给出未知状态。"

    return PluginVersionGovernanceRead(
        source_type="marketplace",
        installed_version=normalized_installed_version,
        declared_version=normalized_declared_version,
        latest_version=normalized_latest_version,
        latest_compatible_version=latest_compatible_version,
        compatibility_status=latest_version_compatibility.status,
        update_state=update_state,
        blocked_reason=blocked_reason,
    )
