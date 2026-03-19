from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso
from app.modules.account.service import AuthenticatedActor
from app.modules.agent import repository as agent_repository
from app.modules.conversation import repository
from app.modules.conversation.models import ConversationMessage, ConversationProposalBatch, ConversationProposalItem, ConversationSession
from app.modules.conversation.proposal_analyzers import (
    ProposalAnalyzerFailure,
    ProposalAnalyzerRegistry,
    ProposalDraft,
    _normalize_config_payload,
)
from app.modules.llm_task import ainvoke_llm, invoke_llm
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput
from app.modules.memory import repository as memory_repository


@dataclass(frozen=True)
class TurnProposalEvidence:
    message_id: str
    role: str
    content: str
    kind: str


@dataclass
class TurnProposalContext:
    db: Session | None
    session_id: str
    request_id: str
    household_id: str
    requester_member_id: str | None
    authenticated_actor: AuthenticatedActor | None
    turn_messages: list[TurnProposalEvidence]
    trusted_events: list[dict]
    conversation_history_excerpt: list[dict[str, str]]
    lane_result: dict
    main_reply_summary: str
    persist_enabled: bool = False

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
        return self.run_with_extraction(
            db,
            session=session,
            request_id=request_id,
            turn_context=turn_context,
            extraction_output=extraction_output,
            persist=persist,
        )

    def run_with_extraction(
        self,
        db: Session,
        *,
        session: ConversationSession,
        request_id: str,
        turn_context: TurnProposalContext,
        extraction_output: ProposalBatchExtractionOutput,
        persist: bool,
    ) -> ProposalPipelineResult:
        turn_context.persist_enabled = persist
        drafts, failures = self.registry.run(turn_context, extraction_output)
        drafts = _filter_noop_config_drafts(db, session=session, drafts=drafts)
        drafts = _filter_existing_memory_drafts(db, session=session, drafts=drafts)
        drafts = _filter_redundant_reminder_drafts(drafts)
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
    db: Session | None,
    session: ConversationSession,
    request_id: str,
    authenticated_actor: AuthenticatedActor | None,
    user_message: ConversationMessage,
    assistant_message: ConversationMessage,
    conversation_history_excerpt: list[dict[str, str]],
    lane_result: dict,
    main_reply_summary: str,
    trusted_events: list[dict] | None = None,
) -> TurnProposalContext:
    return TurnProposalContext(
        db=db,
        session_id=session.id,
        request_id=request_id,
        household_id=session.household_id,
        requester_member_id=session.requester_member_id,
        authenticated_actor=authenticated_actor,
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
            "main_reply_summary": _render_assistant_context_summary(turn_context.main_reply_summary),
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


async def aextract_proposal_batch(
    db: Session,
    turn_context: TurnProposalContext,
    household_id: str,
) -> ProposalBatchExtractionOutput:
    result = await ainvoke_llm(
        db,
        task_type="proposal_batch_extraction",
        variables={
            "turn_messages": _render_turn_messages(turn_context.turn_messages),
            "trusted_events": dump_json(turn_context.trusted_events) or "[]",
            "main_reply_summary": _render_assistant_context_summary(turn_context.main_reply_summary),
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
        content = item.content
        if item.kind == "assistant_message":
            content = "<助手回复内容已省略；仅作上下文，不能作为事实证据>"
        lines.append(f"[{item.kind}] {item.role}({item.message_id}): {content}")
    return "\n".join(lines)


def _render_assistant_context_summary(summary: str) -> str:
    if not summary.strip():
        return "无"
    return "助手回复摘要已省略；它只能帮助理解当前是在追问、确认还是普通问答，不能作为新增事实证据。"


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
        payload = _normalize_config_payload(dict(draft.payload), summary=draft.summary)
        next_display_name = str(payload.get("display_name") or "").strip()
        if next_display_name and next_display_name == agent.display_name:
            payload.pop("display_name", None)
        next_role_summary = str(payload.get("role_summary") or "").strip()
        if next_role_summary and soul is not None and next_role_summary == str(soul.role_summary or "").strip():
            payload.pop("role_summary", None)
        if "intro_message" in payload and soul is not None:
            next_intro_message = payload.get("intro_message")
            current_intro_message = str(soul.intro_message or "").strip() or None
            normalized_intro_message = str(next_intro_message).strip() or None if next_intro_message is not None else None
            if normalized_intro_message == current_intro_message:
                payload.pop("intro_message", None)
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
        current_service_focus = (
            [str(item).strip() for item in (load_json(getattr(soul, "service_focus_json", None)) or []) if str(item).strip()]
            if soul is not None
            else []
        )
        next_service_focus = [
            str(item).strip()
            for item in (payload.get("service_focus") or [])
            if str(item).strip()
        ] if isinstance(payload.get("service_focus"), list) else []
        if next_service_focus and next_service_focus == current_service_focus:
            payload.pop("service_focus", None)
        if not any(
            key in payload and payload.get(key) not in (None, "", [])
            for key in ("display_name", "role_summary", "intro_message", "speaking_style", "personality_traits", "service_focus")
        ):
            continue
        filtered.append(replace(draft, payload=payload))
    return filtered


def _filter_existing_memory_drafts(
    db: Session,
    *,
    session: ConversationSession,
    drafts: list[ProposalDraft],
) -> list[ProposalDraft]:
    existing_memory_rows = _load_existing_memory_rows(db, household_id=session.household_id)
    existing_memory_corpus = _build_existing_memory_corpus(
        rows=existing_memory_rows,
        requester_member_id=session.requester_member_id,
    )
    filtered: list[ProposalDraft] = []
    for draft in drafts:
        if draft.proposal_kind != "memory_write":
            filtered.append(draft)
            continue
        dedupe_key = _build_stable_memory_dedupe_key(session=session, draft=draft)
        existing = memory_repository.get_memory_card_by_dedupe_key(
            db,
            household_id=session.household_id,
            dedupe_key=dedupe_key,
        )
        if existing is not None and getattr(existing, "status", "active") not in {"invalidated", "deleted"}:
            continue
        if existing_memory_corpus and _memory_draft_terms_already_covered(
            draft=draft,
            memory_corpus=existing_memory_corpus,
        ):
            continue
        filtered.append(replace(draft, dedupe_key=dedupe_key))
    return filtered


def _filter_redundant_reminder_drafts(drafts: list[ProposalDraft]) -> list[ProposalDraft]:
    scheduled_evidence_sets = [
        set(draft.evidence_message_ids)
        for draft in drafts
        if draft.proposal_kind == "scheduled_task_create" and draft.evidence_message_ids
    ]
    if not scheduled_evidence_sets:
        return drafts
    filtered: list[ProposalDraft] = []
    for draft in drafts:
        if draft.proposal_kind != "reminder_create":
            filtered.append(draft)
            continue
        evidence_ids = set(draft.evidence_message_ids)
        if evidence_ids and any(evidence_ids & scheduled_ids for scheduled_ids in scheduled_evidence_sets):
            continue
        filtered.append(draft)
    return filtered


def _load_existing_memory_rows(db: Session, *, household_id: str) -> list[Any]:
    rows: list[Any] = []
    page = 1
    page_size = 200
    while True:
        page_rows, total = memory_repository.list_memory_cards(
            db,
            household_id=household_id,
            page=page,
            page_size=page_size,
        )
        rows.extend(page_rows)
        if len(rows) >= total or not page_rows:
            return rows
        page += 1


def _build_existing_memory_corpus(*, rows: list[Any], requester_member_id: str | None) -> str:
    parts: list[str] = []
    for row in rows:
        status = str(getattr(row, "status", "") or "")
        if status in {"invalidated", "deleted"}:
            continue
        subject_member_id = getattr(row, "subject_member_id", None)
        if requester_member_id and subject_member_id not in {None, requester_member_id}:
            continue
        parts.extend(_extract_existing_memory_text_parts(row))
    return " ".join(part for part in parts if part)


def _extract_existing_memory_text_parts(row: Any) -> list[str]:
    parts = [
        _normalize_match_text(getattr(row, "title", None)),
        _normalize_match_text(getattr(row, "summary", None)),
    ]
    content = load_json(getattr(row, "content_json", None))
    parts.extend(_collect_text_fragments(content))
    return [part for part in parts if part]


def _memory_draft_terms_already_covered(*, draft: ProposalDraft, memory_corpus: str) -> bool:
    terms = _extract_memory_match_terms(draft)
    if not terms:
        return False
    return all(term in memory_corpus for term in terms)


def _extract_memory_match_terms(draft: ProposalDraft) -> list[str]:
    payload = dict(draft.payload)
    for key in ("kind", "memory_type", "type", "title", "summary"):
        payload.pop(key, None)
    terms = [term for term in _collect_text_fragments(payload) if len(term) >= 2]
    if terms:
        return sorted(set(terms))
    fallback_terms = [
        term
        for term in (
            _normalize_match_text(draft.summary),
            _normalize_match_text(draft.title),
        )
        if term
    ]
    return sorted(set(fallback_terms))


def _build_stable_memory_dedupe_key(
    *,
    session: ConversationSession,
    draft: ProposalDraft,
) -> str:
    payload = dict(draft.payload)
    memory_type = str(payload.get("memory_type") or payload.get("type") or "fact").strip() or "fact"
    subject_key = session.requester_member_id or "global"
    signature_parts = [
        _normalize_match_text(draft.title),
        _normalize_match_text(draft.summary),
        *_collect_text_fragments(payload),
    ]
    normalized_signature = "|".join(part for part in signature_parts if part)
    if not normalized_signature:
        normalized_signature = "empty"
    digest = sha256(normalized_signature.encode("utf-8")).hexdigest()[:24]
    return f"memory:{session.household_id}:{memory_type}:{subject_key}:{digest}"


def _collect_text_fragments(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = _normalize_match_text(value)
        return [normalized] if normalized else []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        normalized = _normalize_match_text(str(value))
        return [normalized] if normalized else []
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_collect_text_fragments(item))
        return parts
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            if str(key).strip() in {"kind", "memory_type", "type", "title", "summary"}:
                continue
            parts.extend(_collect_text_fragments(item))
        return parts
    return []


def _normalize_match_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())
