from __future__ import annotations

from typing import Any

from app.api.dependencies import ActorContext
from app.db.utils import utc_now_iso
from app.modules.context.service import get_context_overview
from app.modules.memory.query_service import get_memory_hot_summary, query_memory_cards
from app.modules.memory.schemas import (
    MemoryContextBundleRead,
    MemoryContextLiveSummary,
    MemoryQueryRequest,
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
        masked_sections=masked_sections,
        degraded=overview.degraded,
    )
