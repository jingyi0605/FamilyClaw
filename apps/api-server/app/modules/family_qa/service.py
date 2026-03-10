from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.family_qa import repository
from app.modules.family_qa.models import QaQueryLog
from app.modules.family_qa.schemas import QaQueryLogCreate, QaQueryLogRead
from app.modules.household.models import Household
from app.modules.member.models import Member


def create_query_log(db: Session, payload: QaQueryLogCreate) -> QaQueryLogRead:
    _ensure_household_exists(db, payload.household_id)
    _validate_requester_member(db, payload.household_id, payload.requester_member_id)

    row = QaQueryLog(
        id=new_uuid(),
        household_id=payload.household_id,
        requester_member_id=payload.requester_member_id,
        question=payload.question,
        answer_type=payload.answer_type,
        answer_summary=payload.answer_summary,
        confidence=payload.confidence,
        degraded=payload.degraded,
        facts_json=dump_json([fact.model_dump(mode="json") for fact in payload.facts]) or "[]",
        created_at=utc_now_iso(),
    )
    repository.add_query_log(db, row)
    db.flush()
    return _to_query_log_read(row)


def list_query_logs(
    db: Session,
    *,
    household_id: str,
    requester_member_id: str | None = None,
    limit: int = 50,
) -> list[QaQueryLogRead]:
    _ensure_household_exists(db, household_id)
    _validate_requester_member(db, household_id, requester_member_id)
    rows = repository.list_query_logs(
        db,
        household_id=household_id,
        requester_member_id=requester_member_id,
        limit=limit,
    )
    return [_to_query_log_read(row) for row in rows]


def _ensure_household_exists(db: Session, household_id: str) -> None:
    if db.get(Household, household_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="household not found",
        )


def _validate_requester_member(db: Session, household_id: str, requester_member_id: str | None) -> None:
    if requester_member_id is None:
        return

    member = db.get(Member, requester_member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member not found",
        )
    if member.household_id != household_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requester member must belong to the same household",
        )


def _to_query_log_read(row: QaQueryLog) -> QaQueryLogRead:
    return QaQueryLogRead(
        id=row.id,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        question=row.question,
        answer_type=row.answer_type,
        answer_summary=row.answer_summary,
        confidence=row.confidence,
        degraded=row.degraded,
        facts=load_json(row.facts_json) or [],
        created_at=row.created_at,
    )
