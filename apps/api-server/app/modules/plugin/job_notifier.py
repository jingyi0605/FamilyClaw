from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.db.utils import utc_now_iso
from app.modules.realtime.connection_manager import realtime_connection_manager
from app.modules.realtime.schemas import build_plugin_job_updated_event
import app.db.session as db_session_module

from . import repository
from .job_service import get_plugin_job_detail


async def publish_plugin_job_updates(db: Session, *, household_id: str, job_id: str) -> None:
    detail = get_plugin_job_detail(db, household_id=household_id, job_id=job_id)
    notification_ids = _websocket_notification_ids(db, job_id=job_id)

    await realtime_connection_manager.broadcast_household(
        household_id=household_id,
        event_builder=lambda session_id, seq: build_plugin_job_updated_event(
            session_id=session_id,
            seq=seq,
            payload={
                "job": detail.job.model_dump(mode="json"),
                "allowed_actions": detail.allowed_actions,
                "latest_attempt": detail.latest_attempt.model_dump(mode="json") if detail.latest_attempt is not None else None,
                "recent_notifications": [item.model_dump(mode="json") for item in detail.recent_notifications],
            },
        ),
    )
    if notification_ids:
        _mark_delivered(notification_ids)


def _websocket_notification_ids(db: Session, *, job_id: str) -> list[str]:
    rows = repository.list_plugin_job_notifications(db, job_id=job_id)
    return [item.id for item in rows if item.channel == "websocket" and item.delivered_at is None]


def _mark_delivered(notification_ids: Iterable[str]) -> None:
    ids = list(notification_ids)
    if not ids:
        return
    with db_session_module.SessionLocal() as db:
        delivered_at = utc_now_iso()
        for notification_id in ids:
            repository.mark_plugin_job_notification_delivered(db, notification_id=notification_id, delivered_at=delivered_at)
        db.commit()
