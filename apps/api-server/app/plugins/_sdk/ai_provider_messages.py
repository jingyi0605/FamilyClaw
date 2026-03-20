from __future__ import annotations

from collections.abc import Mapping
import json

from app.modules.ai_gateway.schemas import AiCapability


def build_messages(
    *,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> list[dict[str, str]]:
    if "messages" in payload:
        messages = payload.get("messages")
        if isinstance(messages, list) and messages:
            return list(messages)

    if capability == "text":
        text_task_kind = _resolve_text_task_kind(payload)
        if text_task_kind == "reminder_copywriting":
            title = str(payload.get("title") or "提醒")
            return [
                {
                    "role": "system",
                    "content": "你是家庭提醒文案助手。请把提醒改写成自然、克制、明确的中文，不要夸张。",
                },
                {
                    "role": "user",
                    "content": f"请润色这条提醒：{title}",
                },
            ]
        if text_task_kind == "scene_explanation":
            scene_name = str(payload.get("scene_name") or "当前场景")
            blocked_guards = payload.get("blocked_guards") or []
            return [
                {
                    "role": "system",
                    "content": "你是家庭场景解释助手。请用中文解释场景为什么执行或为什么被阻止，保持保守清晰。",
                },
                {
                    "role": "user",
                    "content": f"场景名：{scene_name}\n阻止原因：{blocked_guards}\n步骤数：{payload.get('step_count') or 0}",
                },
            ]

        answer_draft = str(payload.get("answer_draft") or "")
        question = str(payload.get("question") or "")
        agent_prompt = _build_agent_prompt(payload)
        memory_prompt = _build_agent_memory_prompt(payload)
        device_context_prompt = _build_device_context_prompt(payload)
        realtime_context_prompt = _build_realtime_context_prompt(payload)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是家庭服务助手。请基于提供的结构化事实，用中文输出简洁、可靠、可解释的回答。"
                    "不要编造事实，也不要把最近对话里的控制请求、历史动作或上下文暗示说成“这轮已经执行过”。"
                    "除非当前规则回答草稿明确包含执行结果，否则不能说“已为你打开/关闭/执行”。"
                    "同样也不能说“我这就帮你打开/关闭/执行”这类即将执行的话，因为当前链路不是设备执行链。"
                    f"{agent_prompt}{memory_prompt}{device_context_prompt}{realtime_context_prompt}"
                ),
            }
        ]
        messages.extend(_build_conversation_history_messages(payload))
        messages.append(
            {
                "role": "user",
                "content": f"用户问题：{question}\n当前规则回答草稿：{answer_draft}\n请在不改变事实的前提下润色成自然中文。",
            }
        )
        return messages

    return [
        {
            "role": "system",
            "content": "你是家庭服务 AI 助手。请根据输入返回简洁中文结果。",
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def resolve_text_task_kind(payload: Mapping[str, object]) -> str:
    return _resolve_text_task_kind(payload)


def split_system_and_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    if messages and messages[0].get("role") == "system":
        return messages[0].get("content", ""), messages[1:]
    return "", messages


def _resolve_text_task_kind(payload: Mapping[str, object]) -> str:
    task_type = str(payload.get("task_type") or "").strip()
    if task_type in {"reminder_copywriting", "scene_explanation"}:
        return task_type
    if "title" in payload and "question" not in payload and "scene_name" not in payload:
        return "reminder_copywriting"
    if "scene_name" in payload:
        return "scene_explanation"
    return "general_text"


def _build_agent_prompt(payload: Mapping[str, object]) -> str:
    runtime_context = payload.get("agent_runtime_context")
    if not isinstance(runtime_context, Mapping):
        return ""

    prompt_parts: list[str] = []
    agent = runtime_context.get("agent")
    identity = runtime_context.get("identity")
    requester_cognition = runtime_context.get("requester_member_cognition")
    requester_profile = runtime_context.get("requester_member_profile")

    if isinstance(agent, Mapping):
        agent_name = str(agent.get("name") or "").strip()
        agent_type = str(agent.get("type") or "").strip()
        if agent_name or agent_type:
            prompt_parts.append(f"当前生效角色：{agent_name or '当前Agent'}（{agent_type or 'unknown'}）。")

    if isinstance(identity, Mapping):
        role_summary = str(identity.get("role_summary") or "").strip()
        self_identity = str(identity.get("self_identity") or "").strip()
        speaking_style = str(identity.get("speaking_style") or "").strip()
        personality_traits = identity.get("personality_traits") if isinstance(identity.get("personality_traits"), list) else []
        service_focus = identity.get("service_focus") if isinstance(identity.get("service_focus"), list) else []

        if role_summary:
            prompt_parts.append(f"角色定位：{role_summary}。")
        if self_identity:
            prompt_parts.append(f"自我认知：{self_identity}。")
        if speaking_style:
            prompt_parts.append(f"说话风格：{speaking_style}。")
        if personality_traits:
            prompt_parts.append(f"性格标签：{'、'.join(str(item) for item in personality_traits if str(item).strip())}。")
        if service_focus:
            prompt_parts.append(f"服务重点：{'、'.join(str(item) for item in service_focus if str(item).strip())}。")

    if isinstance(requester_cognition, Mapping):
        display_address = str(requester_cognition.get("display_address") or "").strip()
        communication_style = str(requester_cognition.get("communication_style") or "").strip()
        prompt_notes = str(requester_cognition.get("prompt_notes") or "").strip()

        if display_address:
            prompt_parts.append(f"当前对用户的称呼建议：{display_address}。")
        if communication_style:
            prompt_parts.append(f"与当前用户沟通时建议采用：{communication_style}。")
        if prompt_notes:
            prompt_parts.append(f"补充注意事项：{prompt_notes}。")

    if isinstance(requester_profile, Mapping):
        preferred_display_name = str(requester_profile.get("preferred_display_name") or "").strip()
        if preferred_display_name:
            prompt_parts.append(
                f"Preferred user address: {preferred_display_name}. If no more specific address is configured, use this instead of the legal name."
            )

    if not prompt_parts:
        return ""
    return "\n" + "\n".join(prompt_parts)


def _build_agent_memory_prompt(payload: Mapping[str, object]) -> str:
    memory_context = payload.get("agent_memory_context")
    if not isinstance(memory_context, Mapping):
        return ""

    summary = str(memory_context.get("summary") or "").strip()
    items = memory_context.get("items")
    prompt_parts: list[str] = []

    if summary:
        prompt_parts.append(f"当前长期记忆视角：{summary}")

    if isinstance(items, list) and items:
        memory_lines: list[str] = []
        for item in items[:5]:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label") or "").strip()
            item_summary = str(item.get("summary") or "").strip()
            memory_type = str(item.get("memory_type") or "").strip()
            if label or item_summary:
                memory_lines.append(f"- {label}（{memory_type}）：{item_summary}")
        if memory_lines:
            prompt_parts.append("可参考的长期记忆：\n" + "\n".join(memory_lines))

    if not prompt_parts:
        return ""
    return "\n" + "\n".join(prompt_parts)


def _build_device_context_prompt(payload: Mapping[str, object]) -> str:
    summary_text = str(payload.get("device_context_summary_text") or "").strip()
    if not summary_text:
        return ""
    return (
        "\n最近设备上下文只用于理解用户这轮可能在指哪一个设备，不能当成这轮已经执行成功的证据。"
        "如果它和当前结构化事实冲突，以结构化事实为准。\n"
        f"{summary_text}"
    )


def _build_realtime_context_prompt(payload: Mapping[str, object]) -> str:
    summary_text = str(payload.get("realtime_context_text") or "").strip()
    if not summary_text:
        return ""
    return (
        "\n下面这段实时上下文只用于理解“今天”“现在”“今晚”“明天早上”这类相对时间表达。"
        "如果用户的问题依赖当前日期或本地时间，以这里为准。\n"
        f"{summary_text}"
    )


def _build_conversation_history_messages(payload: Mapping[str, object]) -> list[dict[str, str]]:
    raw_history = payload.get("conversation_history")
    if not isinstance(raw_history, list):
        return []

    messages: list[dict[str, str]] = []
    for item in raw_history[:12]:
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant", "system"}:
            continue
        if not content:
            continue
        messages.append({"role": role, "content": content})
    return messages
