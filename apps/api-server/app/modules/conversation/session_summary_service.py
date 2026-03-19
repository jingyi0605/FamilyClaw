from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.api.dependencies import ActorContext
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.conversation import repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalItem, ConversationSession, ConversationSessionSummary
from app.modules.conversation.schemas import ConversationSessionSummaryRead
from app.modules.memory.recall_projection import build_text_embedding, compute_recency_score, extract_search_terms
from app.modules.memory.schemas import MemoryRecallHit

logger = logging.getLogger(__name__)

SESSION_SUMMARY_MESSAGE_THRESHOLD = 4
SESSION_SUMMARY_MAX_OPEN_TOPICS = 3
SESSION_SUMMARY_MAX_CONFIRMATIONS = 3
SESSION_SUMMARY_ACTIVE_STATUSES = {"fresh", "stale"}
SESSION_SUMMARY_EMBEDDING_WEIGHT = 0.28
SESSION_SUMMARY_KEYWORD_WEIGHT = 0.44
SESSION_SUMMARY_RECENCY_WEIGHT = 0.18
SESSION_SUMMARY_VISIBILITY_WEIGHT = 0.10


def get_session_summary_read(
    db: Session,
    *,
    session_id: str,
) -> ConversationSessionSummaryRead | None:
    row = repository.get_session_summary(db, session_id=session_id)
    return None if row is None else _to_session_summary_read(row)


def maybe_refresh_session_summary(
    db: Session,
    *,
    session_id: str,
    trigger_reason: str,
    force: bool = False,
) -> ConversationSessionSummaryRead | None:
    session = repository.get_session(db, session_id)
    if session is None:
        return None

    messages = list(repository.list_messages(db, session_id=session_id))
    if not messages:
        return None

    row = repository.get_session_summary(db, session_id=session_id)
    should_refresh, stale_reason = _should_refresh_summary(
        session=session,
        row=row,
        messages=messages,
        force=force,
    )
    if not should_refresh:
        if row is not None and row.status == "failed":
            row.status = "stale"
            row.updated_at = utc_now_iso()
            db.flush()
        return None if row is None else _to_session_summary_read(row)

    now = utc_now_iso()
    if row is None:
        row = ConversationSessionSummary(
            id=new_uuid(),
            session_id=session.id,
            household_id=session.household_id,
            requester_member_id=session.requester_member_id,
            summary="",
            open_topics_json="[]",
            recent_confirmations_json="[]",
            covered_message_seq=0,
            status="rebuilding",
            generated_at=now,
            updated_at=now,
        )
        repository.add_session_summary(db, row)
    else:
        row.status = "rebuilding"
        row.updated_at = now
    db.flush()

    try:
        summary_text, open_topics, recent_confirmations = _build_session_summary_payload(
            session=session,
            messages=messages,
            completed_items=_list_completed_proposal_items(db, session_id=session.id),
        )
        row.summary = summary_text
        row.open_topics_json = dump_json(open_topics) or "[]"
        row.recent_confirmations_json = dump_json(recent_confirmations) or "[]"
        row.covered_message_seq = max((item.seq for item in messages), default=0)
        row.status = "fresh"
        row.generated_at = now
        row.updated_at = now
        db.flush()
        from app.modules.memory.recall_document_service import sync_session_summary_recall_document
        from app.modules.memory.service import upsert_episodic_memory_from_session_summary

        sync_session_summary_recall_document(db, row=row)
        upsert_episodic_memory_from_session_summary(
            db,
            summary_id=row.id,
            household_id=row.household_id,
            requester_member_id=row.requester_member_id,
            summary=row.summary,
            open_topics=open_topics,
            recent_confirmations=recent_confirmations,
            generated_at=row.generated_at,
            updated_at=row.updated_at,
        )
        logger.info(
            "会话摘要已刷新 session_id=%s trigger_reason=%s stale_reason=%s covered_message_seq=%s",
            session.id,
            trigger_reason,
            stale_reason,
            row.covered_message_seq,
        )
        return _to_session_summary_read(row)
    except Exception:
        logger.exception(
            "会话摘要刷新失败 session_id=%s trigger_reason=%s stale_reason=%s",
            session.id,
            trigger_reason,
            stale_reason,
        )
        row.status = "failed"
        row.updated_at = utc_now_iso()
        db.flush()
        return _to_session_summary_read(row)


