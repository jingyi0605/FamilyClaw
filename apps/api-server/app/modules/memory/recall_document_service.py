from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import and_, exists, false, func, literal, not_, or_, select, text, true
from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import load_json, new_uuid
from app.modules.conversation.models import ConversationSessionSummary
from app.modules.member.models import Member
from app.modules.memory.models import (
    EpisodicMemoryEntry,
    KnowledgeDocument,
    MemoryCard,
    MemoryCardMember,
    MemoryRecallDocument,
)
from app.modules.memory.recall_projection import (
    MEMORY_RECALL_EMBEDDING_DIMENSION,
    build_memory_card_search_text,
    build_text_embedding,
    build_tsquery_text,
    compute_recency_score,
    derive_memory_group,
    extract_search_terms,
    to_vector_literal,
)
from app.modules.memory.repository import (
    add_memory_recall_document,
    get_memory_recall_document_by_source,
    is_memory_recall_pgvector_enabled,
    list_episodic_memory_entries_by_ids,
    list_knowledge_documents_by_ids,
    list_memory_cards_by_ids,
    list_memory_recall_documents_by_ids,
    refresh_memory_recall_document_projection,
)
from app.modules.memory.schemas import MemoryRecallBundleRead, MemoryRecallHit
from app.modules.memory.service import _build_card_reads
from app.modules.permission.models import MemberPermission
from app.modules.relationship.models import MemberRelationship

SESSION_SUMMARY_GROUP = "session_summary"
EXTERNAL_KNOWLEDGE_GROUP = "external_knowledge"


@dataclass(slots=True)
class _RecallCandidate:
    recall_document_id: str
    matched_terms: list[str] = field(default_factory=list)
    fts_score: float | None = None
    vector_score: float | None = None


@dataclass(slots=True)
class _RecallSourceSnapshot:
    layer: str
    group_name: str
    memory_id: str
    source_id: str
    source_kind: str
    title: str
    summary: str
    memory_type: str | None
    visibility: str | None
    subject_member_id: str | None
    occurred_at: str | None
    updated_at: str | None
    importance: int
    confidence: float
    related_member_ids: set[str] = field(default_factory=set)


def sync_session_summary_recall_document(db: Session, *, row: ConversationSessionSummary) -> MemoryRecallDocument:
    return _upsert_recall_document(
        db,
        household_id=row.household_id,
        layer="L1",
        source_kind="conversation_session_summary",
        source_id=row.id,
        subject_member_id=row.requester_member_id,
        visibility="private",
        group_hint=SESSION_SUMMARY_GROUP,
        search_text=_build_session_summary_search_text(row),
        importance=3,
        confidence=0.85,
        occurred_at=row.generated_at,
        updated_at=row.updated_at,
        status="ready" if row.status in {"fresh", "stale"} else "stale",
    )


def sync_episodic_memory_recall_document(db: Session, *, row: EpisodicMemoryEntry) -> MemoryRecallDocument:
    content = load_json(row.content_json)
    memory_type = content.get("memory_type") if isinstance(content, dict) else None
    return _upsert_recall_document(
        db,
        household_id=row.household_id,
        layer="L2",
        source_kind="episodic_memory_entry",
        source_id=row.id,
        subject_member_id=row.subject_member_id,
        visibility=row.visibility,
        group_hint="recent_events",
        search_text=build_memory_card_search_text(
            memory_type=memory_type if isinstance(memory_type, str) and memory_type else "event",
            title=row.title,
            summary=row.summary,
            normalized_text=None,
            content_json=row.content_json,
        ),
        importance=row.importance,
        confidence=row.confidence,
        occurred_at=row.occurred_at,
        updated_at=row.updated_at,
        status="ready" if row.status == "active" else "stale",
    )


def sync_memory_card_recall_document(db: Session, *, row: MemoryCard) -> MemoryRecallDocument:
    status = "ready" if row.status == "active" else "stale"
    if row.created_by == "plugin" and row.memory_type == "observation" and row.source_raw_record_id:
        status = "stale"
    return _upsert_recall_document(
        db,
        household_id=row.household_id,
        layer="L3",
        source_kind="memory_card",
        source_id=row.id,
        subject_member_id=row.subject_member_id,
        visibility=row.visibility,
        group_hint=derive_memory_group(row.memory_type),
        search_text=row.search_text
        or build_memory_card_search_text(
            memory_type=row.memory_type,
            title=row.title,
            summary=row.summary,
            normalized_text=row.normalized_text,
            content_json=row.content_json,
        ),
        importance=row.importance,
        confidence=row.confidence,
        occurred_at=row.last_observed_at or row.effective_at or row.updated_at,
        updated_at=row.updated_at,
        status=status,
    )


