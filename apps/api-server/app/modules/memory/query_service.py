from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, desc, exists, false, func, literal, not_, or_, select, text, true
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.member.models import Member
from app.modules.memory.models import MemoryCard, MemoryCardMember
from app.modules.memory.recall_projection import (
    MEMORY_RECALL_EMBEDDING_DIMENSION,
    build_text_embedding,
    build_tsquery_text,
    compute_recency_score,
    derive_memory_group,
    extract_search_terms,
    to_vector_literal,
)
from app.modules.memory.repository import (
    get_memory_card as repo_get_memory_card,
    is_pgvector_enabled,
    list_memory_cards as repo_list_memory_cards,
    list_memory_cards_by_ids,
)
from app.modules.memory.schemas import (
    MemoryHotSummaryItem,
    MemoryHotSummaryRead,
    MemoryQueryHit,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryRecallBundleRead,
    MemoryRecallHit,
)
from app.modules.memory.service import _build_card_reads
from app.modules.permission.models import MemberPermission
from app.modules.relationship.models import MemberRelationship

_HOT_SUMMARY_LOCK = Lock()
_HOT_SUMMARY_CACHE: dict[str, MemoryHotSummaryRead] = {}


@dataclass(slots=True)
class _HybridCandidate:
    memory_id: str
    matched_terms: list[str] = field(default_factory=list)
    fts_score: float | None = None
    vector_score: float | None = None


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
    if actor.account_type == "system":
        return requested_member_id or actor.member_id

    effective_member_id = actor.member_id
    if effective_member_id is None and actor.actor_type == "member":
        effective_member_id = actor.actor_id

    if effective_member_id is None:
        return None

    if requested_member_id is not None and requested_member_id != effective_member_id:
        return effective_member_id
    return effective_member_id


def resolve_requester_member_id(actor: ActorContext, requested_member_id: str | None) -> str | None:
    return _resolve_requester_member_id(actor, requested_member_id)


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
        if is_self:
            return "self" in allow_scopes and "self" not in deny_scopes
        if is_related_member:
            return "self" in allow_scopes and "self" not in deny_scopes
        if is_child:
            return "children" in allow_scopes and "children" not in deny_scopes
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

    try:
        return _query_memory_cards_impl(
            db,
            payload=payload,
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
        )
    except Exception:
        fallback_hits = _build_visible_fallback_hits(
            db,
            payload=payload,
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
        )
        return _build_query_response(
            payload=payload,
            requester_member_id=requester_member_id,
            hits=fallback_hits,
            degraded=True,
            degrade_reasons=["memory_recall_query_failed"],
        )


def _query_memory_cards_impl(
    db: Session,
    *,
    payload: MemoryQueryRequest,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
) -> MemoryQueryResponse:
    filters = _build_base_filters(
        payload=payload,
        actor=actor,
        requester_member_id=requester_member_id,
        requester_role=requester_role,
        children_ids=children_ids,
        allow_scopes=allow_scopes,
        deny_scopes=deny_scopes,
    )
    query_terms = extract_search_terms(payload.query)
    candidate_limit = max(payload.limit * 4, payload.group_limit * 4, 12)
    candidate_map: dict[str, _HybridCandidate] = {}
    degrade_reasons: list[str] = []

    if payload.query:
        ts_query_text = build_tsquery_text(payload.query)
        if ts_query_text:
            for memory_id, fts_score in _query_fts_candidates(
                db,
                filters=filters,
                ts_query_text=ts_query_text,
                limit=candidate_limit,
            ):
                candidate = candidate_map.setdefault(memory_id, _HybridCandidate(memory_id=memory_id, matched_terms=query_terms))
                candidate.fts_score = float(fts_score or 0.0)

        vector_degrade_reason = _query_vector_candidates(
            db,
            filters=filters,
            query=payload.query,
            limit=candidate_limit,
            candidate_map=candidate_map,
            matched_terms=query_terms,
        )
        if vector_degrade_reason is not None:
            degrade_reasons.append(vector_degrade_reason)
    else:
        candidate_map = {
            card.id: _HybridCandidate(memory_id=card.id)
            for card in _list_visible_cards_for_summary(db, filters=filters, limit=max(candidate_limit, 20))
        }

    if not candidate_map:
        return _build_query_response(
            payload=payload,
            requester_member_id=requester_member_id,
            hits=[],
            degraded=bool(degrade_reasons),
            degrade_reasons=degrade_reasons,
        )

    cards = _build_card_reads(
        db,
        list(list_memory_cards_by_ids(db, memory_ids=list(candidate_map.keys()))),
    )
    hits = _rerank_hits(
        cards=cards,
        candidates=candidate_map,
        payload=payload,
        requester_member_id=requester_member_id,
    )
    return _build_query_response(
        payload=payload,
        requester_member_id=requester_member_id,
        hits=hits,
        degraded=bool(degrade_reasons),
        degrade_reasons=degrade_reasons,
    )