def query_session_summary_hits(
    db: Session,
    *,
    session_id: str,
    actor: ActorContext,
    requester_member_id: str | None,
    query: str | None,
) -> list[MemoryRecallHit]:
    session = repository.get_session(db, session_id)
    row = repository.get_session_summary(db, session_id=session_id)
    if session is None or row is None:
        return []
    if row.status not in SESSION_SUMMARY_ACTIVE_STATUSES:
        return []
    if not _can_actor_read_session_summary(session=session, actor=actor):
        return []

    search_text = _build_session_summary_search_text(row)
    keyword_score, matched_terms = _compute_keyword_score(query=query, search_text=search_text)
    vector_score = _compute_vector_score(query=query, search_text=search_text)
    recency_score = compute_recency_score(row.updated_at, row.generated_at)
    visibility_score = 1.0 if requester_member_id and requester_member_id == session.requester_member_id else 0.8
    score = round(
        keyword_score * SESSION_SUMMARY_KEYWORD_WEIGHT
        + vector_score * SESSION_SUMMARY_EMBEDDING_WEIGHT
        + recency_score * SESSION_SUMMARY_RECENCY_WEIGHT
        + visibility_score * SESSION_SUMMARY_VISIBILITY_WEIGHT,
        6,
    )
    if query and score <= 0:
        return []

    return [
        MemoryRecallHit(
            memory_id=row.id,
            source_id=row.id,
            source_kind="conversation_session_summary",
            group_name="session_summary",
            layer="L1",
            title="当前会话摘要",
            summary=row.summary,
            memory_type="session_summary",
            visibility="private",
            subject_member_id=session.requester_member_id,
            updated_at=row.updated_at,
            occurred_at=row.generated_at,
            score=max(score, 0.000001),
            rank=1,
            fts_score=keyword_score if keyword_score > 0 else None,
            vector_score=vector_score if vector_score > 0 else None,
            reason={
                "keyword_score": keyword_score,
                "vector_score": vector_score,
                "recency_score": recency_score,
                "visibility_score": visibility_score,
                "status": row.status,
            },
            matched_terms=matched_terms,
        )
    ]


def _should_refresh_summary(
    *,
    session: ConversationSession,
    row: ConversationSessionSummary | None,
    messages: list[ConversationMessage],
    force: bool,
) -> tuple[bool, str]:
    if force:
        return True, "force"

    current_max_seq = max((item.seq for item in messages), default=0)
    if row is None:
        if current_max_seq >= SESSION_SUMMARY_MESSAGE_THRESHOLD:
            return True, "initial_threshold_reached"
        return False, "initial_threshold_not_reached"

    uncovered_count = max(0, current_max_seq - row.covered_message_seq)
    if row.status == "failed":
        return True, "retry_after_failed"
    if uncovered_count >= SESSION_SUMMARY_MESSAGE_THRESHOLD:
        return True, "message_threshold_reached"
    if session.status != "active" and uncovered_count > 0:
        return True, "session_closed_with_new_messages"
    return False, "below_threshold"


def _build_session_summary_payload(
    *,
    session: ConversationSession,
    messages: list[ConversationMessage],
    completed_items: list[ConversationProposalItem],
) -> tuple[str, list[str], list[str]]:
    recent_user_messages = [item for item in messages if item.role == "user" and item.content.strip()][-4:]
    recent_assistant_messages = [item for item in messages if item.role == "assistant" and item.content.strip()][-3:]
    open_topics = _extract_open_topics(recent_user_messages)
    recent_confirmations = _extract_recent_confirmations(
        completed_items=completed_items,
        assistant_messages=recent_assistant_messages,
    )

    topic_summary = "；".join(open_topics) if open_topics else "本轮主要围绕同一主题继续推进"
    recent_progress = "；".join(
        _trim_text(item.content, 60)
        for item in recent_assistant_messages[-2:]
    ) or "最近还没有稳定的助手回复摘要"
    confirmation_summary = "；".join(recent_confirmations) if recent_confirmations else "最近没有新的确认事项"
    summary_text = (
        f"会话《{session.title}》最近主要在聊：{topic_summary}。"
        f"最近进展：{recent_progress}。"
        f"最近确认事项：{confirmation_summary}。"
    )
    return summary_text, open_topics, recent_confirmations