def sync_knowledge_document_recall_document(db: Session, *, row: KnowledgeDocument) -> MemoryRecallDocument:
    return _upsert_recall_document(
        db,
        household_id=row.household_id,
        layer="L4",
        source_kind="knowledge_document",
        source_id=row.id,
        subject_member_id=None,
        visibility=row.visibility,
        group_hint=EXTERNAL_KNOWLEDGE_GROUP,
        search_text=build_memory_card_search_text(
            memory_type="knowledge",
            title=row.title,
            summary=row.summary,
            normalized_text=row.body_text,
            content={"source_kind": row.source_kind},
        ),
        importance=3,
        confidence=0.85,
        occurred_at=row.updated_at,
        updated_at=row.updated_at,
        status="ready" if row.status == "active" else "stale",
    )


def _upsert_recall_document(
    db: Session,
    *,
    household_id: str,
    layer: str,
    source_kind: str,
    source_id: str,
    subject_member_id: str | None,
    visibility: str,
    group_hint: str,
    search_text: str,
    importance: int,
    confidence: float,
    occurred_at: str | None,
    updated_at: str,
    status: str,
) -> MemoryRecallDocument:
    row = get_memory_recall_document_by_source(
        db,
        household_id=household_id,
        layer=layer,
        source_kind=source_kind,
        source_id=source_id,
    )
    if row is None:
        row = MemoryRecallDocument(
            id=new_uuid(),
            household_id=household_id,
            layer=layer,
            source_kind=source_kind,
            source_id=source_id,
            subject_member_id=subject_member_id,
            visibility=visibility,
            group_hint=group_hint,
            search_text=search_text or "",
            importance=importance,
            confidence=confidence,
            occurred_at=occurred_at,
            updated_at=updated_at,
            status=status,
        )
        add_memory_recall_document(db, row)
    else:
        row.subject_member_id = subject_member_id
        row.visibility = visibility
        row.group_hint = group_hint
        row.search_text = search_text or ""
        row.importance = importance
        row.confidence = confidence
        row.occurred_at = occurred_at
        row.updated_at = updated_at
        row.status = status
        db.add(row)
    db.flush()
    refresh_memory_recall_document_projection(
        db,
        recall_document_id=row.id,
        search_text=search_text or "",
        embedding_literal=to_vector_literal(build_text_embedding(search_text)),
    )
    db.flush()
    return row


def _build_session_summary_search_text(row: ConversationSessionSummary) -> str:
    open_topics = load_json(row.open_topics_json)
    recent_confirmations = load_json(row.recent_confirmations_json)
    parts = [row.summary]
    if isinstance(open_topics, list):
        parts.extend(str(item).strip() for item in open_topics if str(item).strip())
    if isinstance(recent_confirmations, list):
        parts.extend(str(item).strip() for item in recent_confirmations if str(item).strip())
    return " ".join(part for part in parts if part)


def build_memory_recall_bundle(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None,
    query: str | None,
    session_id: str | None = None,
    group_limit: int = 3,
    limit: int = 12,
) -> MemoryRecallBundleRead:
    requester_member_id = _resolve_requester_member_id(actor, requester_member_id)
    requester_role = _load_member_role(db, requester_member_id)
    children_ids = _load_children_ids(db, requester_member_id)
    allow_scopes, deny_scopes = _load_memory_permission_scopes(db, requester_member_id, requester_role)
    try:
        hits, degrade_reasons = _query_recall_documents_impl(
            db,
            household_id=household_id,
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
            query=query,
            session_id=session_id,
            limit=limit,
        )
    except Exception:
        return MemoryRecallBundleRead(degraded=True, degrade_reasons=["memory_recall_document_query_failed"])

    grouped = _group_hits(hits, group_limit=group_limit)
    return MemoryRecallBundleRead(
        session_summary=grouped[SESSION_SUMMARY_GROUP],
        stable_facts=grouped["stable_facts"],
        recent_events=grouped["recent_events"],
        external_knowledge=grouped[EXTERNAL_KNOWLEDGE_GROUP],
        degraded=bool(degrade_reasons),
        degrade_reasons=degrade_reasons,
    )


