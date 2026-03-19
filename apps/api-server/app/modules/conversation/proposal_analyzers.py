from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.db.utils import load_json
from app.modules.conversation import repository as conversation_repository
from app.modules.llm_task.output_models import ProposalBatchExtractionOutput
from app.modules.scheduler.draft_service import (
    build_partial_update_payload_from_text,
    build_conversation_proposal_payload,
    build_conversation_proposal_summary,
    build_conversation_proposal_title,
    create_draft_from_conversation,
    looks_like_scheduled_task_followup,
    looks_like_scheduled_task_intent,
    preview_draft_from_conversation,
)
from app.modules.scheduler.service import list_task_definitions
from app.modules.scheduler.schemas import ScheduledTaskDefinitionRead, ScheduledTaskDraftFromConversationRequest

if TYPE_CHECKING:
    from app.modules.conversation.proposal_pipeline import TurnProposalContext


@dataclass(frozen=True)
class ProposalDraft:
    proposal_kind: str
    policy_category: str
    title: str
    summary: str | None
    evidence_message_ids: list[str]
    evidence_roles: list[str]
    dedupe_key: str | None
    confidence: float
    payload: dict


class ProposalAnalyzer(Protocol):
    name: str
    proposal_kind: str
    default_policy_category: str

    def supports(self, turn_context: "TurnProposalContext") -> bool: ...
    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]: ...


@dataclass(frozen=True)
class ProposalAnalyzerFailure:
    analyzer_name: str
    error_message: str


class ProposalAnalyzerRegistry:
    def __init__(self, analyzers: list[ProposalAnalyzer] | None = None) -> None:
        default_analyzers: list[ProposalAnalyzer] = [
            MemoryProposalAnalyzer(),
            ConfigProposalAnalyzer(),
            ScheduledTaskProposalAnalyzer(),
            ScheduledTaskOperationProposalAnalyzer(),
            ReminderProposalAnalyzer(),
        ]
        self._analyzers = analyzers or default_analyzers

    def list_analyzers(self) -> list[ProposalAnalyzer]:
        return list(self._analyzers)

    def run(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> tuple[list[ProposalDraft], list[ProposalAnalyzerFailure]]:
        drafts: list[ProposalDraft] = []
        failures: list[ProposalAnalyzerFailure] = []
        for analyzer in self._analyzers:
            if not analyzer.supports(turn_context):
                continue
            try:
                drafts.extend(analyzer.analyze(turn_context, extraction_output))
            except Exception as exc:
                failures.append(
                    ProposalAnalyzerFailure(
                        analyzer_name=analyzer.name,
                        error_message=str(exc),
                    )
                )
        return drafts, failures


class MemoryProposalAnalyzer:
    name = "memory_proposal_analyzer"
    proposal_kind = "memory_write"
    default_policy_category = "ask"

    def supports(self, turn_context: "TurnProposalContext") -> bool:
        return bool(turn_context.user_messages)

    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]:
        drafts: list[ProposalDraft] = []
        for item in extraction_output.memory_items:
            payload = _normalize_memory_payload(dict(item.payload))
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message", "system_event", "trusted_external_event"},
                require_non_assistant=True,
            )
            if not evidence_ids:
                continue
            summary = (
                (item.summary or "").strip()
                or str(payload.get("summary") or "").strip()
                or _build_memory_summary_from_payload(payload)
            )
            title = (
                (item.title or "").strip()
                or str(payload.get("title") or "").strip()
                or _build_title_from_summary(summary, prefix="记忆提案")
            )
            if not title or not summary:
                continue
            payload.setdefault("kind", self.proposal_kind)
            payload.setdefault("summary", summary)
            payload.setdefault("title", title[:200])
            payload.setdefault("memory_type", _infer_memory_type_from_payload(payload))
            drafts.append(
                ProposalDraft(
                    proposal_kind=self.proposal_kind,
                    policy_category=self.default_policy_category,
                    title=title[:200],
                    summary=summary,
                    evidence_message_ids=evidence_ids,
                    evidence_roles=evidence_roles,
                    dedupe_key=_build_dedupe_key(self.proposal_kind, evidence_ids, title),
                    confidence=item.confidence,
                    payload=payload,
                )
            )
        return drafts


