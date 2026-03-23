from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.channel.account_service import _to_channel_account_read, get_channel_account_or_404
from app.modules.channel.schemas import (
    ChannelAccountPluginActionExecuteRead,
    ChannelAccountPluginActionRead,
    ChannelAccountPluginArtifactRead,
    ChannelAccountPluginStatusSummaryRead,
)
from app.modules.plugin.schemas import (
    PluginExecutionRequest,
    PluginManifestChannelAccountActionSpec,
    PluginRegistryItem,
)
from app.modules.plugin.service import execute_household_plugin, get_household_plugin, require_available_household_plugin


class ChannelAccountPluginActionServiceError(ValueError):
    def __init__(self, detail: str, *, error_code: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code

    def to_detail(self) -> dict[str, Any]:
        return {
            "detail": self.detail,
            "error_code": self.error_code,
        }


def list_channel_account_plugin_actions(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> list[ChannelAccountPluginActionRead]:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=account.plugin_id)
    return _build_action_reads(plugin, account_status=account.status)


def get_channel_account_plugin_status_summary(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> ChannelAccountPluginStatusSummaryRead | None:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    plugin = get_household_plugin(db, household_id=household_id, plugin_id=account.plugin_id)
    return _resolve_plugin_status_summary(db, household_id=household_id, account=account, plugin=plugin)


def execute_channel_account_plugin_action(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    action_key: str,
    payload: dict[str, Any] | None = None,
) -> ChannelAccountPluginActionExecuteRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    if account.status == "disabled":
        raise ChannelAccountPluginActionServiceError(
            "当前账号已停用，不能执行插件动作。",
            error_code="channel_account_disabled",
            status_code=409,
        )

    plugin = require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=account.plugin_id,
        plugin_type="action",
        trigger="channel-account-action",
    )
    action_spec = _get_action_spec(plugin, action_key)
    if action_spec is None:
        raise ChannelAccountPluginActionServiceError(
            f"当前账号所属插件没有声明动作 {action_key}。",
            error_code="channel_account_action_not_declared",
            status_code=404,
        )

    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=account.plugin_id,
            plugin_type="action",
            payload=_build_action_payload(account, action_spec=action_spec, payload=payload),
            trigger="channel-account-action",
        ),
    )
    if not execution.success:
        raise ChannelAccountPluginActionServiceError(
            execution.error_message or "账号级插件动作执行失败。",
            error_code=execution.error_code or "channel_account_action_execute_failed",
            status_code=400,
        )

    output = execution.output if isinstance(execution.output, dict) else {}
    return ChannelAccountPluginActionExecuteRead(
        action=_build_action_read(action_spec),
        message=_optional_text(output.get("message")),
        status_summary=_extract_status_summary(output),
        artifacts=_extract_artifacts(output),
        output=output,
    )


def _resolve_plugin_status_summary(
    db: Session,
    *,
    household_id: str,
    account: Any,
    plugin: PluginRegistryItem,
) -> ChannelAccountPluginStatusSummaryRead | None:
    if not plugin.enabled:
        return ChannelAccountPluginStatusSummaryRead(
            status="plugin_disabled",
            title="插件已停用",
            message=plugin.disabled_reason or "当前家庭已停用该通道插件。",
            tone="warning",
        )
    if account.status == "disabled":
        return ChannelAccountPluginStatusSummaryRead(
            status="disabled",
            title="账号已停用",
            message=account.last_error_message or "当前账号已停用，不会再执行插件动作。",
            tone="warning",
            last_error_code=account.last_error_code,
            last_error_message=account.last_error_message,
            updated_at=account.updated_at,
        )

    status_action = _get_status_action_spec(plugin)
    if status_action is None or "action" not in plugin.types or plugin.entrypoints.action is None:
        return _build_fallback_status_summary(account)

    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=account.plugin_id,
            plugin_type="action",
            payload=_build_action_payload(account, action_spec=status_action, payload=None),
            trigger="channel-account-status",
        ),
    )
    if execution.success:
        output = execution.output if isinstance(execution.output, dict) else {}
        return _extract_status_summary(output) or _build_fallback_status_summary(account)
    return ChannelAccountPluginStatusSummaryRead(
        status="error",
        title="状态读取失败",
        message=execution.error_message or "账号级插件状态摘要读取失败。",
        tone="danger",
        last_error_code=execution.error_code,
        last_error_message=execution.error_message,
    )


def _build_action_reads(
    plugin: PluginRegistryItem,
    *,
    account_status: str,
) -> list[ChannelAccountPluginActionRead]:
    if plugin.capabilities.channel is None:
        return []

    disabled = False
    disabled_reason: str | None = None
    if not plugin.enabled:
        disabled = True
        disabled_reason = plugin.disabled_reason or "当前家庭已停用该通道插件。"
    elif account_status == "disabled":
        disabled = True
        disabled_reason = "当前账号已停用，不能执行插件动作。"
    elif "action" not in plugin.types or plugin.entrypoints.action is None:
        disabled = True
        disabled_reason = "当前插件没有声明可执行的账号级动作入口。"

    return [
        _build_action_read(item, disabled=disabled, disabled_reason=disabled_reason)
        for item in plugin.capabilities.channel.ui.account_actions
    ]


