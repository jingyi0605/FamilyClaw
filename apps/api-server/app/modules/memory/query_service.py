from __future__ import annotations

from threading import Lock

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.member.models import Member
from app.modules.memory.repository import list_memory_cards as repo_list_memory_cards
from app.modules.memory.service import _build_card_reads
from app.modules.memory.schemas import (
    MemoryHotSummaryItem,
    MemoryHotSummaryRead,
    MemoryQueryHit,
    MemoryQueryRequest,
    MemoryQueryResponse,
)
from app.modules.permission.models import MemberPermission
from app.modules.relationship.models import MemberRelationship

_HOT_SUMMARY_LOCK = Lock()
_HOT_SUMMARY_CACHE: dict[str, MemoryHotSummaryRead] = {}


def invalidate_memory_hot_summary(household_id: str) -> None:
    with _HOT_SUMMARY_LOCK:
        for key in list(_HOT_SUMMARY_CACHE.keys()):
            if key.startswith(f"{household_id}:"):
                _HOT_SUMMARY_CACHE.pop(key, None)


def _summary_cache_key(household_id: str, actor: ActorContext, requester_member_id: str | None) -> str:
    return f"{household_id}:{actor.role}:{actor.actor_id or '-'}:{requester_member_id or '-'}"


def _resolve_requester_member_id(actor: ActorContext, requested_member_id: str | None) -> str | None:
    if actor.role == "admin":
        return requested_member_id
    if actor.actor_id is None:
        return None
    if requested_member_id is not None and requested_member_id != actor.actor_id:
        return actor.actor_id
    return actor.actor_id


def _load_member_role(db: Session, member_id: str | None) -> str:
    if member_id is None:
        return "guest"
    row = db.get(Member, member_id)
    return row.role if row is not None else "guest"


def _load_children_ids(db: Session, requester_member_id: str | None) -> set[str]:
    if requester_member_id is None:
        return set()
    rows = (
        db.query(MemberRelationship)
        .filter(
            MemberRelationship.source_member_id == requester_member_id,
            MemberRelationship.relation_type.in_(["parent", "guardian", "caregiver"]),
        )
        .all()
    )
    return {row.target_member_id for row in rows}


def _load_memory_permission_scopes(db: Session, requester_member_id: str | None, requester_role: str) -> tuple[set[str], set[str]]:
    allow_scopes: set[str] = {"public"}
    deny_scopes: set[str] = set()

    if requester_role in {"adult", "elder", "admin"}:
        allow_scopes.add("family")
    if requester_member_id is not None:
        allow_scopes.add("self")

    if requester_member_id is None:
        return allow_scopes, deny_scopes

    rows = (
        db.query(MemberPermission)
        .filter(
            MemberPermission.member_id == requester_member_id,
            MemberPermission.resource_type == "memory",
            MemberPermission.action == "read",
        )
        .all()
    )
    for row in rows:
        if row.effect == "allow":
            allow_scopes.add(row.resource_scope)
        elif row.effect == "deny":
            deny_scopes.add(row.resource_scope)
    return allow_scopes, deny_scopes


def _is_card_visible(
    card,
    *,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
) -> bool:
    if actor.role == "admin":
        return True

    subject_member_id = card.subject_member_id
    is_self = requester_member_id is not None and subject_member_id == requester_member_id
    is_child = requester_member_id is not None and subject_member_id in children_ids
    is_related_member = requester_member_id is not None and any(
        link.member_id == requester_member_id for link in card.related_members
    )

    if card.visibility == "public":
        return "public" in allow_scopes and "public" not in deny_scopes

    if card.visibility == "family":
        return "family" in allow_scopes and "family" not in deny_scopes

    if card.visibility == "private":
        if is_self or is_related_member:
            return "self" in allow_scopes and "self" not in deny_scopes
        if is_child:
            return "children" in allow_scopes and "children" not in deny_scopes
        return False

    if card.visibility == "sensitive":
        if is_self:
            return "self" in allow_scopes and "self" not in deny_scopes
        if is_child and requester_role in {"adult", "elder"}:
            return "children" in allow_scopes and "children" not in deny_scopes
        return False

    return False