class ConfigProposalAnalyzer:
    name = "config_proposal_analyzer"
    proposal_kind = "config_apply"
    default_policy_category = "ask"

    def supports(self, turn_context: "TurnProposalContext") -> bool:
        return bool(turn_context.user_messages)

    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]:
        drafts: list[ProposalDraft] = []
        editable_fields = (
            "display_name",
            "role_summary",
            "intro_message",
            "speaking_style",
            "personality_traits",
            "service_focus",
        )
        for item in extraction_output.config_items:
            payload = _normalize_config_payload(dict(item.payload), summary=item.summary)
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message"},
                require_non_assistant=True,
            )
            if not evidence_ids and any(payload.get(key) for key in editable_fields):
                latest_user_evidence = turn_context.latest_user_evidence()
                if latest_user_evidence is not None:
                    evidence_ids = [latest_user_evidence.message_id]
                    evidence_roles = [latest_user_evidence.role]
            if not evidence_ids:
                continue
            if not any(payload.get(key) for key in editable_fields):
                continue
            title = (item.title or "").strip() or "应用 Agent 配置建议"
            summary = (item.summary or "").strip() or "根据用户明确表达更新 Agent 配置。"
            drafts.append(
                ProposalDraft(
                    proposal_kind=self.proposal_kind,
                    policy_category=self.default_policy_category,
                    title=title[:200],
                    summary=summary,
                    evidence_message_ids=evidence_ids,
                    evidence_roles=evidence_roles,
                    dedupe_key=_build_dedupe_key(self.proposal_kind, evidence_ids, title),
                    confidence=item.confidence,
                    payload=payload,
                )
            )
        return drafts


class ReminderProposalAnalyzer:
    name = "reminder_proposal_analyzer"
    proposal_kind = "reminder_create"
    default_policy_category = "ask"

    def supports(self, turn_context: "TurnProposalContext") -> bool:
        return bool(turn_context.user_messages)

    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]:
        drafts: list[ProposalDraft] = []
        for item in extraction_output.reminder_items:
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message"},
                require_non_assistant=True,
            )
            if not evidence_ids:
                continue
            payload = dict(item.payload)
            title = str(payload.get("title") or item.title or "").strip()
            if not title:
                continue
            summary = (item.summary or "").strip() or "根据本轮对话整理出的提醒草稿。"
            drafts.append(
                ProposalDraft(
                    proposal_kind=self.proposal_kind,
                    policy_category=self.default_policy_category,
                    title=title[:200],
                    summary=summary,
                    evidence_message_ids=evidence_ids,
                    evidence_roles=evidence_roles,
                    dedupe_key=_build_dedupe_key(self.proposal_kind, evidence_ids, title),
                    confidence=item.confidence,
                    payload=payload,
                )
            )
        return drafts


class ScheduledTaskProposalAnalyzer:
    name = "scheduled_task_proposal_analyzer"
    proposal_kind = "scheduled_task_create"
    default_policy_category = "ask"

    def supports(self, turn_context: "TurnProposalContext") -> bool:
        return bool(turn_context.user_messages and turn_context.db is not None and turn_context.authenticated_actor is not None)

    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]:
        _ = extraction_output
        latest_user_evidence = turn_context.latest_user_evidence()
        if latest_user_evidence is None:
            return []
        assert turn_context.db is not None
        assert turn_context.authenticated_actor is not None
        db = turn_context.db
        authenticated_actor = turn_context.authenticated_actor
        message_text = latest_user_evidence.content.strip()
        if ScheduledTaskOperationProposalAnalyzer._detect_operation(message_text) is not None:
            return []
        pending_draft_id = _find_latest_pending_scheduled_task_draft_id(turn_context)
        if not looks_like_scheduled_task_intent(message_text) and not (pending_draft_id and looks_like_scheduled_task_followup(message_text)):
            return []
        request = ScheduledTaskDraftFromConversationRequest(
            household_id=turn_context.household_id,
            text=message_text,
            draft_id=pending_draft_id,
        )
        if turn_context.persist_enabled:
            draft = create_draft_from_conversation(
                db,
                actor=authenticated_actor,
                payload=request,
            )
        else:
            draft = preview_draft_from_conversation(
                db,
                actor=authenticated_actor,
                payload=request,
            )
        payload = build_conversation_proposal_payload(draft)
        return [
            ProposalDraft(
                proposal_kind=self.proposal_kind,
                policy_category=self.default_policy_category,
                title=build_conversation_proposal_title(draft),
                summary=build_conversation_proposal_summary(draft),
                evidence_message_ids=[latest_user_evidence.message_id],
                evidence_roles=[latest_user_evidence.role],
                dedupe_key=_build_dedupe_key(self.proposal_kind, [latest_user_evidence.message_id], draft.intent_summary),
                confidence=0.92,
                payload=payload,
            )
        ]