def _resolve_requester_member_id(actor: ActorContext, requested_member_id: str | None) -> str | None:
    if actor.role == "admin":
        return requested_member_id
    if actor.account_type == "system":
        return requested_member_id or actor.member_id
    if actor.member_id is None:
        return None
    if requested_member_id is not None and requested_member_id != actor.member_id:
        return actor.member_id
    return requested_member_id or actor.member_id


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


def _load_memory_permission_scopes(
    db: Session,
    requester_member_id: str | None,
    requester_role: str,
) -> tuple[set[str], set[str]]:
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


def _query_recall_documents_impl(
    db: Session,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
    query: str | None,
    session_id: str | None,
    limit: int,
) -> tuple[list[MemoryRecallHit], list[str]]:
    filters = _build_recall_filters(
        actor=actor,
        household_id=household_id,
        requester_member_id=requester_member_id,
        requester_role=requester_role,
        children_ids=children_ids,
        allow_scopes=allow_scopes,
        deny_scopes=deny_scopes,
        session_id=session_id,
    )
    candidate_limit = max(limit * 4, 16)
    query_terms = extract_search_terms(query)
    candidate_map: dict[str, _RecallCandidate] = {}
    degrade_reasons: list[str] = []

    if query:
        ts_query_text = build_tsquery_text(query)
        if ts_query_text:
            for recall_document_id, fts_score in _query_fts_candidates(
                db,
                filters=filters,
                ts_query_text=ts_query_text,
                limit=candidate_limit,
            ):
                candidate = candidate_map.setdefault(
                    recall_document_id,
                    _RecallCandidate(recall_document_id=recall_document_id, matched_terms=query_terms),
                )
                candidate.fts_score = float(fts_score or 0.0)
        degrade_reason = _query_vector_candidates(
            db,
            filters=filters,
            query=query,
            limit=candidate_limit,
            candidate_map=candidate_map,
            matched_terms=query_terms,
        )
        if degrade_reason is not None:
            degrade_reasons.append(degrade_reason)
        _append_session_summary_candidate(
            db,
            filters=filters,
            session_id=session_id,
            candidate_map=candidate_map,
        )
    else:
        for row in _list_visible_recall_documents(db, filters=filters, limit=candidate_limit):
            candidate_map[row.id] = _RecallCandidate(recall_document_id=row.id)

    if not candidate_map:
        return ([], degrade_reasons)
    hits = _rerank_hits(
        source_snapshots=_load_source_snapshots(db, recall_document_ids=list(candidate_map.keys())),
        candidates=candidate_map,
        requester_member_id=requester_member_id,
    )
    return (hits[:limit], degrade_reasons)


def _append_session_summary_candidate(
    db: Session,
    *,
    filters: list,
    session_id: str | None,
    candidate_map: dict[str, _RecallCandidate],
) -> None:
    if session_id is None:
        return
    stmt = (
        select(MemoryRecallDocument.id)
        .where(
            *filters,
            MemoryRecallDocument.layer == "L1",
            exists(
                select(literal(1)).where(
                    ConversationSessionSummary.id == MemoryRecallDocument.source_id,
                    ConversationSessionSummary.session_id == session_id,
                )
            ),
        )
        .order_by(MemoryRecallDocument.updated_at.desc(), MemoryRecallDocument.id.desc())
        .limit(1)
    )
    recall_document_id = db.scalar(stmt)
    if recall_document_id is None or recall_document_id in candidate_map:
        return
    candidate_map[recall_document_id] = _RecallCandidate(recall_document_id=recall_document_id)