def _build_action_read(
    action_spec: PluginManifestChannelAccountActionSpec,
    *,
    disabled: bool = False,
    disabled_reason: str | None = None,
) -> ChannelAccountPluginActionRead:
    return ChannelAccountPluginActionRead(
        key=action_spec.key,
        action_name=action_spec.action_name,
        label=action_spec.label,
        description=action_spec.description,
        variant=action_spec.variant,
        requires_confirmation=action_spec.requires_confirmation,
        confirmation_text=action_spec.confirmation_text,
        disabled=disabled,
        disabled_reason=disabled_reason,
    )


def _get_status_action_spec(plugin: PluginRegistryItem) -> PluginManifestChannelAccountActionSpec | None:
    channel_spec = plugin.capabilities.channel
    if channel_spec is None or channel_spec.ui.status_action_key is None:
        return None
    return _get_action_spec(plugin, channel_spec.ui.status_action_key)


def _get_action_spec(
    plugin: PluginRegistryItem,
    action_key: str,
) -> PluginManifestChannelAccountActionSpec | None:
    channel_spec = plugin.capabilities.channel
    if channel_spec is None:
        return None
    for item in channel_spec.ui.account_actions:
        if item.key == action_key:
            return item
    return None


def _build_action_payload(
    account: Any,
    *,
    action_spec: PluginManifestChannelAccountActionSpec,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    merged_payload = dict(payload or {})
    for reserved_key in ("action_name", "channel_account_id", "account"):
        if reserved_key in merged_payload:
            raise ChannelAccountPluginActionServiceError(
                f"账号级插件动作请求不能覆盖保留字段 {reserved_key}。",
                error_code="channel_account_action_payload_reserved_key",
                status_code=400,
            )
    account_payload = _to_channel_account_read(account).model_dump(mode="json")
    account_payload["enabled"] = account.status != "disabled"
    merged_payload["action_name"] = action_spec.action_name
    merged_payload["channel_account_id"] = account.id
    merged_payload["account"] = account_payload
    return merged_payload


def _build_fallback_status_summary(account: Any) -> ChannelAccountPluginStatusSummaryRead | None:
    if account.last_error_code or account.last_error_message or account.last_probe_status == "failed":
        return ChannelAccountPluginStatusSummaryRead(
            status=account.status,
            title="最近执行异常",
            message=account.last_error_message or "最近一次插件执行失败。",
            tone="danger",
            last_error_code=account.last_error_code,
            last_error_message=account.last_error_message,
            updated_at=account.updated_at,
        )
    return None


def _extract_status_summary(output: dict[str, Any]) -> ChannelAccountPluginStatusSummaryRead | None:
    raw = output.get("status_summary")
    if isinstance(raw, dict):
        details = raw.get("details")
        status = _optional_text(raw.get("status")) or "unknown"
        return ChannelAccountPluginStatusSummaryRead(
            status=status,
            title=_optional_text(raw.get("title")),
            message=_optional_text(raw.get("message")) or _optional_text(output.get("message")),
            tone=_normalize_tone(raw.get("tone"), status=status, last_error_code=_optional_text(raw.get("last_error_code"))),
            last_error_code=_optional_text(raw.get("last_error_code")),
            last_error_message=_optional_text(raw.get("last_error_message")),
            updated_at=_optional_text(raw.get("updated_at")),
            details=details if isinstance(details, dict) else {},
        )

    status = _optional_text(output.get("status")) or _optional_text(output.get("login_status"))
    message = _optional_text(output.get("message"))
    if status is None and message is None:
        return None
    last_error_code = _optional_text(output.get("last_error_code"))
    last_error_message = _optional_text(output.get("last_error_message"))
    return ChannelAccountPluginStatusSummaryRead(
        status=status or "unknown",
        message=message,
        tone=_normalize_tone(None, status=status or "unknown", last_error_code=last_error_code),
        last_error_code=last_error_code,
        last_error_message=last_error_message,
        updated_at=_optional_text(output.get("updated_at")),
    )


def _extract_artifacts(output: dict[str, Any]) -> list[ChannelAccountPluginArtifactRead]:
    raw = output.get("artifacts")
    if not isinstance(raw, list):
        return []

    artifacts: list[ChannelAccountPluginArtifactRead] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = _optional_text(item.get("kind"))
        if kind not in {"image_url", "external_url", "text"}:
            continue
        artifacts.append(
            ChannelAccountPluginArtifactRead(
                kind=kind,
                label=_optional_text(item.get("label")),
                url=_optional_text(item.get("url")),
                text=_optional_text(item.get("text")),
            )
        )
    return artifacts


def _normalize_tone(
    value: Any,
    *,
    status: str,
    last_error_code: str | None,
) -> str:
    if isinstance(value, str) and value in {"neutral", "info", "success", "warning", "danger"}:
        return value
    if last_error_code:
        return "danger"
    if status in {"active", "ok", "ready"}:
        return "success"
    if status in {"waiting_scan", "scan_confirmed"}:
        return "info"
    if status in {"expired", "disabled", "plugin_disabled"}:
        return "warning"
    if status in {"error", "failed", "degraded"}:
        return "danger"
    return "neutral"


def _optional_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