def _extract_open_topics(messages: list[ConversationMessage]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for item in reversed(messages):
        candidate = _trim_text(item.content, 80)
        if not candidate:
            continue
        if (
            "？" in candidate
            or "?" in candidate
            or any(keyword in candidate for keyword in ("下一步", "之后", "计划", "待办", "安排", "还要"))
        ):
            if candidate not in seen:
                seen.add(candidate)
                topics.append(candidate)
        if len(topics) >= SESSION_SUMMARY_MAX_OPEN_TOPICS:
            break
    if topics:
        return list(reversed(topics))

    fallback_topics = []
    for item in messages[-SESSION_SUMMARY_MAX_OPEN_TOPICS:]:
        candidate = _trim_text(item.content, 60)
        if not candidate or candidate in fallback_topics:
            continue
        fallback_topics.append(candidate)
    return fallback_topics


def _extract_recent_confirmations(
    *,
    completed_items: list[ConversationProposalItem],
    assistant_messages: list[ConversationMessage],
) -> list[str]:
    confirmations: list[str] = []
    for item in completed_items[-SESSION_SUMMARY_MAX_CONFIRMATIONS:]:
        candidate = _trim_text(item.summary or item.title, 80)
        if candidate and candidate not in confirmations:
            confirmations.append(candidate)
    if confirmations:
        return confirmations

    for item in assistant_messages:
        candidate = _trim_text(item.content, 80)
        if not candidate:
            continue
        if any(keyword in candidate for keyword in ("已经", "已为你", "我会", "好的", "可以")):
            confirmations.append(candidate)
        if len(confirmations) >= SESSION_SUMMARY_MAX_CONFIRMATIONS:
            break
    return confirmations


def _list_completed_proposal_items(db: Session, *, session_id: str) -> list[ConversationProposalItem]:
    completed_items: list[ConversationProposalItem] = []
    for batch in repository.list_proposal_batches(db, session_id=session_id):
        completed_items.extend(
            item
            for item in repository.list_proposal_items(db, batch_id=batch.id)
            if item.status == "completed"
        )
    completed_items.sort(key=lambda item: (item.updated_at, item.created_at, item.id))
    return completed_items


def _build_session_summary_search_text(row: ConversationSessionSummary) -> str:
    open_topics = load_json(row.open_topics_json)
    recent_confirmations = load_json(row.recent_confirmations_json)
    parts = [row.summary]
    if isinstance(open_topics, list):
        parts.extend(str(item).strip() for item in open_topics if str(item).strip())
    if isinstance(recent_confirmations, list):
        parts.extend(str(item).strip() for item in recent_confirmations if str(item).strip())
    return " ".join(part for part in parts if part)


def _compute_keyword_score(*, query: str | None, search_text: str) -> tuple[float, list[str]]:
    query_terms = extract_search_terms(query)
    if not query_terms:
        return (0.6 if search_text.strip() else 0.0), []
    search_terms = Counter(extract_search_terms(search_text))
    if not search_terms:
        return 0.0, []
    matched_terms = [term for term in query_terms if term in search_terms]
    if not matched_terms:
        return 0.0, []
    unique_query_term_count = max(1, len(set(query_terms)))
    return round(len(set(matched_terms)) / unique_query_term_count, 6), matched_terms


def _compute_vector_score(*, query: str | None, search_text: str) -> float:
    query_embedding = build_text_embedding(query)
    summary_embedding = build_text_embedding(search_text)
    if not query_embedding or not summary_embedding:
        return 0.0
    dot_product = sum(left * right for left, right in zip(query_embedding, summary_embedding, strict=False))
    return round(max(dot_product, 0.0), 6)


def _can_actor_read_session_summary(*, session: ConversationSession, actor: ActorContext) -> bool:
    if actor.account_type == "system" or actor.role == "admin":
        return True
    if actor.household_id != session.household_id:
        return False
    if actor.member_id is None:
        return False
    if session.requester_member_id is None:
        return True
    return session.requester_member_id == actor.member_id


def _to_session_summary_read(row: ConversationSessionSummary) -> ConversationSessionSummaryRead:
    open_topics = load_json(row.open_topics_json)
    recent_confirmations = load_json(row.recent_confirmations_json)
    return ConversationSessionSummaryRead(
        id=row.id,
        session_id=row.session_id,
        household_id=row.household_id,
        requester_member_id=row.requester_member_id,
        summary=row.summary,
        open_topics=[str(item) for item in open_topics] if isinstance(open_topics, list) else [],
        recent_confirmations=[str(item) for item in recent_confirmations] if isinstance(recent_confirmations, list) else [],
        covered_message_seq=row.covered_message_seq,
        status=row.status,
        generated_at=row.generated_at,
        updated_at=row.updated_at,
    )


def _trim_text(value: str | None, max_length: int) -> str:
    text = " ".join((value or "").strip().split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"
