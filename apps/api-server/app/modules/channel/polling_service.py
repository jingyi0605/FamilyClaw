from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.channel import repository
from app.modules.channel.account_service import get_channel_account_or_404
from app.modules.channel.gateway_service import process_channel_inbound_event
from app.modules.channel.schemas import (
    ChannelGatewayInboundEvent,
    ChannelInboundEventCreate,
    ChannelPollingBatchRead,
    ChannelPollingExecutionRead,
)
from app.modules.channel.service import record_channel_inbound_event
from app.modules.plugin.schemas import PluginExecutionRequest
from app.modules.plugin.service import (
    PluginExecutionError,
    PreparedHouseholdPluginExecution,
    execute_prepared_household_plugin,
    prepare_household_plugin_execution,
)


class ChannelPollingServiceError(ValueError):
    def __init__(self, detail: str, *, already_recorded: bool = False):
        super().__init__(detail)
        self.already_recorded = already_recorded


@dataclass(slots=True)
class PreparedChannelPollExecution:
    household_id: str
    account_id: str
    plugin_execution: PreparedHouseholdPluginExecution


def mark_channel_account_poll_failed(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    error_code: str,
    error_message: str,
) -> None:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    _mark_poll_failed(
        account=account,
        error_code=error_code,
        error_message=error_message,
    )


def poll_channel_account(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> ChannelPollingBatchRead:
    prepared = prepare_channel_account_poll_execution(
        db,
        household_id=household_id,
        account_id=account_id,
    )
    execution = execute_prepared_household_plugin(prepared.plugin_execution)
    return apply_channel_poll_execution(
        db,
        household_id=household_id,
        account_id=account_id,
        execution=execution,
    )


def prepare_channel_account_poll_execution(
    db: Session,
    *,
    household_id: str,
    account_id: str,
) -> PreparedChannelPollExecution:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    if account.status == "disabled":
        raise ChannelPollingServiceError("channel account is disabled")
    if account.connection_mode != "polling":
        raise ChannelPollingServiceError("channel account connection_mode is not polling")

    poll_state = _build_poll_state(db, channel_account_id=account.id)
    return PreparedChannelPollExecution(
        household_id=household_id,
        account_id=account_id,
        plugin_execution=prepare_household_plugin_execution(
            db,
            household_id=household_id,
            request=PluginExecutionRequest(
                plugin_id=account.plugin_id,
                plugin_type="channel",
                payload={
                    "action": "poll",
                    "account": {
                        "id": account.id,
                        "household_id": account.household_id,
                        "plugin_id": account.plugin_id,
                        "platform_code": account.platform_code,
                        "account_code": account.account_code,
                        "connection_mode": account.connection_mode,
                        "config": account.config_json,
                    },
                    "poll_state": poll_state,
                },
                trigger="channel-poll",
            ),
        ),
    )


def apply_channel_poll_execution(
    db: Session,
    *,
    household_id: str,
    account_id: str,
    execution,
) -> ChannelPollingBatchRead:
    account = get_channel_account_or_404(db, household_id=household_id, account_id=account_id)
    if account.status == "disabled":
        raise ChannelPollingServiceError("channel account is disabled")
    if account.connection_mode != "polling":
        raise ChannelPollingServiceError("channel account connection_mode is not polling")

    if not execution.success:
        _mark_poll_failed(
            account=account,
            error_code=execution.error_code or "channel_poll_failed",
            error_message=execution.error_message or "channel polling failed",
        )
        raise PluginExecutionError(execution.error_message or "channel plugin execution failed")

    if not isinstance(execution.output, dict):
        _mark_poll_failed(
            account=account,
            error_code="channel_poll_invalid_output",
            error_message="channel plugin poll output must be a JSON object",
        )
        raise ChannelPollingServiceError(
            "channel plugin poll output must be a JSON object",
            already_recorded=True,
        )

    batch = ChannelPollingExecutionRead.model_validate(execution.output)
    recorded_event_count = 0
    duplicate_event_count = 0
    processed_event_count = 0
    for event in batch.events:
        inbound_event, created = record_channel_inbound_event(
            db,
            payload=ChannelInboundEventCreate(
                household_id=account.household_id,
                channel_account_id=account.id,
                external_event_id=event.external_event_id,
                event_type=event.event_type,
                external_user_id=event.external_user_id,
                external_conversation_key=event.external_conversation_key,
                normalized_payload=event.normalized_payload,
                status=event.status,
                conversation_session_id=event.conversation_session_id,
                error_code=event.error_code,
                error_message=event.error_message,
                received_at=event.received_at,
                processed_at=event.processed_at,
            ),
        )
        if not created:
            duplicate_event_count += 1
            continue
        recorded_event_count += 1
        if event.event_type != "message":
            continue
        process_channel_inbound_event(
            db,
            account_id=account.id,
            inbound_event_id=inbound_event.id,
        )
        processed_event_count += 1

    _mark_poll_succeeded(account=account)
    return ChannelPollingBatchRead(
        account_id=account.id,
        plugin_id=account.plugin_id,
        fetched_event_count=len(batch.events),
        recorded_event_count=recorded_event_count,
        duplicate_event_count=duplicate_event_count,
        processed_event_count=processed_event_count,
        next_cursor=batch.next_cursor,
        message=batch.message,
    )



def _build_poll_state(db: Session, *, channel_account_id: str) -> dict[str, Any]:
    latest_event = repository.get_latest_channel_inbound_event_by_account(
        db,
        channel_account_id=channel_account_id,
    )
    latest_external_event_id = None if latest_event is None else latest_event.external_event_id
    return {
        "cursor": _build_next_cursor(latest_external_event_id),
        "latest_external_event_id": latest_external_event_id,
        "last_received_at": None if latest_event is None else latest_event.received_at,
    }


def _build_next_cursor(latest_external_event_id: str | None) -> str | None:
    if not latest_external_event_id:
        return None
    try:
        return str(int(latest_external_event_id) + 1)
    except (TypeError, ValueError):
        return latest_external_event_id


def _mark_poll_succeeded(*, account) -> None:
    account.last_error_code = None
    account.last_error_message = None
    if account.status == "degraded":
        account.status = "active"
    account.updated_at = utc_now_iso()


def _mark_poll_failed(*, account, error_code: str, error_message: str) -> None:
    account.last_error_code = error_code
    account.last_error_message = error_message
    if account.status != "disabled":
        account.status = "degraded"
    account.updated_at = utc_now_iso()
