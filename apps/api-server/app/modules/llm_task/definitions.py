"""LLM 任务定义 - 一次定义，到处复用"""

from typing import Any

from pydantic import BaseModel

from app.modules.ai_gateway.schemas import AiCapability
from app.modules.llm_task.output_models import (
    ButlerBootstrapOutput,
    MemoryExtractionOutput,
)


class LlmTaskDef:
    """LLM 任务定义"""

    def __init__(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str | None = None,
        output_model: type[BaseModel] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
        capability: AiCapability = "qa_generation",
    ):
        self.task_type = task_type
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.output_model = output_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capability: AiCapability = capability

    def build_messages(
        self,
        variables: dict[str, Any],
        conversation_history: list[dict] | None = None,
    ) -> list[dict[str, str]]:
        """构建消息列表

        Args:
            variables: 提示词变量，用于 .format() 替换
            conversation_history: 对话历史，会插入到 system 和 user 之间

        Returns:
            OpenAI 格式的 messages 列表
        """
        messages = []

        # 渲染 system prompt
        system = self.system_prompt
        if self.output_model:
            # 自动注入输出格式说明
            format_hint = self._build_format_hint()
            system = system.replace("{output_format}", format_hint)
        try:
            system_content = system.format(**variables)
        except KeyError:
            # 允许部分变量缺失
            system_content = system.format(**{k: v for k, v in variables.items() if k in _extract_format_keys(system)})
        messages.append({"role": "system", "content": system_content})

        # 添加对话历史
        if conversation_history:
            messages.extend(conversation_history)

        # 渲染 user prompt
        if self.user_prompt:
            try:
                user_content = self.user_prompt.format(**variables)
            except KeyError:
                user_content = self.user_prompt.format(
                    **{k: v for k, v in variables.items() if k in _extract_format_keys(self.user_prompt)}
                )
            messages.append({"role": "user", "content": user_content})

        return messages

    def _build_format_hint(self) -> str:
        """根据输出模型生成格式说明"""
        if self.output_model is None:
            return ""
        schema = self.output_model.model_json_schema()
        props = schema.get("properties", {})
        fields = [f'  "{k}": <{v.get("description", v.get("type", "value"))}>' for k, v in props.items()]
        # 转义花括号，避免被 .format() 误解析
        return "{{\n" + ",\n".join(fields) + "\n}}"


def _extract_format_keys(template: str) -> set[str]:
    """提取模板中的 format 变量名"""
    import re

    return set(re.findall(r"\{(\w+)\}", template))


# ============ 任务注册表 ============

TASKS: dict[str, LlmTaskDef] = {}


def register(task: LlmTaskDef) -> LlmTaskDef:
    """注册任务定义"""
    TASKS[task.task_type] = task
    return task


# ============ 所有任务定义（一次定义的地方）============

# 1. 管家引导对话
register(
    LlmTaskDef(
        task_type="butler_bootstrap",
        system_prompt="""你是即将加入这个家庭的 AI 管家，正在通过对话了解自己的身份。

## 你的服务对象
{user_context}

## 目标
通过简短自然的对话了解以下信息（关于你自己）：
- 你的名字（display_name）
- 你的说话风格（speaking_style）- 比如：幽默风趣、温柔体贴、干练高效
- 你的性格特点（personality_traits）- 至少2个，比如：细心、乐观、沉稳

## 对话规则
1. 用温暖、自然的方式与用户对话，保持简洁
2. 每次只问一个问题，2-3 轮对话内完成收集
3. 只输出用户会直接看到的自然中文回复，不要输出 JSON、标签、分隔线、配置块或任何给程序看的隐藏协议。
4. 如果信息还没收齐，就继续问下一个最关键的问题；如果已经基本收齐，就用一句自然的话提醒用户可以确认或补充修改。

## 已收集的管家信息
{collected_info}""",
        user_prompt="{user_message}",
        temperature=0.7,
        max_tokens=512,
    )
)


