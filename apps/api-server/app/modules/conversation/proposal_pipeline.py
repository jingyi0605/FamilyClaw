from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.agent import repository as agent_repository
from app.modules.conversation import repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalBatch, ConversationProposalItem, ConversationSession
from app.modules.conversation.proposal_analyzers import ProposalAnalyzerFailure, ProposalAnalyzerRegistry, ProposalDraft
from app.modules.conversation.semantic_router import ProposalGateScore
from app.modules.llm_task import invoke_llm
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput


@dataclass(frozen=True)
class TurnProposalEvidence:
    message_id: str
    role: str
    content: str
    kind: str


@dataclass
class TurnProposalContext:
    session_id: str
    request_id: str
    turn_messages: list[TurnProposalEvidence]
    trusted_events: list[dict]
    conversation_history_excerpt: list[dict[str, str]]
    lane_result: dict
    main_reply_summary: str
    proposal_gate_scores: list[ProposalGateScore] = field(default_factory=list)

    @property
    def user_messages(self) -> list[TurnProposalEvidence]:
        return [item for item in self.turn_messages if item.kind == "user_message"]

    def resolve_evidence(
        self,
        evidence_message_ids: list[str],
        *,
        allowed_kinds: set[str],
        require_non_assistant: bool,
    ) -> tuple[list[str], list[str]]:
        evidence_by_id = {item.message_id: item for item in self.turn_messages}
        resolved_ids: list[str] = []
        resolved_roles: list[str] = []
        for message_id in evidence_message_ids:
            evidence = evidence_by_id.get(message_id)
            if evidence is None:
                normalized_id = _normalize_turn_message_id_alias(message_id, evidence_by_id)
                if normalized_id is not None:
                    evidence = evidence_by_id.get(normalized_id)
            if evidence is None or evidence.kind not in allowed_kinds:
                continue
            resolved_ids.append(evidence.message_id)
            resolved_roles.append(evidence.role)
        if require_non_assistant and resolved_ids and all(role == "assistant" for role in resolved_roles):
            return [], []
        return resolved_ids, resolved_roles

    def latest_user_evidence(self) -> TurnProposalEvidence | None:
        user_messages = self.user_messages
        if not user_messages:
            return None
        return user_messages[-1]


@dataclass(frozen=True)
class ProposalPipelineResult:
    batch_id: str | None
    item_ids: list[str]
    drafts: list[ProposalDraft]
    failures: list[ProposalAnalyzerFailure]
    extraction_output: ProposalBatchExtractionOutput | None

    @property
    def memory_candidate_payloads(self) -> list[dict]:
        payloads: list[dict] = []
        for draft in self.drafts:
            if draft.proposal_kind != "memory_write":
                continue
            payload = dict(draft.payload)
            payload.setdefault("title", draft.title)
            payload.setdefault("summary", draft.summary)
            payload.setdefault("confidence", draft.confidence)
            payload.setdefault("memory_type", payload.get("memory_type") or payload.get("type") or "fact")
            payloads.append(payload)
        return payloads

    @property
    def config_suggestion(self) -> dict | None:
        for draft in self.drafts:
            if draft.proposal_kind == "config_apply":
                return dict(draft.payload)
        return None

    @property
    def action_payloads(self) -> list[dict]:
        payloads: list[dict] = []
        for draft in self.drafts:
            if draft.proposal_kind == "reminder_create":
                payload = dict(draft.payload)
                payload.setdefault("action_type", "reminder_create")
                payloads.append(payload)
        return payloads


Extractor = Callable[[Session, TurnProposalContext, str], ProposalBatchExtractionOutput]


class ProposalPipeline:
    def __init__(
        self,
        *,
        registry: ProposalAnalyzerRegistry | None = None,
        extractor: Extractor | None = None,
    ) -> None:
        self.registry = registry or ProposalAnalyzerRegistry()
        self.extractor = extractor or extract_proposal_batch

    def run(
        self,
        db: Session,
        *,
        session: ConversationSession,
        request_id: str,
        turn_context: TurnProposalContext,
        persist: bool,
    ) -> ProposalPipelineResult:
        extraction_output = self.extractor(db, turn_context, session.household_id)
        drafts, failures = self.registry.run(turn_context, extraction_output)
        drafts = _filter_noop_config_drafts(db, session=session, drafts=drafts)
        if not drafts or not persist:
            return ProposalPipelineResult(
                batch_id=None,
                item_ids=[],
                drafts=drafts,
                failures=failures,
                extraction_output=extraction_output,
            )
        batch_id, item_ids = persist_proposal_batch(
            db,
            session=session,
            request_id=request_id,
            turn_context=turn_context,
            drafts=drafts,
        )
        return ProposalPipelineResult(
            batch_id=batch_id,
            item_ids=item_ids,
            drafts=drafts,
            failures=failures,
            extraction_output=extraction_output,
        )


def build_turn_proposal_context(
    *,
    session: ConversationSession,
    request_id: str,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    conversation_history_excerpt: list[dict[str, str]],
    lane_result: dict,
    main_reply_summary: str,
    proposal_gate_scores: list[ProposalGateScore] | None = None,
    trusted_events: list[dict] | None = None,
) -> TurnProposalContext:
    return TurnProposalContext(
        session_id=session.id,
        request_id=request_id,
        turn_messages=[
            TurnProposalEvidence(
                message_id=user_message.id,
                role="user",
                content=user_message.content,
                kind="user_message",
            ),
            TurnProposalEvidence(
                message_id=assistant_message.id,
                role="assistant",
                content=assistant_message.content,
                kind="assistant_message",
            ),
        ],
        trusted_events=trusted_events or [],
        conversation_history_excerpt=conversation_history_excerpt,
        lane_result=lane_result,
        main_reply_summary=main_reply_summary,
        proposal_gate_scores=proposal_gate_scores or [],
    )


