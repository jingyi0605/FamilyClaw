"""LLM 结构化输出模型定义"""

from typing import Any
from pydantic import BaseModel, Field


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


class QaGenerationOutput(BaseModel):
    """问答输出（通常不需要结构化）"""

    answer: str = Field(description="回答内容")
    confidence: str | None = Field(default=None, description="置信度: high/medium/low")