def _build_query_response(
    *,
    payload: MemoryQueryRequest,
    requester_member_id: str | None,
    hits: list[MemoryQueryHit],
    degraded: bool,
    degrade_reasons: list[str],
) -> MemoryQueryResponse:
    grouped_hits = _group_hits(hits, group_limit=payload.group_limit)
    flat_hits = sorted(
        grouped_hits["stable_facts"] + grouped_hits["recent_events"],
        key=lambda item: (item.score, item.card.updated_at, item.card.importance),
        reverse=True,
    )[: payload.limit]
    return MemoryQueryResponse(
        household_id=payload.household_id,
        requester_member_id=requester_member_id,
        total=len(hits),
        query=payload.query,
        items=flat_hits,
        recall=MemoryRecallBundleRead(
            stable_facts=[_to_recall_hit(item) for item in grouped_hits["stable_facts"]],
            recent_events=[_to_recall_hit(item) for item in grouped_hits["recent_events"]],
            degraded=degraded,
            degrade_reasons=degrade_reasons,
        ),
        degraded=degraded,
        degrade_reasons=degrade_reasons,
    )


def _group_hits(hits: list[MemoryQueryHit], *, group_limit: int) -> dict[str, list[MemoryQueryHit]]:
    grouped: dict[str, list[MemoryQueryHit]] = {"stable_facts": [], "recent_events": []}
    for group_name in grouped:
        ranked = [item for item in hits if item.group_name == group_name]
        ranked.sort(key=lambda item: (item.score, item.card.updated_at, item.card.importance), reverse=True)
        for index, item in enumerate(ranked[:group_limit], start=1):
            item.rank = index
            grouped[group_name].append(item)
    return grouped


def _to_recall_hit(hit: MemoryQueryHit) -> MemoryRecallHit:
    return MemoryRecallHit(
        memory_id=hit.memory_id,
        source_id=hit.source_id,
        source_kind=hit.source_kind,
        group_name=hit.group_name,
        layer=hit.layer,
        title=hit.card.title,
        summary=hit.card.summary,
        memory_type=hit.card.memory_type,
        visibility=hit.card.visibility,
        subject_member_id=hit.card.subject_member_id,
        updated_at=hit.card.updated_at,
        occurred_at=hit.card.last_observed_at or hit.card.effective_at or hit.card.updated_at,
        score=hit.score,
        rank=hit.rank,
        fts_score=hit.fts_score,
        vector_score=hit.vector_score,
        reason=hit.reason,
        matched_terms=hit.matched_terms,
    )


def _rerank_hits(
    *,
    cards,
    candidates: dict[str, _HybridCandidate],
    payload: MemoryQueryRequest,
    requester_member_id: str | None,
) -> list[MemoryQueryHit]:
    hits: list[MemoryQueryHit] = []
    for card in cards:
        candidate = candidates.get(card.id)
        if candidate is None:
            continue
        group_name = derive_memory_group(card.memory_type)
        importance_score = round(card.importance / 5.0, 6)
        confidence_score = round(card.confidence, 6)
        recency_score = compute_recency_score(card.last_observed_at, card.effective_at, card.updated_at)
        member_match_score = _compute_member_match_score(
            card,
            member_id=payload.member_id,
            requester_member_id=requester_member_id,
        )
        visibility_score = _compute_visibility_score(
            card,
            requester_member_id=requester_member_id,
        )
        fts_score = round(candidate.fts_score or 0.0, 6)
        vector_score = round(candidate.vector_score or 0.0, 6)
        score = _compute_hybrid_score(
            group_name=group_name,
            fts_score=fts_score,
            vector_score=vector_score,
            importance_score=importance_score,
            confidence_score=confidence_score,
            recency_score=recency_score,
            member_match_score=member_match_score,
            visibility_score=visibility_score,
        )
        if payload.query and score <= 0:
            continue
        hits.append(
            MemoryQueryHit(
                card=card,
                score=score,
                rank=1,
                group_name=group_name,
                layer="L3",
                memory_id=card.id,
                source_kind="memory_card",
                source_id=card.source_event_id or card.source_raw_record_id or card.id,
                fts_score=fts_score if fts_score > 0 else None,
                vector_score=vector_score if vector_score > 0 else None,
                reason={
                    "fts_score": fts_score,
                    "vector_score": vector_score,
                    "importance_score": importance_score,
                    "confidence_score": confidence_score,
                    "recency_score": recency_score,
                    "member_match_score": member_match_score,
                    "visibility_score": visibility_score,
                },
                matched_terms=candidate.matched_terms,
            )
        )
    hits.sort(key=lambda item: (item.score, item.card.updated_at, item.card.importance), reverse=True)
    return hits