class ScheduledTaskOperationProposalAnalyzer:
    name = "scheduled_task_operation_proposal_analyzer"
    default_policy_category = "ask"

    def supports(self, turn_context: "TurnProposalContext") -> bool:
        return bool(turn_context.user_messages and turn_context.db is not None and turn_context.authenticated_actor is not None)

    def analyze(
        self,
        turn_context: "TurnProposalContext",
        extraction_output: ProposalBatchExtractionOutput,
    ) -> list[ProposalDraft]:
        _ = extraction_output
        latest_user_evidence = turn_context.latest_user_evidence()
        if latest_user_evidence is None:
            return []
        assert turn_context.db is not None
        assert turn_context.authenticated_actor is not None
        message_text = latest_user_evidence.content.strip()
        operation = self._detect_operation(message_text)
        if operation is None:
            return []
        tasks = list_task_definitions(
            turn_context.db,
            actor=turn_context.authenticated_actor,
            household_id=turn_context.household_id,
        )
        target_task = self._match_task(message_text, tasks)
        if target_task is None:
            return []
        proposal_kind = f"scheduled_task_{operation}"
        payload: dict[str, object] = {
            "task_id": target_task.id,
            "task_name": target_task.name,
            "intent_summary": self._build_summary(operation, target_task.name),
            "can_confirm": True,
        }
        summary = self._build_summary(operation, target_task.name)
        if operation == "update":
            update_payload = build_partial_update_payload_from_text(
                turn_context.db,
                actor=turn_context.authenticated_actor,
                household_id=turn_context.household_id,
                text=message_text,
            )
            if not update_payload:
                return []
            payload["update_payload"] = update_payload
            payload["can_confirm"] = True
            summary = f"更新计划任务“{target_task.name}”"
        return [
            ProposalDraft(
                proposal_kind=proposal_kind,
                policy_category=self.default_policy_category,
                title=summary,
                summary=summary,
                evidence_message_ids=[latest_user_evidence.message_id],
                evidence_roles=[latest_user_evidence.role],
                dedupe_key=_build_dedupe_key(proposal_kind, [latest_user_evidence.message_id], summary),
                confidence=0.88,
                payload=payload,
            )
        ]

    @staticmethod
    def _detect_operation(text: str) -> str | None:
        if any(keyword in text for keyword in ("暂停", "停用", "先停")):
            return "pause"
        if any(keyword in text for keyword in ("恢复", "启用", "继续执行", "重新开启")):
            return "resume"
        if any(keyword in text for keyword in ("删除", "删掉", "移除")):
            return "delete"
        if any(keyword in text for keyword in ("改成", "改为", "换成", "调整", "修改")):
            return "update"
        return None

    @staticmethod
    def _match_task(text: str, tasks: list[ScheduledTaskDefinitionRead]) -> ScheduledTaskDefinitionRead | None:
        sorted_tasks = sorted(tasks, key=lambda item: len(getattr(item, "name", "")), reverse=True)
        for task in sorted_tasks:
            name = str(getattr(task, "name", "")).strip()
            if name and name in text:
                return task
        if len(tasks) == 1 and any(keyword in text for keyword in ("这个任务", "这个计划任务", "这条计划任务")):
            return tasks[0]
        return None

    @staticmethod
    def _build_summary(operation: str, task_name: str) -> str:
        mapping = {
            "pause": f"暂停计划任务：{task_name}",
            "resume": f"恢复计划任务：{task_name}",
            "delete": f"删除计划任务：{task_name}",
            "update": f"更新计划任务：{task_name}",
        }
        return mapping.get(operation, task_name)


