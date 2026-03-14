"""LLM 结构化输出模型定义"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
