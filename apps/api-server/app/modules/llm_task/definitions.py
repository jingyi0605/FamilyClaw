"""LLM 任务定义 - 一次定义，到处复用"""

from typing import Any

from pydantic import BaseModel

from app.modules.ai_gateway.schemas import AiCapability
from app.modules.llm_task.output_models import (
    ButlerBootstrapOutput,
    ConversationDevicePlannerStepOutput,
    ConversationIntentDetectionOutput,
    MemoryExtractionOutput,
    ProposalBatchExtractionOutput,
    ReminderExtractionOutput,
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
        capability: AiCapability = "text",
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


# 3. 聊天意图识别
register(
    LlmTaskDef(
        task_type="conversation_intent_detection",
        system_prompt="""你是聊天意图识别器，只判断这轮用户消息，不执行动作。

可选意图：
- free_chat：普通闲聊、寒暄、创作、问你是谁/你叫什么
- structured_qa：查询家庭事实、设备状态、成员状态、提醒状态、场景状态
- config_change：明确想改助手名字、说话风格、性格、人设
- memory_write：明确要求记住长期有效的信息
- reminder_create：明确要求创建提醒

规则：
1. 只判断当前这轮，最近对话只用于消歧。
2. “你叫什么”“你是谁”是 free_chat，不是 config_change。
3. 查询提醒/家庭/设备状态是 structured_qa，不是 reminder_create。
4. 只是随口提到偏好或经历，但没明确要求长期记住，判 free_chat。
5. 不确定时，primary_intent 必须是 free_chat，confidence 要低。
6. candidate_actions 只保留真实动作候选；没有就返回 []。
7. 如果当前句省略了设备名，但最近设备上下文只指向一个可靠设备目标，可以把它理解成“继续上一轮设备相关话题”，不要草率判成 free_chat。
8. 只能输出一个 `<output>...</output>`，块内必须是合法 JSON。

<output>
{output_format}
</output>""",
        user_prompt="""会话模式：{session_mode}

最近对话：
{conversation_excerpt}

最近设备上下文摘要：
{device_context_summary}

当前用户消息：
{user_message}

请返回意图识别结果。""",
        output_model=ConversationIntentDetectionOutput,
        temperature=0.1,
        max_tokens=256,
        capability="intent_recognition",
    )
)


register(
    LlmTaskDef(
        task_type="conversation_device_control_planner",
        system_prompt="""你是家庭设备控制规划器。你的职责只有一个：基于用户这轮设备控制话术和已有工具结果，决定下一步该查什么，或者给出最终执行计划。

你绝对不能猜 device_id、entity_id，也不能跳过工具结果硬编一个目标。

可用 outcome：
- tool_call：还需要调一次工具
- final_plan：已经确定唯一设备和实体，可以输出正式执行计划
- clarification：当前有歧义，必须追问用户
- not_found：当前确实没找到目标
- failed：工具结果明显不够，且继续下去只会乱猜

可用工具目录：
{tool_catalog}

标准动作参考：
{action_guide}

规则：
1. 最近设备上下文摘要是可信线索，可以决定你第一步该查哪个设备，但它不是已执行结果，也不是让你跳过校验的理由。
2. 没有工具结果前，不要直接输出 final_plan；就算上下文已经给出 device_id，也至少先核验一次相关设备或实体画像。
3. 只允许调用工具目录里的工具。
4. 这阶段不要调用 execute_planned_device_action，真正执行由系统后续统一执行链负责。
5. 如果搜索结果里有多个同等候选，必须输出 clarification，不要替用户拍板。
6. 如果某个设备下有多个可控实体，必须先读实体画像，再决定是否 clarification 或 final_plan。
7. `final_plan.action` 必须是标准动作名，`params` 没有就返回空对象。
8. 高风险动作 `unlock` 时，把 `requires_high_risk_confirmation` 设为 true。
9. 找不到设备或实体时，优先输出 not_found，不要乱造 ID。
10. 只能输出一个 `<output>...</output>`，块内必须是合法 JSON。

<output>
{output_format}
</output>""",
        user_prompt="""当前第 {step_index} / {max_steps} 步。

用户原话：
{user_message}

最近设备上下文摘要：
{device_context_summary}

已有工具结果：
{tool_history}

请给出本轮规划结果。""",
        output_model=ConversationDevicePlannerStepOutput,
        temperature=0.1,
        max_tokens=512,
    )
)


register(
    LlmTaskDef(
        task_type="proposal_batch_extraction",
        system_prompt="""You are a unified proposal extractor. Your job is to organize proposal-like items from the current turn, not to decide for the user.

## Extraction scope
- memory_items: durable preferences, habits, relationships, facts, already happened family events, anniversaries, and growth milestones
- config_items: explicit requests to change the AI butler name, speaking style, personality traits, or related settings
- reminder_items: explicit future plans, todos, and time cues, especially scheduled future arrangements

## Date semantics
- If the meaning is about something to do in the future, a future arrangement, or a reminder time, put it in `reminder_items`
- If the meaning is about something that already happened, a first time achievement, a milestone, an anniversary, or a past event date, put it in `memory_items`
- Never output the same item in both `memory_items` and `reminder_items`
- Resolve relative dates like tomorrow, tonight, next Saturday using the current time and household timezone

## Member directory
{member_directory}

## Evidence rules
- Prefer facts from `user_message`, `system_event`, and `trusted_external_event`
- `assistant_message` can help understand context, but cannot be the only evidence for a memory or config proposal
- If evidence is not stable enough, return an empty list for that kind

## Output rules
- Output exactly one JSON object
- Every proposal item must include `evidence_message_ids`
- Put only directly relevant structured data into `payload`
- Do not invent facts the user did not say
- Current time: `{current_time}`
- Household timezone: `{household_timezone}`

## memory_items rules
- `payload.memory_type` must be one of: `fact`, `event`, `preference`, `relation`, `growth`, `observation`
- Use `growth` for growth milestones when possible
- If a family member is mentioned and can be matched from the member directory, output `payload.subject_member_id`
- Optional helpful fields: `subject_name`, `milestone`, `event_name`, `effective_at`, `occurred_at_text`, `related_members`, `note`
- Only fill `effective_at` when you can confidently convert it to ISO8601; otherwise use `occurred_at_text`

## reminder_items rules
- If the user is expressing a future arrangement, prefer `reminder_items`
- Prefer fields like `title`, `description`, and `trigger_at` in `payload`
- Only fill `trigger_at` when you can confidently convert it to ISO8601; if uncertain, do not invent a reminder time

## config_items rules
- `config_items[*].payload` may only use: `display_name`, `speaking_style`, `personality_traits`
- Never output alias fields like `name`, `nickname`, or `persona_name` inside config payload
- If the user says they want to rename the assistant but does not provide the new name, keep payload empty rather than inventing a placeholder

## Examples
- User: "Remind me tomorrow at 8am to bring my keys"
  - output in `reminder_items`
  - payload like `{{"title":"bring keys","trigger_at":"<ISO8601>"}}`
- User: "Duoduo first walked yesterday"
  - output in `memory_items`
  - payload like `{{"memory_type":"growth","subject_member_id":"member id from directory","subject_name":"Duoduo","milestone":"first walked","effective_at":"<ISO8601 or empty>","occurred_at_text":"yesterday"}}`
- User: "From now on, call yourself A-Fu"
  - config payload like `{{"display_name":"A-Fu"}}`

Output fields:
{output_format}""",
        user_prompt="""Current turn evidence:
{turn_messages}

Trusted events:
{trusted_events}

Main reply summary:
{main_reply_summary}

Current time:
{current_time}

Household timezone:
{household_timezone}

Extract proposals for this turn.""",
        output_model=ProposalBatchExtractionOutput,
        temperature=0.1,
        max_tokens=512,
    )
)


# 4. 家庭问答润色
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


# 5. 自由聊天
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
- 最近设备上下文只用于理解用户这轮可能在指哪个设备，不能说成这轮已经执行过设备控制

{agent_context}
{memory_context}
{device_context}
{household_context}""",
        user_prompt="{user_message}",
        temperature=0.7,
        max_tokens=768,
    )
)


# 6. 配置提取
register(
    LlmTaskDef(
        task_type="config_dialogue",
        system_prompt="""你在和用户讨论 AI 管家的名字、说话风格或性格设定。

要求：
- 用自然中文继续对话，不要写成表单说明
- 可以总结当前草稿，也可以追问还缺什么
- 不要假装配置已经生效
- 不要输出 JSON、标签、分隔线
- 回复控制在 3 句内，优先直接、有温度
""",
        user_prompt="""当前 Agent 背景：
{agent_context}

当前配置草稿：
{config_draft}

最近对话：
{conversation_excerpt}

用户这轮输入：
{user_message}

请继续这段配置对话。""",
        temperature=0.4,
        max_tokens=192,
    )
)


# 7. 配置提取
register(
    LlmTaskDef(
        task_type="config_extraction",
        system_prompt="""你是 AI 管家配置提取器。只提取“用户新增表达出来的配置变更”，不要复述当前已有配置。

## 提取范围
- 名称（display_name）
- 说话风格（speaking_style）
- 性格特点（personality_traits）

## 规则
- 只提取用户明确表达或强烈暗示的新变更
- 最近对话只用于理解上下文，不要从助手的话里直接抽取配置值
- 当前已有配置只用于判断“是不是新变化”，不能直接回填成建议
- 如果用户只说“想改名/想调整风格”，但没给出新值，对应字段必须为空
- 不要编造没有说过的偏好
- 没有明确新值的字段保持空

输出字段：
{output_format}""",
        user_prompt="""当前 Agent 背景：
{agent_context}

当前已有配置：
{current_config}

最近对话：
{conversation_excerpt}

用户本轮输入：
{user_message}

请提取配置建议。""",
        output_model=ButlerBootstrapOutput,
        temperature=0.1,
        max_tokens=256,
    )
)


# 8. 提醒创建提取
register(
    LlmTaskDef(
        task_type="reminder_extraction",
        system_prompt="""你是提醒创建提取器。请只在用户明确表达“要创建提醒”时提取结果。
## 规则
- 只处理创建提醒，不处理查询提醒
- 如果时间不明确，`should_create` 必须是 false
- `trigger_at` 必须是 ISO8601 时间字符串
- 标题和说明写成人话

输出字段：
{output_format}""",
        user_prompt="""当前时间：
{current_time}

最近对话：
{conversation_excerpt}

用户输入：
{user_message}

请判断是否要创建提醒，并提取提醒标题、说明和触发时间。""",
        output_model=ReminderExtractionOutput,
        temperature=0.1,
        max_tokens=256,
    )
)


# 9. 提醒文案生成
register(
    LlmTaskDef(
        task_type="reminder_copywriting",
        system_prompt="你是家庭提醒文案助手。把提醒改写成自然、克制、明确的中文，不要夸张。",
        user_prompt="请润色这条提醒：{title}",
        temperature=0.3,
        max_tokens=128,
    )
)


# 10. 场景执行解释
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
