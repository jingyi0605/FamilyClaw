from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.channel import repository
from app.modules.channel.schemas import ChannelDeliveryFailureSummaryRead


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
