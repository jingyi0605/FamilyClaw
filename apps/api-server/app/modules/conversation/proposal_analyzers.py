from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.modules.llm_task.output_models import ProposalBatchExtractionOutput

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
        self._analyzers = analyzers or [
            MemoryProposalAnalyzer(),
            ConfigProposalAnalyzer(),
            ReminderProposalAnalyzer(),
        ]

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
        for item in extraction_output.config_items:
            payload = _normalize_config_payload(dict(item.payload), summary=item.summary)
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message"},
                require_non_assistant=True,
            )
            if not evidence_ids and any(payload.get(key) for key in ("display_name", "speaking_style", "personality_traits")):
                latest_user_evidence = turn_context.latest_user_evidence()
                if latest_user_evidence is not None:
                    evidence_ids = [latest_user_evidence.message_id]
                    evidence_roles = [latest_user_evidence.role]
            if not evidence_ids:
                continue
            if not any(payload.get(key) for key in ("display_name", "speaking_style", "personality_traits")):
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


def _build_title_from_summary(summary: str | None, *, prefix: str) -> str:
    normalized = (summary or "").strip()
    return prefix if not normalized else f"{prefix}：{normalized[:24]}"


def _build_dedupe_key(proposal_kind: str, evidence_message_ids: list[str], title: str) -> str:
    source_part = ",".join(sorted(evidence_message_ids))
    return f"{proposal_kind}:{source_part}:{title[:50]}"


def _normalize_memory_payload(payload: dict) -> dict:
    normalized = dict(payload)
    if "type" in normalized and "memory_type" not in normalized:
        normalized["memory_type"] = normalized.get("type")
    return normalized


def _build_memory_summary_from_payload(payload: dict) -> str:
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
        return f"{key}：{value}"
    return "；".join(f"{key}：{value}" for key, value in entries[:3])


def _stringify_memory_payload_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "、".join(parts)
    return str(value).strip() if value is not None else ""


def _infer_memory_type_from_payload(payload: dict) -> str:
    explicit_type = str(payload.get("memory_type") or payload.get("type") or "").strip()
    if explicit_type:
        return explicit_type
    keys = [str(key).strip() for key in payload.keys()]
    if any(("喜欢" in key) or ("不喜欢" in key) or ("偏好" in key) for key in keys):
        return "preference"
    return "fact"


def _normalize_config_payload(payload: dict, *, summary: str | None) -> dict:
    normalized = dict(payload)
    alias_value = normalized.pop("name", None)
    if not normalized.get("display_name") and isinstance(alias_value, str):
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
            normalized["display_name"] = None
        else:
            normalized["display_name"] = display_name
    personality_traits = normalized.get("personality_traits")
    if isinstance(personality_traits, str):
        normalized["personality_traits"] = [personality_traits.strip()] if personality_traits.strip() else []
    elif isinstance(personality_traits, list):
        normalized["personality_traits"] = [str(item).strip() for item in personality_traits if str(item).strip()]
    speaking_style = normalized.get("speaking_style")
    if isinstance(speaking_style, str):
        normalized["speaking_style"] = speaking_style.strip() or None

    if not any(normalized.get(key) for key in ("display_name", "speaking_style", "personality_traits")):
        summary_text = (summary or "").strip()
        if summary_text:
            inferred_name = _extract_display_name_from_summary(summary_text)
            if inferred_name is not None:
                normalized["display_name"] = inferred_name
    return normalized


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
