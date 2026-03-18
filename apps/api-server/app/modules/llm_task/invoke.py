"""LLM 任务统一调用"""

from collections.abc import AsyncGenerator
import logging
from typing import Any, cast

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.modules.ai_gateway import repository as ai_gateway_repo
from app.modules.ai_gateway.gateway_service import ainvoke_capability, build_invocation_plan, invoke_capability
from app.modules.ai_gateway.provider_runtime import stream_provider_invoke
from app.modules.ai_gateway.schemas import AiCapability, AiGatewayInvokeRequest
from app.modules.llm_task.definitions import get_task
from app.modules.llm_task.parser import parse_to_model, strip_structured_output

logger = logging.getLogger(__name__)


class LlmResult:
    """LLM 调用结果"""

    def __init__(
        self,
        raw_text: str,
        display_text: str,
        parsed: BaseModel | None = None,
        latency_ms: int = 0,
        provider: str = "",
    ):
        self.raw_text = raw_text
        self.display_text = display_text
        self.parsed = parsed
        self.latency_ms = latency_ms
        self.provider = provider

    @property
    def text(self) -> str:
        """获取可直接展示的文本。"""
        return self.display_text

    @property
    def data(self) -> BaseModel | None:
        """获取解析后的结构化数据"""
        return self.parsed

    def __repr__(self) -> str:
        return f"LlmResult(text={self.display_text[:50]!r}..., parsed={self.parsed is not None})"


class LlmStreamEvent:
    """流式调用事件。"""

    def __init__(
        self,
        event_type: str,
        *,
        content: str = "",
        parsed: BaseModel | None = None,
        result: LlmResult | None = None,
    ):
        self.event_type = event_type
        self.content = content
        self.parsed = parsed
        self.result = result


def invoke_llm(
    db: Session,
    task_type: str,
    variables: dict[str, Any],
    *,
    household_id: str | None = None,
    conversation_history: list[dict] | None = None,
    request_context: dict[str, Any] | None = None,
    timeout_ms_override: int | None = None,
    honor_timeout_override: bool = False,
) -> LlmResult:
    """调用 LLM 执行任务

    Args:
        db: 数据库会话
        task_type: 任务类型（在 definitions.py 中定义）
        variables: 提示词变量，用于 .format() 替换
        household_id: 家庭ID（用于路由）
        conversation_history: 对话历史（多轮对话场景）

    Returns:
        LlmResult: 包含原始文本和解析后的结构化数据

    Example:
        result = invoke_llm(
            db,
            "butler_bootstrap",
            {
                "collected_info": "暂无",
                "user_message": "你好",
            },
            household_id=household_id,
            conversation_history=previous_messages,
        )

        print(result.text)  # AI 的文本回复
        if result.data:     # 解析出的结构化数据
            print(result.data.display_name)
    """
    task = get_task(task_type)
    messages = task.build_messages(variables, conversation_history)

    # 调用 AI Gateway
    response = invoke_capability(
        db,
        AiGatewayInvokeRequest(
            capability=task.capability,
            household_id=household_id,
            payload={
                "task_type": task_type,
                "messages": messages,
                "temperature": task.temperature,
                "max_tokens": task.max_tokens,
                "request_context": request_context or {},
            },
            timeout_ms_override=timeout_ms_override,
            honor_timeout_override=honor_timeout_override,
        ),
    )

    raw_text = str(response.normalized_output.get("text", "") or "")
    result = _build_result(
        raw_text=raw_text,
        provider=response.provider_code,
        latency_ms=response.attempts[-1].latency_ms or 0 if response.attempts else 0,
        output_model=task.output_model,
        task_type=task_type,
    )

    return result


