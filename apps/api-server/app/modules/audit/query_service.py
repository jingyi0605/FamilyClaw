from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.household.service import get_household_or_404


def list_audit_logs(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    action: str | None = None,
) -> tuple[list[AuditLog], int]:
    get_household_or_404(db, household_id)

    filters = [AuditLog.household_id == household_id]
    if action:
        filters.append(AuditLog.action == action)

    total = db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    statement = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(db.scalars(statement).all())
    return items, total

