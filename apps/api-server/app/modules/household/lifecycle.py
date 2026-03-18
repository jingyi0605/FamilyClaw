from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.modules.household.models import Household
from app.modules.plugin.storage_cleanup import cleanup_household_plugin_storage

_DELETED_HOUSEHOLD_IDS_KEY = "deleted_household_ids_for_plugin_storage_cleanup"


@event.listens_for(Session, "before_flush")
def collect_deleted_household_ids_for_plugin_storage_cleanup(
    session: Session,
    flush_context,
    instances,
) -> None:
    deleted_household_ids: set[str] = session.info.setdefault(_DELETED_HOUSEHOLD_IDS_KEY, set())
    for item in session.deleted:
        if isinstance(item, Household):
            deleted_household_ids.add(item.id)


@event.listens_for(Session, "after_commit")
def cleanup_deleted_household_plugin_storage(session: Session) -> None:
    deleted_household_ids = session.info.pop(_DELETED_HOUSEHOLD_IDS_KEY, None)
    if not deleted_household_ids:
        return
    for household_id in sorted(deleted_household_ids):
        cleanup_household_plugin_storage(household_id)


@event.listens_for(Session, "after_rollback")
def clear_deleted_household_plugin_storage_cleanup_state(session: Session) -> None:
    session.info.pop(_DELETED_HOUSEHOLD_IDS_KEY, None)
