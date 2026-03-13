from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.plugin.models import PluginRawRecord, PluginRun


def add_plugin_run(db: Session, row: PluginRun) -> PluginRun:
    db.add(row)
    return row


def get_plugin_run(db: Session, run_id: str) -> PluginRun | None:
    return db.get(PluginRun, run_id)


def list_plugin_runs(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
) -> list[PluginRun]:
    filters = [PluginRun.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginRun.plugin_id == plugin_id)

    stmt: Select[tuple[PluginRun]] = (
        select(PluginRun)
        .where(*filters)
        .order_by(PluginRun.started_at.desc(), PluginRun.id.desc())
    )
    return list(db.scalars(stmt).all())


def add_plugin_raw_record(db: Session, row: PluginRawRecord) -> PluginRawRecord:
    db.add(row)
    return row


def list_plugin_raw_records(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
    run_id: str | None = None,
) -> list[PluginRawRecord]:
    filters = [PluginRawRecord.household_id == household_id]
    if plugin_id is not None:
        filters.append(PluginRawRecord.plugin_id == plugin_id)
    if run_id is not None:
        filters.append(PluginRawRecord.run_id == run_id)

    stmt: Select[tuple[PluginRawRecord]] = (
        select(PluginRawRecord)
        .where(*filters)
        .order_by(PluginRawRecord.captured_at.desc(), PluginRawRecord.id.desc())
    )
    return list(db.scalars(stmt).all())