register(
    LlmTaskDef(
        task_type="butler_bootstrap_extract",
        system_prompt="""你是结构化提取器。请根据这轮初始化对话内容，提取 AI 管家的结构化状态。

输出规则：
1. 只输出一个 JSON 对象
2. 不要输出解释、标签、代码块或分隔线
3. 未确认的字段用空字符串或空数组
4. personality_traits 只保留简洁中文标签，去重后最多 5 个

输出字段：
{output_format}""",
        user_prompt="""当前草稿：{collected_info}
用户本轮输入：{user_message}
AI 本轮回复：{assistant_message}

请提取最新草稿。""",
        output_model=ButlerBootstrapOutput,
        temperature=0.1,
        max_tokens=256,
    )
)


# 2. 记忆卡片提取
register(
    LlmTaskDef(
        task_type="memory_extraction",
        system_prompt="""你是一个记忆提取助手。从对话中提取值得长期记住的信息。

## 提取规则
- 只提取有长期价值的信息（偏好、习惯、重要事件、关系变化）
- 忽略临时性、无关紧要的内容
- 如果没有值得记住的信息，输出空列表

## 输出格式
<memories>
{output_format}
</memories>

## 当前家庭成员
{member_context}""",
        user_prompt="""请从以下对话中提取记忆：

{conversation}""",
        output_model=MemoryExtractionOutput,
        temperature=0.1,  # 提取需要稳定
        max_tokens=256,
    )
)


# 3. 家庭问答润色
register(
    LlmTaskDef(
        task_type="qa_polish",
        system_prompt="""你是家庭服务助手。请基于提供的结构化事实，用中文输出简洁、可靠、可解释的回答。

## 规则
- 不要编造事实
- 如果不确定，明确说明
- 保持回答简洁

{agent_context}
{memory_context}""",
        user_prompt="""用户问题：{question}

结构化事实草稿：{answer_draft}

请润色成自然的中文回答。""",
        temperature=0.2,
        max_tokens=256,
    )
)


# 4. 自由聊天
register(
    LlmTaskDef(
        task_type="free_chat",
        system_prompt="""你是家庭 AI 管家，但当前回合优先按自由聊天来处理。

## 基本要求
- 用自然中文回复
- 允许讲故事、闲聊、创作和开放式回答
- 保持和当前 Agent 身份一致
- 不要强行把每个问题都拉回“家庭状态播报”

## 边界要求
- 如果用户问的是家庭实时状态、提醒、场景、设备、谁在家这类结构化问题，不要编造，应该提示自己会按家庭事实回答
- 如果用户请求创作内容，可以正常创作

{agent_context}
{memory_context}
{household_context}""",
        user_prompt="{user_message}",
        temperature=0.7,
        max_tokens=768,
    )
)


# 5. 配置提取
register(
    LlmTaskDef(
        task_type="config_extraction",
        system_prompt="""你是 AI 管家配置提取器。请从用户这轮表达里提取适合写入 Agent 配置的建议。

## 提取范围
- 名称（display_name）
- 说话风格（speaking_style）
- 性格特点（personality_traits）

## 规则
- 只提取用户明确表达或强烈暗示的内容
- 不要编造没有说过的偏好
- 如果没有相关内容，字段保持空

输出字段：
{output_format}""",
        user_prompt="""当前 Agent 背景：
{agent_context}

用户本轮输入：
{user_message}

请提取配置建议。""",
        output_model=ButlerBootstrapOutput,
        temperature=0.1,
        max_tokens=256,
    )
)


# 6. 提醒文案生成
register(
    LlmTaskDef(
        task_type="reminder_copywriting",
        system_prompt="你是家庭提醒文案助手。把提醒改写成自然、克制、明确的中文，不要夸张。",
        user_prompt="请润色这条提醒：{title}",
        temperature=0.3,
        max_tokens=128,
    )
)


# 7. 场景执行解释
register(
    LlmTaskDef(
        task_type="scene_explanation",
        system_prompt="你是家庭场景解释助手。用中文解释场景执行或被阻断的原因，保持保守清晰。",
        user_prompt="""场景名：{scene_name}
阻断原因：{blocked_guards}
步骤数：{step_count}

请解释这个场景的执行情况。""",
        temperature=0.2,
        max_tokens=256,
    )
)


def get_task(task_type: str) -> LlmTaskDef:
    """获取任务定义

    Args:
        task_type: 任务类型

    Returns:
        LlmTaskDef 实例

    Raises:
        ValueError: 任务类型不存在
    """
    if task_type not in TASKS:
        raise ValueError(f"未知的 LLM 任务类型: {task_type}")
    return TASKS[task_type]
