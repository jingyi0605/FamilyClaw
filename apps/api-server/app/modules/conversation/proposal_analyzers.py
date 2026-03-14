from __future__ import annotations

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
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message", "system_event", "trusted_external_event"},
                require_non_assistant=True,
            )
            if not evidence_ids:
                continue
            title = (item.title or "").strip() or _build_title_from_summary(item.summary, prefix="记忆提案")
            summary = (item.summary or "").strip()
            if not title or not summary:
                continue
            payload = dict(item.payload)
            payload.setdefault("kind", self.proposal_kind)
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
            evidence_ids, evidence_roles = turn_context.resolve_evidence(
                item.evidence_message_ids,
                allowed_kinds={"user_message"},
                require_non_assistant=True,
            )
            if not evidence_ids:
                continue
            payload = dict(item.payload)
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