def _find_latest_pending_scheduled_task_draft_id(turn_context: "TurnProposalContext") -> str | None:
    if turn_context.db is None:
        return None
    batches = list(conversation_repository.list_proposal_batches(turn_context.db, session_id=turn_context.session_id))
    for batch in reversed(batches):
        items = list(conversation_repository.list_proposal_items(turn_context.db, batch_id=batch.id))
        for item in reversed(items):
            if item.proposal_kind != "scheduled_task_create" or item.status != "pending_confirmation":
                continue
            payload = load_json(item.payload_json) or {}
            draft_id = str(payload.get("draft_id") or "").strip() if isinstance(payload, dict) else ""
            if draft_id:
                return draft_id
    return None


def _build_title_from_summary(summary: str | None, *, prefix: str) -> str:
    normalized = (summary or "").strip()
    return prefix if not normalized else f"{prefix}：{normalized[:24]}"


def _build_dedupe_key(proposal_kind: str, evidence_message_ids: list[str], title: str) -> str:
    source_part = ",".join(sorted(evidence_message_ids))
    return f"{proposal_kind}:{source_part}:{title[:50]}"


def _normalize_memory_payload(payload: dict) -> dict:
    normalized = dict(payload)
    memory_type = _normalize_memory_type_alias(normalized.get("memory_type") or normalized.get("type"))
    if memory_type:
        normalized["memory_type"] = memory_type
    subject_name = str(
        normalized.get("subject_name")
        or normalized.get("subject")
        or normalized.get("member_name")
        or ""
    ).strip()
    if subject_name and "subject_name" not in normalized:
        normalized["subject_name"] = subject_name
    event_name = str(
        normalized.get("milestone")
        or normalized.get("event_name")
        or normalized.get("event")
        or ""
    ).strip()
    if event_name:
        if "milestone" not in normalized and _looks_like_growth_milestone(event_name):
            normalized["milestone"] = event_name
        if "event_name" not in normalized:
            normalized["event_name"] = event_name
    occurred_at_text = str(
        normalized.get("occurred_at_text")
        or normalized.get("date")
        or normalized.get("date_text")
        or ""
    ).strip()
    if occurred_at_text and "occurred_at_text" not in normalized:
        normalized["occurred_at_text"] = occurred_at_text
    return normalized


def _build_memory_summary_from_payload(payload: dict) -> str:
    subject_name = str(payload.get("subject_name") or "").strip()
    milestone = str(payload.get("milestone") or payload.get("event_name") or "").strip()
    occurred_at_text = str(payload.get("occurred_at_text") or payload.get("effective_at") or "").strip()
    if subject_name and milestone and occurred_at_text:
        return f"{subject_name}: {milestone} ({occurred_at_text})"
    if subject_name and milestone:
        return f"{subject_name}: {milestone}"
    if milestone and occurred_at_text:
        return f"{milestone} ({occurred_at_text})"
    entries = [
        (str(key).strip(), _stringify_memory_payload_value(value))
        for key, value in payload.items()
        if str(key).strip() and str(key).strip() not in {"kind", "memory_type", "type", "title", "summary"}
    ]
    entries = [(key, value) for key, value in entries if value]
    if not entries:
        return ""
    if len(entries) == 1:
        key, value = entries[0]
        return f"{key}: {value}"
    return "; ".join(f"{key}: {value}" for key, value in entries[:3])


def _stringify_memory_payload_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts)
    return str(value).strip() if value is not None else ""


def _infer_memory_type_from_payload(payload: dict) -> str:
    explicit_type = _normalize_memory_type_alias(payload.get("memory_type") or payload.get("type"))
    if explicit_type:
        return explicit_type
    keys = [str(key).strip() for key in payload.keys()]
    text_blob = " ".join(_stringify_memory_payload_value(value) for value in payload.values())
    if any(key in {"milestone", "event_name", "occurred_at_text", "effective_at"} for key in keys) or _looks_like_growth_milestone(text_blob):
        return "growth"
    if any(key in {"date", "date_text"} for key in keys):
        return "event"
    if any(("\u559c\u6b22" in key) or ("\u4e0d\u559c\u6b22" in key) or ("\u504f\u597d" in key) for key in keys):
        return "preference"
    return "fact"


