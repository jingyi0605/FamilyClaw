from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.family_qa.models import QaQueryLog


def add_query_log(db: Session, row: QaQueryLog) -> QaQueryLog:
    db.add(row)
    return row


def get_query_log(db: Session, query_log_id: str) -> QaQueryLog | None:
    return db.get(QaQueryLog, query_log_id)


def list_query_logs(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    limit: int = 50,
) -> Sequence[QaQueryLog]:
    stmt: Select[tuple[QaQueryLog]] = (
        select(QaQueryLog)
        .where(QaQueryLog.household_id == household_id)
        .order_by(QaQueryLog.created_at.desc())
        .limit(limit)
    )
    if requester_member_id is not None:
        stmt = stmt.where(QaQueryLog.requester_member_id == requester_member_id)
    return list(db.scalars(stmt).all())