def _compute_hybrid_score(
    *,
    group_name: str,
    fts_score: float,
    vector_score: float,
    importance_score: float,
    confidence_score: float,
    recency_score: float,
    member_match_score: float,
    visibility_score: float,
) -> float:
    if group_name == "recent_events":
        score = (
            fts_score * 0.28
            + vector_score * 0.24
            + recency_score * 0.22
            + importance_score * 0.12
            + confidence_score * 0.08
            + member_match_score * 0.04
            + visibility_score * 0.02
        )
    else:
        score = (
            fts_score * 0.34
            + vector_score * 0.28
            + importance_score * 0.16
            + confidence_score * 0.12
            + member_match_score * 0.05
            + visibility_score * 0.03
            + recency_score * 0.02
        )
    return round(max(score, 0.0), 6)


def _compute_member_match_score(card, *, member_id: str | None, requester_member_id: str | None) -> float:
    if member_id and card.subject_member_id == member_id:
        return 1.0
    if member_id and any(link.member_id == member_id for link in card.related_members):
        return 0.8
    if requester_member_id and card.subject_member_id == requester_member_id:
        return 0.6
    return 0.0


def _compute_visibility_score(card, *, requester_member_id: str | None) -> float:
    if requester_member_id and card.subject_member_id == requester_member_id and card.visibility in {"private", "sensitive"}:
        return 1.0
    if card.visibility == "family":
        return 0.8
    if card.visibility == "private":
        return 0.9
    if card.visibility == "sensitive":
        return 0.95
    return 0.6


def _query_fts_candidates(
    db: Session,
    *,
    filters: list,
    ts_query_text: str,
    limit: int,
) -> list[tuple[str, float]]:
    ts_query = func.to_tsquery("simple", ts_query_text)
    rank_expr = func.ts_rank_cd(MemoryCard.search_tsv, ts_query).label("fts_score")
    stmt = (
        select(MemoryCard.id, rank_expr)
        .where(*filters)
        .where(MemoryCard.search_tsv.is_not(None))
        .where(MemoryCard.search_tsv.op("@@")(ts_query))
        .order_by(rank_expr.desc(), MemoryCard.updated_at.desc(), MemoryCard.id.desc())
        .limit(limit)
    )
    return [(str(row.id), float(row.fts_score or 0.0)) for row in db.execute(stmt).all()]


def _query_vector_candidates(
    db: Session,
    *,
    filters: list,
    query: str,
    limit: int,
    candidate_map: dict[str, _HybridCandidate],
    matched_terms: list[str],
) -> str | None:
    if not is_pgvector_enabled(db):
        return "pgvector_unavailable"

    query_embedding = build_text_embedding(query)
    query_embedding_literal = to_vector_literal(query_embedding)
    if query_embedding_literal is None:
        return "embedding_unavailable"

    distance_expr = MemoryCard.embedding.op("<->")(
        text(f"CAST(:query_embedding AS vector({MEMORY_RECALL_EMBEDDING_DIMENSION}))")
    ).label("vector_distance")
    stmt = (
        select(MemoryCard.id, distance_expr)
        .where(*filters)
        .where(MemoryCard.embedding.is_not(None))
        .order_by(distance_expr.asc(), MemoryCard.updated_at.desc(), MemoryCard.id.desc())
        .limit(limit)
    )
    try:
        rows = db.execute(stmt, {"query_embedding": query_embedding_literal}).all()
    except Exception:
        return "vector_query_failed"

    for row in rows:
        distance = float(row.vector_distance or 0.0)
        vector_score = round(1.0 / (1.0 + max(distance, 0.0)), 6)
        candidate = candidate_map.setdefault(str(row.id), _HybridCandidate(memory_id=str(row.id), matched_terms=matched_terms))
        candidate.vector_score = vector_score
    return None


