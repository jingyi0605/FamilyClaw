from collections.abc import Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.modules.memory.models import EventRecord, MemoryCard, MemoryCardMember, MemoryCardRevision


def add_event_record(db: Session, row: EventRecord) -> EventRecord:
    db.add(row)
    return row


def get_event_record(db: Session, event_id: str) -> EventRecord | None:
    return db.get(EventRecord, event_id)


def get_event_record_by_dedupe_key(
    db: Session,
    *,
    household_id: str,
    dedupe_key: str,
) -> EventRecord | None:
    stmt = select(EventRecord).where(
        EventRecord.household_id == household_id,
        EventRecord.dedupe_key == dedupe_key,
    )
    return db.scalar(stmt)


def list_event_records(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    processing_status: str | None = None,
) -> tuple[list[EventRecord], int]:
    filters = [EventRecord.household_id == household_id]
    if processing_status is not None:
        filters.append(EventRecord.processing_status == processing_status)

    total = db.scalar(select(func.count()).select_from(EventRecord).where(*filters)) or 0
    stmt: Select[tuple[EventRecord]] = (
        select(EventRecord)
        .where(*filters)
        .order_by(EventRecord.occurred_at.desc(), EventRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).all()), total


def count_event_records_by_status(db: Session, *, household_id: str) -> dict[str, int]:
    stmt = (
        select(EventRecord.processing_status, func.count())
        .where(EventRecord.household_id == household_id)
        .group_by(EventRecord.processing_status)
    )
    return {status: count for status, count in db.execute(stmt).all()}


def get_latest_event_occurred_at(db: Session, *, household_id: str) -> str | None:
    stmt = select(EventRecord.occurred_at).where(EventRecord.household_id == household_id).order_by(
        EventRecord.occurred_at.desc(),
        EventRecord.id.desc(),
    )
    return db.scalar(stmt)


def add_memory_card(db: Session, row: MemoryCard) -> MemoryCard:
    db.add(row)
    return row


def get_memory_card(db: Session, memory_id: str) -> MemoryCard | None:
    return db.get(MemoryCard, memory_id)


def get_memory_card_by_dedupe_key(
    db: Session,
    *,
    household_id: str,
    dedupe_key: str,
) -> MemoryCard | None:
    stmt = select(MemoryCard).where(
        MemoryCard.household_id == household_id,
        MemoryCard.dedupe_key == dedupe_key,
    )
    return db.scalar(stmt)


def list_memory_cards(
    db: Session,
    *,
    household_id: str,
    page: int,
    page_size: int,
    memory_type: str | None = None,
) -> tuple[list[MemoryCard], int]:
    filters = [MemoryCard.household_id == household_id]
    if memory_type is not None:
        filters.append(MemoryCard.memory_type == memory_type)

    total = db.scalar(select(func.count()).select_from(MemoryCard).where(*filters)) or 0
    stmt: Select[tuple[MemoryCard]] = (
        select(MemoryCard)
        .where(*filters)
        .order_by(MemoryCard.updated_at.desc(), MemoryCard.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(stmt).all()), total


def count_memory_cards_by_status(db: Session, *, household_id: str) -> dict[str, int]:
    stmt = (
        select(MemoryCard.status, func.count())
        .where(MemoryCard.household_id == household_id)
        .group_by(MemoryCard.status)
    )
    return {status: count for status, count in db.execute(stmt).all()}


def get_latest_memory_card_updated_at(db: Session, *, household_id: str) -> str | None:
    stmt = select(MemoryCard.updated_at).where(MemoryCard.household_id == household_id).order_by(
        MemoryCard.updated_at.desc(),
        MemoryCard.id.desc(),
    )
    return db.scalar(stmt)


def add_memory_card_member(db: Session, row: MemoryCardMember) -> MemoryCardMember:
    db.add(row)
    return row


def list_memory_card_members(db: Session, *, memory_ids: list[str]) -> Sequence[MemoryCardMember]:
    if not memory_ids:
        return []
    stmt: Select[tuple[MemoryCardMember]] = (
        select(MemoryCardMember)
        .where(MemoryCardMember.memory_id.in_(memory_ids))
        .order_by(
            MemoryCardMember.memory_id.asc(),
            MemoryCardMember.relation_role.asc(),
            MemoryCardMember.member_id.asc(),
        )
    )
    return list(db.scalars(stmt).all())


def replace_memory_card_members(
    db: Session,
    *,
    memory_id: str,
    links: list[MemoryCardMember],
) -> None:
    db.execute(delete(MemoryCardMember).where(MemoryCardMember.memory_id == memory_id))
    for link in links:
        db.add(link)


def add_memory_card_revision(db: Session, row: MemoryCardRevision) -> MemoryCardRevision:
    db.add(row)
    return row


def get_next_revision_no(db: Session, *, memory_id: str) -> int:
    stmt = select(func.max(MemoryCardRevision.revision_no)).where(MemoryCardRevision.memory_id == memory_id)
    current = db.scalar(stmt)
    return int(current or 0) + 1


def list_memory_card_revisions(db: Session, *, memory_id: str) -> Sequence[MemoryCardRevision]:
    stmt: Select[tuple[MemoryCardRevision]] = (
        select(MemoryCardRevision)
        .where(MemoryCardRevision.memory_id == memory_id)
        .order_by(MemoryCardRevision.revision_no.desc(), MemoryCardRevision.id.desc())
    )
    return list(db.scalars(stmt).all())
