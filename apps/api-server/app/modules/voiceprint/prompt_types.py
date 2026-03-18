from __future__ import annotations

from dataclasses import dataclass

from app.modules.voiceprint.models import VoiceprintEnrollment


@dataclass(slots=True, frozen=True)
class VoiceprintPromptEnrollmentSnapshot:
    id: str
    terminal_id: str
    status: str
    sample_goal: int
    sample_count: int

    @classmethod
    def from_enrollment(cls, enrollment: VoiceprintEnrollment) -> "VoiceprintPromptEnrollmentSnapshot":
        return cls(
            id=str(enrollment.id),
            terminal_id=str(enrollment.terminal_id),
            status=str(enrollment.status),
            sample_goal=int(enrollment.sample_goal or 0),
            sample_count=int(enrollment.sample_count or 0),
        )
