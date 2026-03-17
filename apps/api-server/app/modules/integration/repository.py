from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance


def add_integration_instance(db: Session, row: IntegrationInstance) -> IntegrationInstance:
    db.add(row)
    return row


def get_integration_instance(db: Session, instance_id: str) -> IntegrationInstance | None:
    return db.get(IntegrationInstance, instance_id)


def list_integration_instances(
    db: Session,
    *,
    household_id: str,
    plugin_id: str | None = None,
) -> list[IntegrationInstance]:
    filters = [IntegrationInstance.household_id == household_id]
    if plugin_id is not None:
        filters.append(IntegrationInstance.plugin_id == plugin_id)

    stmt: Select[tuple[IntegrationInstance]] = (
        select(IntegrationInstance)
        .where(*filters)
        .order_by(IntegrationInstance.updated_at.desc(), IntegrationInstance.id.desc())
    )
    return list(db.scalars(stmt).all())


def delete_integration_instance(db: Session, row: IntegrationInstance) -> None:
    db.delete(row)


def add_integration_discovery(db: Session, row: IntegrationDiscovery) -> IntegrationDiscovery:
    db.add(row)
    return row


def get_integration_discovery(db: Session, discovery_id: str) -> IntegrationDiscovery | None:
    return db.get(IntegrationDiscovery, discovery_id)


def get_integration_discovery_by_plugin_and_key(
    db: Session,
    *,
    plugin_id: str,
    discovery_key: str,
) -> IntegrationDiscovery | None:
    stmt: Select[tuple[IntegrationDiscovery]] = select(IntegrationDiscovery).where(
        IntegrationDiscovery.plugin_id == plugin_id,
        IntegrationDiscovery.discovery_key == discovery_key,
    )
    return db.scalar(stmt)


def list_integration_discoveries(
    db: Session,
    *,
    household_id: str,
    integration_instance_id: str | None = None,
    plugin_id: str | None = None,
    status: str | None = None,
    include_unbound: bool = False,
) -> list[IntegrationDiscovery]:
    household_filter = IntegrationDiscovery.household_id == household_id
    if include_unbound:
        household_filter = or_(household_filter, IntegrationDiscovery.household_id.is_(None))
    filters = [household_filter]
    if integration_instance_id is not None:
        filters.append(IntegrationDiscovery.integration_instance_id == integration_instance_id)
    if plugin_id is not None:
        filters.append(IntegrationDiscovery.plugin_id == plugin_id)
    if status is not None:
        filters.append(IntegrationDiscovery.status == status)

    stmt: Select[tuple[IntegrationDiscovery]] = (
        select(IntegrationDiscovery)
        .where(*filters)
        .order_by(IntegrationDiscovery.updated_at.desc(), IntegrationDiscovery.id.desc())
    )
    return list(db.scalars(stmt).all())
