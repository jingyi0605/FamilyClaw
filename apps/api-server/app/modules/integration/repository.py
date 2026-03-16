from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.integration.models import IntegrationInstance


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
