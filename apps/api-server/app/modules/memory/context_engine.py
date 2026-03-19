from __future__ import annotations

from typing import Any

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.conversation.session_summary_service import query_session_summary_hits
from app.modules.context.service import get_context_overview
from app.modules.memory.recall_document_service import build_memory_recall_bundle as build_unified_memory_recall_bundle
from app.modules.memory.query_service import get_memory_hot_summary, query_memory_cards
from app.modules.memory.schemas import (
    MemoryContextBundleRead,
    MemoryContextLiveSummary,
    MemoryQueryRequest,
    MemoryRecallBundleRead,
)
from app.modules.member import service as member_service
from app.modules.plugin.slot_service import invoke_slot_plugin


def build_memory_context_bundle(
    db,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None = None,
    question: str | None = None,
    capability: str = "family_qa",
    session_id: str | None = None,
) -> MemoryContextBundleRead:
    return invoke_slot_plugin(
        db,
        household_id=household_id,
        slot_name="context_engine",
        operation="build_context_bundle",
        payload={
            "household_id": household_id,
            "requester_member_id": requester_member_id,
            "question": question,
            "capability": capability,
            "session_id": session_id,
            "actor": _build_actor_snapshot(actor),
        },
        output_model=MemoryContextBundleRead,
        fallback=lambda: _build_default_memory_context_bundle(
            db,
            household_id=household_id,
            actor=actor,
            requester_member_id=requester_member_id,
            question=question,
            capability=capability,
            session_id=session_id,
        ),
    )


def _build_actor_snapshot(actor: ActorContext) -> dict[str, Any]:
    return {
        "role": actor.role,
        "actor_type": actor.actor_type,
        "actor_id": actor.actor_id,
        "account_type": actor.account_type,
        "account_id": actor.account_id,
        "member_id": actor.member_id,
        "member_role": actor.member_role,
    }


def _build_default_memory_context_bundle(
    db,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None = None,
    question: str | None = None,
    capability: str = "family_qa",
    session_id: str | None = None,
) -> MemoryContextBundleRead:
    overview = get_context_overview(db, household_id)
    active_member_name = (
        member_service.get_member_display_name(db, member_id=overview.active_member.member_id)
        if overview.active_member is not None
        else None
    ) or (overview.active_member.name if overview.active_member is not None else None)
    hot_summary = get_memory_hot_summary(
        db,
        household_id=household_id,
        actor=actor,
        requester_member_id=requester_member_id,
    )
    query_result = query_memory_cards(
        db,
        payload=MemoryQueryRequest(
            household_id=household_id,
            requester_member_id=requester_member_id,
            query=question,
            status="active",
            limit=8,
            group_limit=3,
        ),
        actor=actor,
    )
    recall = build_unified_memory_recall_bundle(
        db,
        household_id=household_id,
        actor=actor,
        requester_member_id=requester_member_id,
        session_id=session_id,
        query=question,
        group_limit=3,
        limit=12,
    )
    if recall.degraded and not any(
        [recall.session_summary, recall.stable_facts, recall.recent_events, recall.external_knowledge]
    ):
        recall = _build_legacy_memory_recall_bundle(
        db,
        actor=actor,
        requester_member_id=requester_member_id,
        session_id=session_id,
        question=question,
        query_result=query_result,
        )

    masked_sections: list[str] = []
    if actor.role != "admin" and query_result.total == 0:
        masked_sections.append("memory_query")

    return MemoryContextBundleRead(
        household_id=household_id,
        requester_member_id=query_result.requester_member_id,
        capability=capability,
        question=question,
        generated_at=utc_now_iso(),
        live_summary=MemoryContextLiveSummary(
            active_member_name=active_member_name,
            active_member_id=overview.active_member.member_id if overview.active_member is not None else None,
            pending_reminders=0,
            running_scenes=0,
            visible_member_count=len(overview.member_states),
            room_count=len(overview.room_occupancy),
            degraded=overview.degraded,
        ),
        hot_summary=hot_summary,
        query_result=query_result,
        recall=recall,
        masked_sections=masked_sections,
        degraded=overview.degraded or recall.degraded,
    )


def _build_legacy_memory_recall_bundle(
    db,
    *,
    actor: ActorContext,
    requester_member_id: str | None,
    session_id: str | None,
    question: str | None,
    query_result,
) -> MemoryRecallBundleRead:
    session_summary_hits = []
    if session_id:
        session_summary_hits = query_session_summary_hits(
            db,
            session_id=session_id,
            actor=actor,
            requester_member_id=requester_member_id,
            query=question,
        )
    return MemoryRecallBundleRead(
        stable_facts=list(query_result.recall.stable_facts),
        recent_events=list(query_result.recall.recent_events),
        session_summary=session_summary_hits,
        external_knowledge=list(query_result.recall.external_knowledge),
        degraded=query_result.degraded,
        degrade_reasons=list(query_result.degrade_reasons),
    )
