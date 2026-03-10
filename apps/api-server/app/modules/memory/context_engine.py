from __future__ import annotations

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.context.service import get_context_overview
from app.modules.memory.query_service import get_memory_hot_summary, query_memory_cards
from app.modules.memory.schemas import (
    MemoryContextBundleRead,
    MemoryContextLiveSummary,
    MemoryQueryRequest,
)


def build_memory_context_bundle(
    db,
    *,
    household_id: str,
    actor: ActorContext,
    requester_member_id: str | None = None,
    question: str | None = None,
    capability: str = "family_qa",
) -> MemoryContextBundleRead:
    overview = get_context_overview(db, household_id)
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
            limit=8,
        ),
        actor=actor,
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
            active_member_name=overview.active_member.name if overview.active_member is not None else None,
            active_member_id=overview.active_member.member_id if overview.active_member is not None else None,
            pending_reminders=0,
            running_scenes=0,
            visible_member_count=len(overview.member_states),
            room_count=len(overview.room_occupancy),
            degraded=overview.degraded,
        ),
        hot_summary=hot_summary,
        query_result=query_result,
        masked_sections=masked_sections,
        degraded=overview.degraded,
    )
