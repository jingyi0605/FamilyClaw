from typing import Any

from pydantic import BaseModel, Field


class QaFactReference(BaseModel):
    type: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    occurred_at: str | None = None
    visibility: str = Field(default="family", min_length=1, max_length=30)
    inferred: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class QaQueryLogCreate(BaseModel):
    household_id: str = Field(min_length=1)
    requester_member_id: str | None = Field(default=None, min_length=1)
    question: str = Field(min_length=1, max_length=500)
    answer_type: str = Field(min_length=1, max_length=50)
    answer_summary: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0, ge=0, le=1)
    degraded: bool = False
    facts: list[QaFactReference] = Field(default_factory=list)


class QaQueryLogRead(QaQueryLogCreate):
    id: str
    created_at: str