async def ainvoke_llm(
    db: Session,
    task_type: str,
    variables: dict[str, Any],
    *,
    household_id: str | None = None,
    conversation_history: list[dict] | None = None,
    request_context: dict[str, Any] | None = None,
    timeout_ms_override: int | None = None,
    honor_timeout_override: bool = False,
) -> LlmResult:
    task = get_task(task_type)
    messages = task.build_messages(variables, conversation_history)

    response = await ainvoke_capability(
        db,
        AiGatewayInvokeRequest(
            capability=task.capability,
            household_id=household_id,
            payload={
                "task_type": task_type,
                "messages": messages,
                "temperature": task.temperature,
                "max_tokens": task.max_tokens,
                "request_context": request_context or {},
            },
            timeout_ms_override=timeout_ms_override,
            honor_timeout_override=honor_timeout_override,
        ),
    )

    raw_text = str(response.normalized_output.get("text", "") or "")
    return _build_result(
        raw_text=raw_text,
        provider=response.provider_code,
        latency_ms=response.attempts[-1].latency_ms or 0 if response.attempts else 0,
        output_model=task.output_model,
        task_type=task_type,
    )


async def stream_llm(
    db: Session,
    task_type: str,
    variables: dict[str, Any],
    *,
    household_id: str | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    request_context: dict[str, Any] | None = None,
) -> AsyncGenerator[LlmStreamEvent, None]:
    """流式调用 LLM 任务。"""
    task = get_task(task_type)
    messages = task.build_messages(variables, conversation_history)

    provider_profile, timeout_ms = _resolve_stream_provider(
        db,
        capability=task.capability,
        household_id=household_id,
        request_context=request_context,
    )

    full_text = ""
    sent_display_length = 0
    last_parsed_dump: dict[str, Any] | list[Any] | None = None

    async for chunk in stream_provider_invoke(
        provider_profile=provider_profile,
        payload={
            "messages": messages,
            "temperature": task.temperature,
            "max_tokens": task.max_tokens,
            "request_context": request_context or {},
        },
        timeout_ms=timeout_ms,
    ):
        full_text += cast(str, chunk)

        display_text = strip_structured_output(full_text)
        if len(display_text) > sent_display_length:
            new_content = display_text[sent_display_length:]
            sent_display_length = len(display_text)
            if new_content:
                yield LlmStreamEvent("chunk", content=new_content)

        if task.output_model:
            parsed = parse_to_model(full_text, task.output_model)
            if parsed is not None:
                parsed_dump = parsed.model_dump(mode="json")
                if parsed_dump != last_parsed_dump:
                    last_parsed_dump = parsed_dump
                    yield LlmStreamEvent("parsed", parsed=parsed)

    yield LlmStreamEvent(
        "done",
        result=_build_result(
            raw_text=full_text,
            provider=provider_profile.provider_code,
            latency_ms=0,
            output_model=task.output_model,
            task_type=task_type,
        ),
    )


def _build_result(
    *,
    raw_text: str,
    provider: str,
    latency_ms: int,
    output_model: type[BaseModel] | None,
    task_type: str,
) -> LlmResult:
    parsed = parse_to_model(raw_text, output_model) if output_model else None
    if output_model is not None and parsed is None and raw_text.strip():
        logger.warning(
            "LLM structured parse failed: task_type=%s provider=%s raw_text_preview=%s",
            task_type,
            provider,
            raw_text[:500],
        )
    return LlmResult(
        raw_text=raw_text,
        display_text=strip_structured_output(raw_text),
        parsed=parsed,
        latency_ms=latency_ms,
        provider=provider,
    )


def _resolve_stream_provider(
    db: Session,
    *,
    capability: AiCapability,
    household_id: str | None,
    request_context: dict[str, Any] | None,
):
    plan = build_invocation_plan(
        db,
        capability=cast(AiCapability, capability),
        household_id=household_id,
        request_payload={"request_context": request_context or {}},
    )
    if plan.primary_provider is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=plan.blocked_reason or "当前能力没有可用主提供商")

    provider_profile = ai_gateway_repo.get_provider_profile(db, plan.primary_provider.provider_profile_id)
    if provider_profile is None or not provider_profile.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前主提供商不可用")
    return provider_profile, plan.timeout_ms
