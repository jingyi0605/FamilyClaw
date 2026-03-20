from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json

from app.modules.ai_gateway.schemas import AiCapability


@dataclass(frozen=True)
class ProviderInvokeResult:
    provider_code: str
    model_name: str
    latency_ms: int
    finish_reason: str
    normalized_output: dict[str, object]
    raw_response_ref: str | None


class ProviderRuntimeError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def build_template_fallback_output(
    *,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> dict[str, object]:
    task_type = str(payload.get("task_type") or "").strip()
    if task_type == "conversation_intent_detection":
        return {
            "text": json.dumps(
                {
                    "primary_intent": "free_chat",
                    "secondary_intents": [],
                    "confidence": 0.0,
                    "reason": "意图识别已降级，先按 free_chat 保守处理。",
                    "candidate_actions": [],
                },
                ensure_ascii=False,
            ),
            "mode": "template_fallback",
        }
    if task_type == "free_chat":
        user_message = str(payload.get("user_message") or "").strip()
        if user_message in {"你好", "哈喽", "嗨", "hello", "hi", "您好"}:
            text = "你好，我在。刚才响应有点慢，但现在可以继续聊。"
        else:
            text = "我还在，只是刚才模型响应有点慢。你可以继续说，我会尽量直接回答。"
        return {
            "text": text,
            "mode": "template_fallback",
        }
    if capability == "text":
        text_task_kind = _resolve_text_task_kind(payload)
        if text_task_kind == "reminder_copywriting":
            title = str(payload.get("title") or "提醒")
            return {
                "text": f"{title}：请按计划处理。",
                "mode": "template_fallback",
            }
        if text_task_kind == "scene_explanation":
            scene_name = str(payload.get("scene_name") or "当前场景")
            return {
                "text": f"{scene_name} 当前使用模板解释，具体执行将按受控步骤处理。",
                "mode": "template_fallback",
            }

        question = str(payload.get("question") or "当前问题")
        agent_name = _read_agent_name_from_payload(payload)
        memory_summary = _read_agent_memory_summary(payload)
        return {
            "text": f"{agent_name}当前进入模板回答模式，先返回保守结论：{question} 需要结合结构化事实进一步确认。{memory_summary}",
            "mode": "template_fallback",
        }
    return {
        "text": "当前能力进入模板降级模式。",
        "mode": "template_fallback",
    }


def _should_fail(
    *,
    extra_config: dict[str, object],
    payload: Mapping[str, object],
    capability: AiCapability,
    provider_code: str,
) -> bool:
    if bool(extra_config.get("simulate_failure")):
        return True
    raw_fail_capabilities = extra_config.get("simulate_fail_capabilities")
    fail_capabilities = {str(item) for item in raw_fail_capabilities} if isinstance(raw_fail_capabilities, list) else set()
    if capability in fail_capabilities:
        return True
    raw_payload_failures = payload.get("_simulate_fail_provider_codes")
    payload_failures = {str(item) for item in raw_payload_failures} if isinstance(raw_payload_failures, list) else set()
    return provider_code in payload_failures


def _resolve_text_task_kind(payload: Mapping[str, object]) -> str:
    task_type = str(payload.get("task_type") or "").strip()
    if task_type in {"reminder_copywriting", "scene_explanation"}:
        return task_type
    if "title" in payload and "question" not in payload and "scene_name" not in payload:
        return "reminder_copywriting"
    if "scene_name" in payload:
        return "scene_explanation"
    return "general_text"


def _read_agent_name_from_payload(payload: Mapping[str, object]) -> str:
    runtime_context = payload.get("agent_runtime_context")
    if not isinstance(runtime_context, Mapping):
        return ""
    agent = runtime_context.get("agent")
    if not isinstance(agent, Mapping):
        return ""
    agent_name = str(agent.get("name") or "").strip()
    if not agent_name:
        return ""
    return f"{agent_name}："


def _read_agent_memory_summary(payload: Mapping[str, object]) -> str:
    memory_context = payload.get("agent_memory_context")
    if not isinstance(memory_context, Mapping):
        return ""
    summary = str(memory_context.get("summary") or "").strip()
    if not summary:
        return ""
    return f" 当前记忆视角：{summary}"
