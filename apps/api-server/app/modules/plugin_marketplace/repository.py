from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.plugin_marketplace.models import (
    PluginMarketplaceEntrySnapshot,
    PluginMarketplaceInstallTask,
    PluginMarketplaceInstance,
    PluginMarketplaceSource,
)


def add_marketplace_source(db: Session, row: PluginMarketplaceSource) -> PluginMarketplaceSource:
    db.add(row)
    return row


def get_marketplace_source(db: Session, source_id: str) -> PluginMarketplaceSource | None:
    return db.get(PluginMarketplaceSource, source_id)


def get_marketplace_source_by_repo(
    db: Session,
    *,
    repo_url: str,
    branch: str,
    entry_root: str,
) -> PluginMarketplaceSource | None:
    stmt: Select[tuple[PluginMarketplaceSource]] = select(PluginMarketplaceSource).where(
        PluginMarketplaceSource.repo_url == repo_url,
        PluginMarketplaceSource.branch == branch,
        PluginMarketplaceSource.entry_root == entry_root,
    )
    return db.scalar(stmt)


def list_marketplace_sources(db: Session, *, enabled_only: bool = False) -> list[PluginMarketplaceSource]:
    stmt: Select[tuple[PluginMarketplaceSource]] = select(PluginMarketplaceSource).order_by(
        PluginMarketplaceSource.created_at.asc(),
        PluginMarketplaceSource.source_id.asc(),
    )
    if enabled_only:
        stmt = stmt.where(PluginMarketplaceSource.enabled.is_(True))
    return list(db.scalars(stmt).all())


def list_marketplace_entry_snapshots(
    db: Session,
    *,
    source_id: str | None = None,
    sync_status: str | None = None,
) -> list[PluginMarketplaceEntrySnapshot]:
    stmt: Select[tuple[PluginMarketplaceEntrySnapshot]] = select(PluginMarketplaceEntrySnapshot).order_by(
        PluginMarketplaceEntrySnapshot.name.asc(),
        PluginMarketplaceEntrySnapshot.plugin_id.asc(),
    )
    if source_id is not None:
        stmt = stmt.where(PluginMarketplaceEntrySnapshot.source_id == source_id)
    if sync_status is not None:
        stmt = stmt.where(PluginMarketplaceEntrySnapshot.sync_status == sync_status)
    return list(db.scalars(stmt).all())


def get_marketplace_entry_snapshot(
    db: Session,
    *,
    source_id: str,
    plugin_id: str,
) -> PluginMarketplaceEntrySnapshot | None:
    stmt: Select[tuple[PluginMarketplaceEntrySnapshot]] = select(PluginMarketplaceEntrySnapshot).where(
        PluginMarketplaceEntrySnapshot.source_id == source_id,
        PluginMarketplaceEntrySnapshot.plugin_id == plugin_id,
    )
    return db.scalar(stmt)


def add_marketplace_entry_snapshot(
    db: Session,
    row: PluginMarketplaceEntrySnapshot,
) -> PluginMarketplaceEntrySnapshot:
    db.add(row)
    return row


def delete_marketplace_entry_snapshots_for_source(db: Session, *, source_id: str) -> None:
    for row in list_marketplace_entry_snapshots(db, source_id=source_id):
        db.delete(row)


def add_marketplace_install_task(db: Session, row: PluginMarketplaceInstallTask) -> PluginMarketplaceInstallTask:
    db.add(row)
    return row


def get_marketplace_install_task(db: Session, task_id: str) -> PluginMarketplaceInstallTask | None:
    return db.get(PluginMarketplaceInstallTask, task_id)


def list_marketplace_install_tasks(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
) -> list[PluginMarketplaceInstallTask]:
    stmt: Select[tuple[PluginMarketplaceInstallTask]] = select(PluginMarketplaceInstallTask).where(
        PluginMarketplaceInstallTask.household_id == household_id,
    ).order_by(
        PluginMarketplaceInstallTask.created_at.desc(),
        PluginMarketplaceInstallTask.id.desc(),
    )
    if plugin_id is not None:
        stmt = stmt.where(PluginMarketplaceInstallTask.plugin_id == plugin_id)
    return list(db.scalars(stmt).all())


def add_marketplace_instance(db: Session, row: PluginMarketplaceInstance) -> PluginMarketplaceInstance:
    db.add(row)
    return row


def get_marketplace_instance(db: Session, instance_id: str) -> PluginMarketplaceInstance | None:
    return db.get(PluginMarketplaceInstance, instance_id)


def get_marketplace_instance_for_plugin(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
) -> PluginMarketplaceInstance | None:
    stmt: Select[tuple[PluginMarketplaceInstance]] = select(PluginMarketplaceInstance).where(
        PluginMarketplaceInstance.household_id == household_id,
        PluginMarketplaceInstance.plugin_id == plugin_id,
    )
    return db.scalar(stmt)


def list_marketplace_instances(db: Session, *, household_id: str) -> list[PluginMarketplaceInstance]:
    stmt: Select[tuple[PluginMarketplaceInstance]] = select(PluginMarketplaceInstance).where(
        PluginMarketplaceInstance.household_id == household_id,
    ).order_by(
        PluginMarketplaceInstance.created_at.desc(),
        PluginMarketplaceInstance.id.desc(),
    )
    return list(db.scalars(stmt).all())