def _list_visible_cards_for_summary(db: Session, *, filters: list, limit: int):
    stmt: Select[tuple[MemoryCard]] = (
        select(MemoryCard)
        .where(*filters)
        .order_by(
            MemoryCard.importance.desc(),
            MemoryCard.confidence.desc(),
            MemoryCard.updated_at.desc(),
            MemoryCard.id.desc(),
        )
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _build_visible_fallback_hits(
    db: Session,
    *,
    payload: MemoryQueryRequest,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
) -> list[MemoryQueryHit]:
    rows, _ = repo_list_memory_cards(
        db,
        household_id=payload.household_id,
        page=1,
        page_size=max(payload.limit * 2, payload.group_limit * 2, 12),
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
    hits: list[MemoryQueryHit] = []
    for card in visible_cards:
        if payload.member_id and card.subject_member_id != payload.member_id:
            continue
        if payload.status and card.status != payload.status:
            continue
        if payload.visibility and card.visibility != payload.visibility:
            continue
        recency_score = compute_recency_score(card.last_observed_at, card.effective_at, card.updated_at)
        score = round(card.importance / 5.0 + card.confidence * 0.5 + recency_score * 0.2, 6)
        hits.append(
            MemoryQueryHit(
                card=card,
                score=score,
                rank=1,
                group_name=derive_memory_group(card.memory_type),
                layer="L3",
                memory_id=card.id,
                source_kind="memory_card",
                source_id=card.source_event_id or card.source_raw_record_id or card.id,
                reason={"fallback": True, "recency_score": recency_score},
                matched_terms=[],
            )
        )
    hits.sort(key=lambda item: (item.score, item.card.updated_at, item.card.importance), reverse=True)
    return hits


def _build_base_filters(
    *,
    payload: MemoryQueryRequest,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
) -> list:
    filters = [MemoryCard.household_id == payload.household_id]
    if payload.memory_type is not None:
        filters.append(MemoryCard.memory_type == payload.memory_type)
    if payload.status is not None:
        filters.append(MemoryCard.status == payload.status)
    if payload.visibility is not None:
        filters.append(MemoryCard.visibility == payload.visibility)
    if payload.member_id is not None:
        filters.append(MemoryCard.subject_member_id == payload.member_id)
    filters.append(
        _build_visibility_predicate(
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
        )
    )
    return filters


def _build_visibility_predicate(
    *,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
):
    if actor.role == "admin":
        return true()

    is_self = false()
    is_related_member = false()
    if requester_member_id is not None:
        is_self = MemoryCard.subject_member_id == requester_member_id
        is_related_member = exists(
            select(literal(1)).where(
                MemoryCardMember.memory_id == MemoryCard.id,
                MemoryCardMember.member_id == requester_member_id,
            )
        )
    is_child = MemoryCard.subject_member_id.in_(tuple(children_ids)) if children_ids else false()

    clauses = []
    if "public" in allow_scopes and "public" not in deny_scopes:
        clauses.append(MemoryCard.visibility == "public")
    if "self" in allow_scopes and "self" not in deny_scopes:
        clauses.append(and_(MemoryCard.visibility.in_(["family", "private"]), or_(is_self, is_related_member)))
        clauses.append(and_(MemoryCard.visibility == "sensitive", is_self))
    if "children" in allow_scopes and "children" not in deny_scopes:
        clauses.append(and_(MemoryCard.visibility.in_(["family", "private"]), is_child))
        if requester_role in {"adult", "elder", "admin"}:
            clauses.append(and_(MemoryCard.visibility == "sensitive", is_child))
    if "family" in allow_scopes and "family" not in deny_scopes:
        clauses.append(
            and_(
                MemoryCard.visibility == "family",
                not_(or_(is_self, is_related_member, is_child)),
            )
        )
    if not clauses:
        return false()
    return or_(*clauses)


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
            status="active",
            limit=12,
            group_limit=5,
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
            if item.group_name == "recent_events"
        ][:3],
    )
    with _HOT_SUMMARY_LOCK:
        _HOT_SUMMARY_CACHE[cache_key] = summary
    return summary


def get_visible_memory_card_or_404(
    db: Session,
    *,
    memory_id: str,
    actor: ActorContext,
    requester_member_id: str | None = None,
):
    row = repo_get_memory_card(db, memory_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory card not found")
    card = _build_card_reads(db, [row])[0]
    effective_requester_member_id = _resolve_requester_member_id(actor, requester_member_id)
    requester_role = _load_member_role(db, effective_requester_member_id)
    children_ids = _load_children_ids(db, effective_requester_member_id)
    allow_scopes, deny_scopes = _load_memory_permission_scopes(
        db,
        effective_requester_member_id,
        requester_role,
    )
    if not _is_card_visible(
        card,
        actor=actor,
        requester_member_id=effective_requester_member_id,
        requester_role=requester_role,
        children_ids=children_ids,
        allow_scopes=allow_scopes,
        deny_scopes=deny_scopes,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="memory card not visible to current actor")
    return card


def ensure_can_mutate_memory_card(
    db: Session,
    *,
    memory_id: str,
    actor: ActorContext,
    action: str,
    requester_member_id: str | None = None,
):
    card = get_visible_memory_card_or_404(
        db,
        memory_id=memory_id,
        actor=actor,
        requester_member_id=requester_member_id,
    )
    effective_requester_member_id = _resolve_requester_member_id(actor, requester_member_id)
    if actor.role == "admin":
        return card
    if actor.actor_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor required")
    if action == "delete":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member actor cannot delete memory card")
    if card.visibility == "sensitive" and card.subject_member_id != effective_requester_member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="sensitive memory can only be corrected by owner")
    return card