def extract_proposal_batch(
    db: Session,
    turn_context: TurnProposalContext,
    household_id: str,
) -> ProposalBatchExtractionOutput:
    result = invoke_llm(
        db,
        task_type="proposal_batch_extraction",
        variables={
            "turn_messages": _render_turn_messages(turn_context.turn_messages),
            "trusted_events": dump_json(turn_context.trusted_events) or "[]",
            "main_reply_summary": turn_context.main_reply_summary,
        },
        household_id=household_id,
        conversation_history=turn_context.conversation_history_excerpt,
        request_context={
            "request_id": turn_context.request_id,
            "trace_id": turn_context.request_id,
            "session_id": turn_context.session_id,
            "channel": "conversation_proposal_pipeline",
        },
    )
    if not isinstance(result.data, ProposalBatchExtractionOutput):
        return ProposalBatchExtractionOutput()
    return result.data


def _normalize_turn_message_id_alias(message_id: str, evidence_by_id: dict[str, TurnProposalEvidence]) -> str | None:
    normalized_message_id = str(message_id or "").strip()
    if not normalized_message_id:
        return None
    if normalized_message_id in evidence_by_id:
        return normalized_message_id
    for prefix in ("user_", "assistant_", "message_", "user_message:", "assistant_message:"):
        if not normalized_message_id.startswith(prefix):
            continue
        candidate_id = normalized_message_id[len(prefix) :].strip()
        if candidate_id in evidence_by_id:
            return candidate_id
    return None


def persist_proposal_batch(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    turn_context: TurnProposalContext,
    drafts: list[ProposalDraft],
) -> tuple[str, list[str]]:
    now = utc_now_iso()
    batch_status = _resolve_batch_status(drafts)
    batch = ConversationProposalBatch(
        id=new_uuid(),
        session_id=session.id,
        request_id=request_id,
        source_message_ids_json=dump_json([item.message_id for item in turn_context.turn_messages]) or "[]",
        source_roles_json=dump_json([item.role for item in turn_context.turn_messages]) or "[]",
        lane_json=dump_json(turn_context.lane_result) or "{}",
        status=batch_status,
        created_at=now,
        updated_at=now,
    )
    repository.add_proposal_batch(db, batch)
    item_ids: list[str] = []
    for draft in drafts:
        item = ConversationProposalItem(
            id=new_uuid(),
            batch_id=batch.id,
            proposal_kind=draft.proposal_kind,
            policy_category=draft.policy_category,
            status=_resolve_item_status(draft.policy_category),
            title=draft.title,
            summary=draft.summary,
            evidence_message_ids_json=dump_json(draft.evidence_message_ids) or "[]",
            evidence_roles_json=dump_json(draft.evidence_roles) or "[]",
            dedupe_key=draft.dedupe_key,
            confidence=draft.confidence,
            payload_json=dump_json(draft.payload) or "{}",
            created_at=now,
            updated_at=now,
        )
        repository.add_proposal_item(db, item)
        item_ids.append(item.id)
    db.flush()
    return batch.id, item_ids


def _render_turn_messages(turn_messages: list[TurnProposalEvidence]) -> str:
    lines: list[str] = []
    for item in turn_messages:
        lines.append(f"[{item.kind}] {item.role}({item.message_id}): {item.content}")
    return "\n".join(lines)


def _resolve_item_status(policy_category: str) -> str:
    if policy_category == "ignore":
        return "ignored"
    if policy_category in {"notify", "auto"}:
        return "completed"
    return "pending_confirmation"


def _resolve_batch_status(drafts: list[ProposalDraft]) -> str:
    statuses = {_resolve_item_status(draft.policy_category) for draft in drafts}
    if statuses <= {"completed"}:
        return "completed"
    if statuses <= {"ignored"}:
        return "ignored"
    if "pending_confirmation" in statuses:
        return "pending_confirmation"
    return "pending_policy"


def _filter_noop_config_drafts(
    db: Session,
    *,
    session: ConversationSession,
    drafts: list[ProposalDraft],
) -> list[ProposalDraft]:
    if not session.active_agent_id:
        return drafts
    agent = agent_repository.get_agent_by_household_and_id(
        db,
        household_id=session.household_id,
        agent_id=session.active_agent_id,
    )
    if agent is None:
        return drafts
    soul = agent_repository.get_active_soul_profile(db, agent_id=agent.id)
    current_speaking_style = str(getattr(soul, "speaking_style", "") or "").strip()
    current_personality_traits = (
        [str(item).strip() for item in (load_json(getattr(soul, "personality_traits_json", None)) or []) if str(item).strip()]
        if soul is not None
        else []
    )
    filtered: list[ProposalDraft] = []
    for draft in drafts:
        if draft.proposal_kind != "config_apply":
            filtered.append(draft)
            continue
        payload = dict(draft.payload)
        next_display_name = str(payload.get("display_name") or "").strip()
        if next_display_name and next_display_name == agent.display_name:
            payload.pop("display_name", None)
        next_speaking_style = str(payload.get("speaking_style") or "").strip()
        if next_speaking_style and next_speaking_style == current_speaking_style:
            payload.pop("speaking_style", None)
        next_personality_traits = [
            str(item).strip()
            for item in (payload.get("personality_traits") or [])
            if str(item).strip()
        ] if isinstance(payload.get("personality_traits"), list) else []
        if next_personality_traits and next_personality_traits == current_personality_traits:
            payload.pop("personality_traits", None)
        if not any(payload.get(key) for key in ("display_name", "speaking_style", "personality_traits")):
            continue
        filtered.append(replace(draft, payload=payload))
    return filtered
