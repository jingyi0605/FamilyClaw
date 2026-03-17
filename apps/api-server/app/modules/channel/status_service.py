from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.channel import repository
from app.modules.channel.account_service import get_channel_account_or_404
from app.modules.channel.schemas import (
    ChannelAccountRead,
    ChannelAccountStatusRead,
    ChannelDeliveryFailureSummaryRead,
    ChannelDeliveryRead,
    ChannelInboundEventRead,
)
from app.modules.channel.service import (
    _to_channel_delivery_read,
    _to_channel_inbound_event_read,
)
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import execute_household_plugin, get_household_plugin, require_available_household_plugin


class ChannelStatusServiceError(ValueError):
    pass


def summarize_recent_delivery_failures(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str,
) -> ChannelDeliveryFailureSummaryRead:
    deliveries = repository.list_channel_deliveries_by_account(
        db,
        household_id=household_id,
        channel_account_id=channel_account_id,
    )
    failed = [item for item in deliveries if item.status == "failed"]
    latest = failed[0] if failed else None
    platform_code = deliveries[0].platform_code if deliveries else ""
    return ChannelDeliveryFailureSummaryRead(
        channel_account_id=channel_account_id,
        platform_code=platform_code,
        recent_failure_count=len(failed),
        last_delivery_id=None if latest is None else latest.id,
        last_error_code=None if latest is None else latest.last_error_code,
        last_error_message=None if latest is None else latest.last_error_message,
        last_failed_at=None if latest is None else latest.updated_at,
    )


def get_channel_account_status(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> ChannelAccountStatusRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    try:
        plugin = get_household_plugin(db, household_id=household_id, plugin_id=account.plugin_id)
    except ValueError as exc:
        raise ChannelStatusServiceError(str(exc)) from exc
    deliveries = repository.list_channel_deliveries_by_account(
        db,
        household_id=household_id,
        channel_account_id=account_id,
    )
    inbound_events = [
        item
        for item in repository.list_channel_inbound_events(db, household_id=household_id)
        if item.channel_account_id == account_id
    ]
    failed_inbound = next((item for item in inbound_events if item.status == "failed"), None)

    account_read = _to_channel_account_read(account)
    if not plugin.enabled:
        account_read.status = "degraded"
        account_read.last_error_code = "plugin_disabled"
        account_read.last_error_message = plugin.disabled_reason or "当前家庭已停用该通道插件"

    return ChannelAccountStatusRead(
        account=account_read,
        recent_failure_summary=summarize_recent_delivery_failures(
            db,
            household_id=household_id,
            channel_account_id=account_id,
        ),
        latest_delivery=None if not deliveries else _to_channel_delivery_read(deliveries[0]),
        latest_inbound_event=None if not inbound_events else _to_channel_inbound_event_read(inbound_events[0]),
        latest_failed_inbound_event=None if failed_inbound is None else _to_channel_inbound_event_read(failed_inbound),
        recent_delivery_count=len(deliveries),
        recent_inbound_count=len(inbound_events),
    )


def probe_channel_account(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> ChannelAccountStatusRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    require_available_household_plugin(
        db,
        household_id=household_id,
        plugin_id=account.plugin_id,
        plugin_type="channel",
        trigger="channel-probe",
    )
    execution = execute_household_plugin(
        db,
        household_id=household_id,
        request=PluginExecutionRequest(
            plugin_id=account.plugin_id,
            plugin_type="channel",
            payload={
                "action": "probe",
                "account": {
                    "id": account.id,
                    "household_id": account.household_id,
                    "plugin_id": account.plugin_id,
                    "platform_code": account.platform_code,
                    "account_code": account.account_code,
                    "connection_mode": account.connection_mode,
                    "config": account.config_json,
                },
            },
            trigger="channel-probe",
        ),
    )

    output = execution.output if isinstance(execution.output, dict) else {}
    if execution.success:
        probe_status = str(output.get("probe_status") or "ok").strip() or "ok"
        message = _optional_text(output.get("message"))
        account.last_probe_status = probe_status
        account.last_error_code = None
        account.last_error_message = message
        if account.status != "disabled":
            account.status = "active"
    else:
        account.last_probe_status = "failed"
        account.last_error_code = execution.error_code or "channel_probe_failed"
        account.last_error_message = execution.error_message
        if account.status != "disabled":
            account.status = "degraded"
    return get_channel_account_status(db, household_id=household_id, account_id=account_id)


def list_channel_delivery_status_records(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str | None = None,
    platform_code: str | None = None,
    status: str | None = None,
) -> list[ChannelDeliveryRead]:
    items = repository.list_channel_deliveries(db, household_id=household_id)
    filtered: list[ChannelDeliveryRead] = []
    for item in items:
        if channel_account_id is not None and item.channel_account_id != channel_account_id:
            continue
        if platform_code is not None and item.platform_code != platform_code:
            continue
        if status is not None and item.status != status:
            continue
        filtered.append(_to_channel_delivery_read(item))
    return filtered


def list_channel_inbound_event_status_records(
    db: Session,
    *,
    household_id: str,
    channel_account_id: str | None = None,
    platform_code: str | None = None,
    status: str | None = None,
) -> list[ChannelInboundEventRead]:
    items = repository.list_channel_inbound_events(db, household_id=household_id)
    filtered: list[ChannelInboundEventRead] = []
    for item in items:
        if channel_account_id is not None and item.channel_account_id != channel_account_id:
            continue
        if platform_code is not None and item.platform_code != platform_code:
            continue
        if status is not None and item.status != status:
            continue
        filtered.append(_to_channel_inbound_event_read(item))
    return filtered


def _to_channel_account_read(row) -> ChannelAccountRead:
    from app.modules.channel.account_service import _to_channel_account_read as convert

    return convert(row)


def _optional_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