def _normalize_memory_type_alias(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    aliases = {
        "fact": "fact",
        "event": "event",
        "preference": "preference",
        "relation": "relation",
        "growth": "growth",
        "observation": "observation",
        "milestone": "growth",
        "growth_milestone": "growth",
        "growth-event": "growth",
        "timeline": "event",
        "schedule": "event",
    }
    return aliases.get(normalized, "")


def _looks_like_growth_milestone(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    keywords = ("\u7b2c\u4e00\u6b21", "\u91cc\u7a0b\u7891", "\u4f1a\u8d70\u8def", "\u4f1a\u53eb", "\u957f\u7259", "\u7ffb\u8eab", "\u722c", "\u7ad9")
    return any(keyword in normalized for keyword in keywords)


def _normalize_config_payload(payload: dict, *, summary: str | None) -> dict:
    normalized = dict(payload)
    updates: dict[str, object] = {}

    alias_value = normalized.pop("name", None)
    if not normalized.get("display_name") and isinstance(alias_value, str) and alias_value.strip():
        normalized["display_name"] = alias_value.strip()
    if not normalized.get("display_name"):
        for alias_key in ("nickname", "persona_name", "assistant_name"):
            alias_candidate = normalized.pop(alias_key, None)
            if isinstance(alias_candidate, str) and alias_candidate.strip():
                normalized["display_name"] = alias_candidate.strip()
                break
    display_name = normalized.get("display_name")
    if isinstance(display_name, str):
        display_name = display_name.strip()
        if _looks_like_placeholder_name(display_name):
            display_name = ""
        if display_name:
            updates["display_name"] = display_name
    role_summary = normalized.get("role_summary", normalized.get("role"))
    if isinstance(role_summary, str):
        role_summary = role_summary.strip()
        if role_summary:
            updates["role_summary"] = role_summary

    for nullable_key in ("intro_message", "speaking_style"):
        if nullable_key not in normalized:
            continue
        raw_value = normalized.get(nullable_key)
        if raw_value is None:
            updates[nullable_key] = None
        else:
            next_value = str(raw_value).strip()
            updates[nullable_key] = next_value or None

    personality_traits = normalized.get("personality_traits")
    if isinstance(personality_traits, str):
        updates["personality_traits"] = [personality_traits.strip()] if personality_traits.strip() else []
    elif isinstance(personality_traits, list):
        updates["personality_traits"] = [str(item).strip() for item in personality_traits if str(item).strip()]

    service_focus = normalized.get("service_focus")
    if isinstance(service_focus, str):
        updates["service_focus"] = [service_focus.strip()] if service_focus.strip() else []
    elif isinstance(service_focus, list):
        updates["service_focus"] = [str(item).strip() for item in service_focus if str(item).strip()]

    if not any(updates.get(key) for key in ("display_name", "role_summary", "intro_message", "speaking_style", "personality_traits", "service_focus")):
        summary_text = (summary or "").strip()
        if summary_text:
            inferred_name = _extract_display_name_from_summary(summary_text)
            if inferred_name is not None:
                updates["display_name"] = inferred_name
    return updates


def _looks_like_placeholder_name(value: str) -> bool:
    normalized = value.strip().lower()
    placeholders = {"新名字", "名字", "新称呼", "某个名字", "待定", "未定", "new name"}
    return normalized in {item.lower() for item in placeholders}


def _extract_display_name_from_summary(summary: str) -> str | None:
    normalized = summary.strip()
    markers = ("改成", "叫", "改名为", "名字是")
    for marker in markers:
        if marker not in normalized:
            continue
        candidate = normalized.split(marker, 1)[1].strip(" ：:，。,.！!？?“”\"'")
        if not candidate:
            continue
        candidate = candidate.split("，", 1)[0].split("。", 1)[0].split(" ", 1)[0].strip("“”\"'")
        if candidate and not _looks_like_placeholder_name(candidate):
            return candidate
    return None
