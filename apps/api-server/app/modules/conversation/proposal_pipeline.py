from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app.db.utils import dump_json, new_uuid, utc_now_iso
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
            if evidence is None or evidence.kind not in allowed_kinds:
                continue
            resolved_ids.append(evidence.message_id)
            resolved_roles.append(evidence.role)
        if require_non_assistant and resolved_ids and all(role == "assistant" for role in resolved_roles):
            return [], []
        return resolved_ids, resolved_roles


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


def persist_proposal_batch(
    db: Session,
    *,
    session: ConversationSession,
    request_id: str,
    turn_context: TurnProposalContext,
    drafts: list[ProposalDraft],
) -> tuple[str, list[str]]:
    now = utc_now_iso()
    batch = ConversationProposalBatch(
        id=new_uuid(),
        session_id=session.id,
        request_id=request_id,
        source_message_ids_json=dump_json([item.message_id for item in turn_context.turn_messages]) or "[]",
        source_roles_json=dump_json([item.role for item in turn_context.turn_messages]) or "[]",
        lane_json=dump_json(turn_context.lane_result) or "{}",
        status="pending_policy",
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
            status="pending_policy",
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
