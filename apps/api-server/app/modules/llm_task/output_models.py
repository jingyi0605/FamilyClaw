"""LLM 结构化输出模型定义"""

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ButlerBootstrapOutput(BaseModel):
    """管家引导输出（简化版）"""

    display_name: str | None = Field(default=None, description="管家名称")
    speaking_style: str | None = Field(default=None, description="说话风格，如：幽默风趣、温柔体贴、干练高效")
    personality_traits: list[str] = Field(default_factory=list, description="性格特点列表，至少2个")
    is_complete: bool = Field(default=False, description="是否收集完毕")


class MemoryExtractionOutput(BaseModel):
    """记忆提取输出"""

    memories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="提取的记忆列表，每条包含 type/content/members 字段",
    )


class ReminderExtractionOutput(BaseModel):
    """提醒创建提取输出"""

    should_create: bool = Field(default=False, description="是否识别到明确的提醒创建意图")
    title: str | None = Field(default=None, description="提醒标题")
    description: str | None = Field(default=None, description="提醒说明")
    trigger_at: str | None = Field(default=None, description="提醒触发时间，ISO8601 字符串")


class ProposalExtractionItemOutput(BaseModel):
    """统一提案提取项"""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(
        default=None,
        description="提案标题",
        validation_alias=AliasChoices("title", "name"),
    )
    summary: str | None = Field(
        default=None,
        description="提案摘要",
        validation_alias=AliasChoices("summary", "content", "description"),
    )
    confidence: float = Field(default=0.0, ge=0, le=1, description="提案置信度")
    evidence_message_ids: list[str] = Field(
        default_factory=list,
        description="提案引用的来源消息 ID",
        validation_alias=AliasChoices("evidence_message_ids", "evidence_ids", "message_ids"),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="提案原始载荷",
        validation_alias=AliasChoices("payload", "data", "content_payload"),
    )

    @field_validator("title", "summary", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        normalized = str(value or "").strip().lower()
        if not normalized:
            return 0.0
        if normalized in {"high", "\u9ad8", "\u9ad8\u7f6e\u4fe1\u5ea6"}:
            return 0.9
        if normalized in {"medium", "medium_high", "\u4e2d", "\u4e2d\u7b49", "\u4e2d\u7f6e\u4fe1\u5ea6"}:
            return 0.65
        if normalized in {"low", "\u4f4e", "\u4f4e\u7f6e\u4fe1\u5ea6"}:
            return 0.35
        try:
            return float(normalized)
        except ValueError:
            return 0.0

    @field_validator("evidence_message_ids", mode="before")
    @classmethod
    def normalize_evidence_message_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if not isinstance(value, list):
            return []
        normalized_ids: list[str] = []
        for item in value:
            message_id = str(item or "").strip()
            if message_id:
                normalized_ids.append(message_id)
        return normalized_ids

    @field_validator("payload", mode="before")
    @classmethod
    def normalize_payload(cls, value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ProposalBatchExtractionOutput(BaseModel):
    """统一提案提取输出"""

    memory_items: list[ProposalExtractionItemOutput] = Field(default_factory=list, description="记忆提案列表")
    config_items: list[ProposalExtractionItemOutput] = Field(default_factory=list, description="配置提案列表")
    reminder_items: list[ProposalExtractionItemOutput] = Field(default_factory=list, description="提醒提案列表")


ConversationIntentType = Literal["free_chat", "structured_qa", "config_change", "memory_write", "reminder_create"]
ConversationActionType = Literal["config_change", "memory_write", "reminder_create"]


class ConversationIntentCandidateActionOutput(BaseModel):
    """意图识别阶段的候选动作"""

    action_type: ConversationActionType = Field(description="候选动作类型")
    confidence: float = Field(default=0.0, ge=0, le=1, description="动作候选置信度")
    reason: str | None = Field(default=None, description="为什么认为它像这个动作")


class ConversationIntentDetectionOutput(BaseModel):
    """聊天意图识别输出"""

    primary_intent: ConversationIntentType = Field(description="本轮主意图")
    secondary_intents: list[ConversationIntentType] = Field(default_factory=list, description="次级候选意图列表")
    confidence: float = Field(default=0.0, ge=0, le=1, description="主意图置信度")
    reason: str = Field(default="", description="判定原因，写人话")
    candidate_actions: list[ConversationIntentCandidateActionOutput] = Field(default_factory=list, description="候选动作列表")

    @field_validator("candidate_actions", mode="before")
    @classmethod
    def normalize_candidate_actions(cls, value: object) -> list[dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                action_type = str(item.get("action_type") or "").strip()
                if action_type not in {"config_change", "memory_write", "reminder_create"}:
                    continue
                normalized.append(
                    {
                        "action_type": action_type,
                        "confidence": float(item.get("confidence") or 0.0),
                        "reason": str(item.get("reason") or "").strip() or None,
                    }
                )
                continue

            if not isinstance(item, str):
                continue
            inferred = cls._infer_action_type_from_text(item)
            if inferred is None:
                continue
            normalized.append(
                {
                    "action_type": inferred,
                    "confidence": 0.0,
                    "reason": item.strip() or None,
                }
            )
        return normalized

    @staticmethod
    def _infer_action_type_from_text(text: str) -> ConversationActionType | None:
        normalized = text.strip().lower()
        if not normalized:
            return None
        if any(keyword in normalized for keyword in ("配置", "名字", "称呼", "风格", "性格", "人设", "config")):
            return "config_change"
        if any(keyword in normalized for keyword in ("记住", "记忆", "memory")):
            return "memory_write"
        if any(keyword in normalized for keyword in ("提醒", "reminder", "闹钟")):
            return "reminder_create"
        return None


class QaGenerationOutput(BaseModel):
    """问答输出（通常不需要结构化）"""

    answer: str = Field(description="回答内容")
    confidence: str | None = Field(default=None, description="置信度: high/medium/low")


class ConversationDevicePlannerToolCallOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tool_name: str = Field(
        description="本轮要调用的工具名",
        validation_alias=AliasChoices("tool_name", "name"),
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="工具调用参数",
        validation_alias=AliasChoices("arguments", "input"),
    )

    @field_validator("arguments", mode="before")
    @classmethod
    def normalize_arguments(cls, value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ConversationDevicePlannerPlanOutput(BaseModel):
    device_id: str = Field(description="最终执行设备 ID")
    entity_id: str = Field(description="最终执行实体 ID")
    action: str = Field(description="标准动作名")
    params: dict[str, Any] = Field(default_factory=dict, description="标准动作参数")
    confidence: float = Field(default=0.0, ge=0, le=1, description="规划结果置信度")
    reason: str = Field(default="", description="为什么选择这个设备和实体")
    requires_high_risk_confirmation: bool = Field(default=False, description="是否属于高风险动作")

    @field_validator("params", mode="before")
    @classmethod
    def normalize_params(cls, value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)


class ConversationDevicePlannerStepOutput(BaseModel):
    outcome: Literal["tool_call", "final_plan", "clarification", "not_found", "failed"] = Field(
        description="本轮规划结果类型"
    )
    reason: str = Field(default="", description="人话解释")
    tool_call: ConversationDevicePlannerToolCallOutput | None = Field(default=None, description="待执行工具调用")
    final_plan: ConversationDevicePlannerPlanOutput | None = Field(default=None, description="最终执行计划")
    clarification_question: str | None = Field(default=None, description="需要追问用户时的问题")
    suggestions: list[str] = Field(default_factory=list, description="可直接提示给用户的候选建议")

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_step_reason(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("clarification_question", mode="before")
    @classmethod
    def normalize_clarification_question(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("suggestions", mode="before")
    @classmethod
    def normalize_suggestions(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                normalized.append(text)
        return normalized