def _build_recall_filters(
    *,
    actor: ActorContext,
    household_id: str,
    requester_member_id: str | None,
    requester_role: str,
    children_ids: set[str],
    allow_scopes: set[str],
    deny_scopes: set[str],
    session_id: str | None,
) -> list:
    filters = [
        MemoryRecallDocument.household_id == household_id,
        MemoryRecallDocument.status == "ready",
        _build_recall_visibility_predicate(
            actor=actor,
            requester_member_id=requester_member_id,
            requester_role=requester_role,
            children_ids=children_ids,
            allow_scopes=allow_scopes,
            deny_scopes=deny_scopes,
        ),
    ]
    if session_id is None:
        filters.append(MemoryRecallDocument.layer != "L1")
    else:
        filters.append(
            or_(
                MemoryRecallDocument.layer != "L1",
                exists(
                    select(literal(1)).where(
                        ConversationSessionSummary.id == MemoryRecallDocument.source_id,
                        ConversationSessionSummary.session_id == session_id,
                    )
                ),
            )
        )
    return filters


def _build_recall_visibility_predicate(
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
        is_self = MemoryRecallDocument.subject_member_id == requester_member_id
        is_related_member = exists(
            select(literal(1)).where(
                MemoryRecallDocument.layer == "L3",
                MemoryCardMember.memory_id == MemoryRecallDocument.source_id,
                MemoryCardMember.member_id == requester_member_id,
            )
        )
    is_child = MemoryRecallDocument.subject_member_id.in_(tuple(children_ids)) if children_ids else false()
    clauses = []
    if "public" in allow_scopes and "public" not in deny_scopes:
        clauses.append(MemoryRecallDocument.visibility == "public")
    if "self" in allow_scopes and "self" not in deny_scopes:
        clauses.append(and_(MemoryRecallDocument.visibility.in_(["family", "private"]), or_(is_self, is_related_member)))
        clauses.append(and_(MemoryRecallDocument.visibility == "sensitive", is_self))
    if "children" in allow_scopes and "children" not in deny_scopes:
        clauses.append(and_(MemoryRecallDocument.visibility.in_(["family", "private"]), is_child))
        if requester_role in {"adult", "elder", "admin"}:
            clauses.append(and_(MemoryRecallDocument.visibility == "sensitive", is_child))
    if "family" in allow_scopes and "family" not in deny_scopes:
        clauses.append(and_(MemoryRecallDocument.visibility == "family", not_(or_(is_self, is_related_member, is_child))))
    return or_(*clauses) if clauses else false()


def _query_fts_candidates(db: Session, *, filters: list, ts_query_text: str, limit: int) -> list[tuple[str, float]]:
    ts_query = func.to_tsquery("simple", ts_query_text)
    rank_expr = func.ts_rank_cd(MemoryRecallDocument.search_tsv, ts_query).label("fts_score")
    stmt = (
        select(MemoryRecallDocument.id, rank_expr)
        .where(*filters)
        .where(MemoryRecallDocument.search_tsv.is_not(None))
        .where(MemoryRecallDocument.search_tsv.op("@@")(ts_query))
        .order_by(rank_expr.desc(), MemoryRecallDocument.updated_at.desc(), MemoryRecallDocument.id.desc())
        .limit(limit)
    )
    return [(str(row.id), float(row.fts_score or 0.0)) for row in db.execute(stmt).all()]


def _query_vector_candidates(
    db: Session,
    *,
    filters: list,
    query: str,
    limit: int,
    candidate_map: dict[str, _RecallCandidate],
    matched_terms: list[str],
) -> str | None:
    if not is_memory_recall_pgvector_enabled(db):
        return "pgvector_unavailable"
    query_embedding_literal = to_vector_literal(build_text_embedding(query))
    if query_embedding_literal is None:
        return "embedding_unavailable"
    distance_expr = MemoryRecallDocument.embedding.op("<->")(
        text(f"CAST(:query_embedding AS vector({MEMORY_RECALL_EMBEDDING_DIMENSION}))")
    ).label("vector_distance")
    stmt = (
        select(MemoryRecallDocument.id, distance_expr)
        .where(*filters)
        .where(MemoryRecallDocument.embedding.is_not(None))
        .order_by(distance_expr.asc(), MemoryRecallDocument.updated_at.desc(), MemoryRecallDocument.id.desc())
        .limit(limit)
    )
    try:
        rows = db.execute(stmt, {"query_embedding": query_embedding_literal}).all()
    except Exception:
        return "vector_query_failed"
    for row in rows:
        vector_score = round(1.0 / (1.0 + max(float(row.vector_distance or 0.0), 0.0)), 6)
        candidate = candidate_map.setdefault(
            str(row.id),
            _RecallCandidate(recall_document_id=str(row.id), matched_terms=matched_terms),
        )
        candidate.vector_score = vector_score
    return None


def _list_visible_recall_documents(db: Session, *, filters: list, limit: int) -> list[MemoryRecallDocument]:
    stmt = (
        select(MemoryRecallDocument)
        .where(*filters)
        .order_by(
            MemoryRecallDocument.importance.desc(),
            MemoryRecallDocument.confidence.desc(),
            MemoryRecallDocument.updated_at.desc(),
            MemoryRecallDocument.id.desc(),
        )
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _load_source_snapshots(db: Session, *, recall_document_ids: list[str]) -> dict[str, _RecallSourceSnapshot]:
    recall_documents = list(list_memory_recall_documents_by_ids(db, recall_document_ids=recall_document_ids))
    l1_ids = [row.source_id for row in recall_documents if row.layer == "L1"]
    l2_ids = [row.source_id for row in recall_documents if row.layer == "L2"]
    l3_ids = [row.source_id for row in recall_documents if row.layer == "L3"]
    l4_ids = [row.source_id for row in recall_documents if row.layer == "L4"]
    l1_rows = {row.id: row for row in db.scalars(select(ConversationSessionSummary).where(ConversationSessionSummary.id.in_(l1_ids))).all()} if l1_ids else {}
    l2_rows = {row.id: row for row in list_episodic_memory_entries_by_ids(db, entry_ids=l2_ids)}
    l3_rows = {row.id: row for row in _build_card_reads(db, list(list_memory_cards_by_ids(db, memory_ids=l3_ids)))}
    l4_rows = {row.id: row for row in list_knowledge_documents_by_ids(db, document_ids=l4_ids)}
    snapshots: dict[str, _RecallSourceSnapshot] = {}
    for recall_document in recall_documents:
        if recall_document.layer == "L1" and recall_document.source_id in l1_rows:
            row = l1_rows[recall_document.source_id]
            snapshots[recall_document.id] = _RecallSourceSnapshot(
                layer="L1", group_name=SESSION_SUMMARY_GROUP, memory_id=row.id, source_id=row.id,
                source_kind="conversation_session_summary", title="当前会话摘要", summary=row.summary,
                memory_type="session_summary", visibility="private", subject_member_id=row.requester_member_id,
                occurred_at=row.generated_at, updated_at=row.updated_at,
                importance=recall_document.importance, confidence=recall_document.confidence,
            )
        elif recall_document.layer == "L2" and recall_document.source_id in l2_rows:
            row = l2_rows[recall_document.source_id]
            content = load_json(row.content_json)
            memory_type = content.get("memory_type") if isinstance(content, dict) else "event"
            snapshots[recall_document.id] = _RecallSourceSnapshot(
                layer="L2", group_name="recent_events", memory_id=row.id, source_id=row.source_id,
                source_kind=row.source_kind, title=row.title, summary=row.summary,
                memory_type=memory_type if isinstance(memory_type, str) else "event", visibility=row.visibility,
                subject_member_id=row.subject_member_id, occurred_at=row.occurred_at, updated_at=row.updated_at,
                importance=row.importance, confidence=row.confidence,
            )
        elif recall_document.layer == "L3" and recall_document.source_id in l3_rows:
            row = l3_rows[recall_document.source_id]
            snapshots[recall_document.id] = _RecallSourceSnapshot(
                layer="L3", group_name=derive_memory_group(row.memory_type), memory_id=row.id,
                source_id=row.source_event_id or row.source_raw_record_id or row.id, source_kind="memory_card",
                title=row.title, summary=row.summary, memory_type=row.memory_type, visibility=row.visibility,
                subject_member_id=row.subject_member_id,
                occurred_at=row.last_observed_at or row.effective_at or row.updated_at, updated_at=row.updated_at,
                importance=row.importance, confidence=row.confidence,
                related_member_ids={item.member_id for item in row.related_members},
            )
        elif recall_document.layer == "L4" and recall_document.source_id in l4_rows:
            row = l4_rows[recall_document.source_id]
            snapshots[recall_document.id] = _RecallSourceSnapshot(
                layer="L4", group_name=EXTERNAL_KNOWLEDGE_GROUP, memory_id=row.id, source_id=row.source_ref,
                source_kind=row.source_kind, title=row.title, summary=row.summary, memory_type="knowledge_document",
                visibility=row.visibility, subject_member_id=None, occurred_at=row.updated_at, updated_at=row.updated_at,
                importance=recall_document.importance, confidence=recall_document.confidence,
            )
    return snapshots


def _rerank_hits(
    *,
    source_snapshots: dict[str, _RecallSourceSnapshot],
    candidates: dict[str, _RecallCandidate],
    requester_member_id: str | None,
) -> list[MemoryRecallHit]:
    hits: list[MemoryRecallHit] = []
    for recall_document_id, snapshot in source_snapshots.items():
        candidate = candidates.get(recall_document_id)
        if candidate is None:
            continue
        importance_score = round(snapshot.importance / 5.0, 6)
        confidence_score = round(snapshot.confidence, 6)
        recency_score = compute_recency_score(snapshot.occurred_at, snapshot.updated_at)
        member_match_score = 1.0 if requester_member_id and snapshot.subject_member_id == requester_member_id else (0.8 if requester_member_id in snapshot.related_member_ids else 0.0)
        visibility_score = 1.0 if requester_member_id and snapshot.subject_member_id == requester_member_id and snapshot.visibility in {"private", "sensitive"} else (0.8 if snapshot.visibility == "family" else (0.9 if snapshot.visibility == "private" else (0.95 if snapshot.visibility == "sensitive" else 0.6)))
        fts_score = round(candidate.fts_score or 0.0, 6)
        vector_score = round(candidate.vector_score or 0.0, 6)
        if snapshot.group_name == "recent_events":
            score = fts_score * 0.28 + vector_score * 0.24 + recency_score * 0.22 + importance_score * 0.12 + confidence_score * 0.08 + member_match_score * 0.04 + visibility_score * 0.02
        elif snapshot.group_name == SESSION_SUMMARY_GROUP:
            score = fts_score * 0.44 + vector_score * 0.28 + recency_score * 0.18 + visibility_score * 0.10
        elif snapshot.group_name == EXTERNAL_KNOWLEDGE_GROUP:
            score = fts_score * 0.36 + vector_score * 0.30 + importance_score * 0.12 + confidence_score * 0.10 + recency_score * 0.05 + visibility_score * 0.05 + member_match_score * 0.02
        else:
            score = fts_score * 0.34 + vector_score * 0.28 + importance_score * 0.16 + confidence_score * 0.12 + member_match_score * 0.05 + visibility_score * 0.03 + recency_score * 0.02
        hits.append(
            MemoryRecallHit(
                memory_id=snapshot.memory_id, source_id=snapshot.source_id, source_kind=snapshot.source_kind,
                group_name=snapshot.group_name, layer=snapshot.layer, title=snapshot.title, summary=snapshot.summary,
                memory_type=snapshot.memory_type, visibility=snapshot.visibility, subject_member_id=snapshot.subject_member_id,
                updated_at=snapshot.updated_at, occurred_at=snapshot.occurred_at, score=round(max(score, 0.000001), 6), rank=1,
                fts_score=fts_score if fts_score > 0 else None, vector_score=vector_score if vector_score > 0 else None,
                reason={"fts_score": fts_score, "vector_score": vector_score, "importance_score": importance_score, "confidence_score": confidence_score, "recency_score": recency_score, "member_match_score": member_match_score, "visibility_score": visibility_score},
                matched_terms=candidate.matched_terms,
            )
        )
    hits.sort(key=lambda item: (item.score, item.updated_at or "", item.memory_id), reverse=True)
    return hits


def _group_hits(hits: list[MemoryRecallHit], *, group_limit: int) -> dict[str, list[MemoryRecallHit]]:
    grouped = {SESSION_SUMMARY_GROUP: [], "stable_facts": [], "recent_events": [], EXTERNAL_KNOWLEDGE_GROUP: []}
    for group_name in grouped:
        ranked = [item for item in hits if item.group_name == group_name]
        ranked.sort(key=lambda item: (item.score, item.updated_at or "", item.memory_id), reverse=True)
        for index, item in enumerate(ranked[:group_limit], start=1):
            item.rank = index
            grouped[group_name].append(item)
    return grouped
