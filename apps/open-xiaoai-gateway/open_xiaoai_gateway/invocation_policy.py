from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from open_xiaoai_gateway.settings import GatewayInvocationMode, Settings

InvocationDecisionType = Literal["familyclaw_takeover", "native_passthrough", "invalid_config"]


@dataclass(slots=True)
class InvocationDecision:
    decision_type: InvocationDecisionType
    matched_prefix: str | None
    resolved_text: str | None
    reason: str
    should_pause: bool = False


@dataclass(slots=True)
class GatewayInvocationPolicy:
    mode: GatewayInvocationMode
    takeover_prefixes: tuple[str, ...]
    strip_takeover_prefix: bool
    pause_on_takeover: bool

    @classmethod
    def from_settings(cls, current_settings: Settings) -> "GatewayInvocationPolicy":
        return cls(
            mode=current_settings.invocation_mode,
            takeover_prefixes=tuple(current_settings.takeover_prefixes),
            strip_takeover_prefix=current_settings.strip_takeover_prefix,
            pause_on_takeover=current_settings.pause_on_takeover,
        )

    def decide(self, text: str) -> InvocationDecision:
        normalized_text = text.strip()
        if not normalized_text:
            return InvocationDecision(
                decision_type="native_passthrough",
                matched_prefix=None,
                resolved_text=None,
                reason="transcript_empty",
            )

        if self.mode == "always_familyclaw":
            return InvocationDecision(
                decision_type="familyclaw_takeover",
                matched_prefix=None,
                resolved_text=normalized_text,
                reason="always_familyclaw",
                should_pause=False,
            )

        if not self.takeover_prefixes:
            return InvocationDecision(
                decision_type="invalid_config",
                matched_prefix=None,
                resolved_text=None,
                reason="native_first_prefixes_empty",
            )

        for prefix in self.takeover_prefixes:
            if not normalized_text.startswith(prefix):
                continue
            resolved_text = normalized_text
            if self.strip_takeover_prefix:
                resolved_text = normalized_text[len(prefix) :].lstrip()
            resolved_text = resolved_text.strip()
            if not resolved_text:
                return InvocationDecision(
                    decision_type="native_passthrough",
                    matched_prefix=prefix,
                    resolved_text=None,
                    reason="takeover_text_empty_after_strip",
                )
            return InvocationDecision(
                decision_type="familyclaw_takeover",
                matched_prefix=prefix,
                resolved_text=resolved_text,
                reason="takeover_prefix_matched",
                should_pause=self.pause_on_takeover,
            )

        return InvocationDecision(
            decision_type="native_passthrough",
            matched_prefix=None,
            resolved_text=None,
            reason="takeover_prefix_not_matched",
        )
