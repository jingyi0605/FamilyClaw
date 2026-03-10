from typing import Any, Literal

from pydantic import BaseModel, Field

SceneExecutionStatus = Literal["planned", "running", "success", "partial", "skipped", "blocked", "failed"]
SceneExecutionStepType = Literal["reminder", "broadcast", "device_action", "context_update"]
SceneExecutionStepStatus = Literal["planned", "success", "skipped", "failed", "blocked"]


class SceneTemplateBase(BaseModel):
    household_id: str = Field(min_length=1)
    template_code: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=1000)
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    trigger: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    guards: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    rollout_policy: dict[str, Any] = Field(default_factory=dict)


class SceneTemplateUpsert(SceneTemplateBase):
    updated_by: str | None = Field(default=None, min_length=1)


class SceneTemplateRead(SceneTemplateBase):
    id: str
    version: int
    updated_by: str | None = None
    updated_at: str


class SceneExecutionCreate(BaseModel):
    template_id: str = Field(min_length=1)
    household_id: str = Field(min_length=1)
    trigger_key: str = Field(min_length=1, max_length=100)
    trigger_source: str = Field(min_length=1, max_length=30)
    started_at: str = Field(min_length=1)
    finished_at: str | None = None
    status: SceneExecutionStatus = "planned"
    guard_result: dict[str, Any] = Field(default_factory=dict)
    conflict_result: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class SceneExecutionRead(SceneExecutionCreate):
    id: str


class SceneExecutionStepCreate(BaseModel):
    execution_id: str = Field(min_length=1)
    step_index: int = Field(ge=0, le=1000)
    step_type: SceneExecutionStepType
    target_ref: str | None = Field(default=None, max_length=255)
    request: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    status: SceneExecutionStepStatus = "planned"
    started_at: str | None = None
    finished_at: str | None = None


class SceneExecutionStepRead(SceneExecutionStepCreate):
    id: str