def _score_card(card, query: str | None, member_id: str | None) -> tuple[int, list[str]]:
    score = 0
    matched_terms: list[str] = []
    searchable_text = " ".join(
        part
        for part in [card.title, card.summary, card.normalized_text or ""]
        if isinstance(part, str)
    ).lower()

    if member_id and card.subject_member_id == member_id:
        score += 40
        matched_terms.append("subject_member")
    if card.importance >= 4:
        score += 10
        matched_terms.append("importance")
    if card.confidence >= 0.8:
        score += 10
        matched_terms.append("confidence")
    if card.memory_type == "preference":
        score += 3

    if query:
        tokens = [token.strip().lower() for token in query.split() if token.strip()]
        if len(tokens) == 1 and " " not in query.strip():
            tokens = tokens or [query.strip().lower()]
        for token in tokens:
            if token and token in searchable_text:
                score += 25
                matched_terms.append(token)
    return score, matched_terms


def query_memory_cards(
    db: Session,
    *,
    payload: MemoryQueryRequest,
    actor: ActorContext,
) -> MemoryQueryResponse:
    requester_member_id = _resolve_requester_member_id(actor, payload.requester_member_id)
    requester_role = _load_member_role(db, requester_member_id)
    children_ids = _load_children_ids(db, requester_member_id)
    allow_scopes, deny_scopes = _load_memory_permission_scopes(db, requester_member_id, requester_role)

    rows, _ = repo_list_memory_cards(
        db,
        household_id=payload.household_id,
        page=1,
        page_size=500,
        memory_type=payload.memory_type,
    )
    cards = _build_card_reads(db, rows)

    visible_cards = [
        card
        for card in cards
        if _is_card_visible(
            card,
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
        )
    ]

    filtered_cards = []
    for card in visible_cards:
        if payload.member_id and card.subject_member_id != payload.member_id:
            continue
        if payload.status and card.status != payload.status:
            continue
        if payload.visibility and card.visibility != payload.visibility:
            continue
        filtered_cards.append(card)

    hits: list[MemoryQueryHit] = []
    for card in filtered_cards:
        score, matched_terms = _score_card(card, payload.query, payload.member_id)
        if payload.query and score < 25:
            continue
        hits.append(MemoryQueryHit(card=card, score=score, matched_terms=matched_terms))

    hits.sort(
        key=lambda item: (
            item.score,
            item.card.updated_at,
            item.card.importance,
        ),
        reverse=True,
    )
    return MemoryQueryResponse(
        household_id=payload.household_id,
        requester_member_id=requester_member_id,
        total=len(hits),
        query=payload.query,
        items=hits[: payload.limit],
    )


def get_memory_hot_summary(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None = None,
) -> MemoryHotSummaryRead:
    effective_requester_member_id = _resolve_requester_member_id(actor, requester_member_id)
    cache_key = _summary_cache_key(household_id, actor, effective_requester_member_id)
    with _HOT_SUMMARY_LOCK:
        cached = _HOT_SUMMARY_CACHE.get(cache_key)
        if cached is not None:
            return cached

    result = query_memory_cards(
        db,
        payload=MemoryQueryRequest(
            household_id=household_id,
            requester_member_id=effective_requester_member_id,
            limit=12,
        ),
        actor=actor,
    )
    top_cards = result.items[:5]
    summary = MemoryHotSummaryRead(
        household_id=household_id,
        requester_member_id=effective_requester_member_id,
        generated_at=utc_now_iso(),
        total_visible_cards=result.total,
        top_memories=[
            MemoryHotSummaryItem(
                title=item.card.title,
                memory_id=item.card.id,
                memory_type=item.card.memory_type,
                summary=item.card.summary,
                updated_at=item.card.updated_at,
            )
            for item in top_cards
        ],
        preference_highlights=[
            item.card.summary
            for item in top_cards
            if item.card.memory_type == "preference"
        ][:3],
        recent_event_highlights=[
            item.card.summary
            for item in top_cards
            if item.card.memory_type == "event"
        ][:3],
    )
    with _HOT_SUMMARY_LOCK:
        _HOT_SUMMARY_CACHE[cache_key] = summary
    return summary
