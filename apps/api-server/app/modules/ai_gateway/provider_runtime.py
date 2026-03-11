from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
import socket
from time import perf_counter
from urllib import error, request

from app.core.config import settings
from app.db.utils import load_json
from app.modules.ai_gateway.models import AiProviderProfile
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


class ProviderAdapter:
    transport_type: str

    def __init__(self, transport_type: str):
        self.transport_type = transport_type

    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
    ) -> ProviderInvokeResult:
        extra_config = load_json(provider_profile.extra_config_json) or {}
        if _should_fail(
            extra_config=extra_config,
            payload=payload,
            capability=capability,
            provider_code=provider_profile.provider_code,
        ):
            error_code = str(extra_config.get("simulate_error_code") or "provider_failed")
            raise ProviderRuntimeError(error_code, f"{provider_profile.provider_code} simulated failure")

        if self.transport_type in {"openai_compatible", "local_gateway"}:
            return _invoke_openai_compatible(
                capability=capability,
                provider_profile=provider_profile,
                payload=payload,
                timeout_ms=timeout_ms,
            )

        return _invoke_simulated(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )


def get_provider_adapter(transport_type: str) -> ProviderAdapter | None:
    if transport_type not in {"openai_compatible", "native_sdk", "local_gateway"}:
        return None
    return ProviderAdapter(transport_type=transport_type)


def build_template_fallback_output(
    *,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> dict[str, object]:
    if capability == "qa_generation":
        question = str(payload.get("question") or "当前问题")
        agent_name = _read_agent_name_from_payload(payload)
        memory_summary = _read_agent_memory_summary(payload)
        return {
            "text": f"{agent_name}当前进入模板回答模式，先返回保守结论：{question} 需要结合结构化事实进一步确认。{memory_summary}",
            "mode": "template_fallback",
        }
    if capability == "reminder_copywriting":
        title = str(payload.get("title") or "提醒")
        return {
            "text": f"{title}：请按计划处理。",
            "mode": "template_fallback",
        }
    if capability == "scene_explanation":
        scene_name = str(payload.get("scene_name") or "当前场景")
        return {
            "text": f"{scene_name} 当前使用模板解释，具体执行将按受控步骤处理。",
            "mode": "template_fallback",
        }
    return {
        "text": "当前能力进入模板降级模式。",
        "mode": "template_fallback",
    }


def _invoke_openai_compatible(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
) -> ProviderInvokeResult:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    endpoint = _resolve_chat_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的接口地址")

    messages = _build_messages(capability=capability, payload=payload)
    request_body: dict[str, object] = {
        "model": model_name,
        "messages": messages,
        "temperature": extra_config.get("temperature", 0.2),
        "stream": False,
    }
    if "max_tokens" in extra_config:
        request_body["max_tokens"] = extra_config["max_tokens"]
    else:
        request_body["max_tokens"] = _default_max_tokens_for_capability(capability)
    if isinstance(extra_config.get("default_request_body"), dict):
        request_body = {
            **extra_config["default_request_body"],
            **request_body,
        }

    _apply_provider_specific_defaults(
        request_body=request_body,
        provider_profile=provider_profile,
        model_name=model_name,
        capability=capability,
    )

    request_headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    custom_headers = extra_config.get("headers")
    if isinstance(custom_headers, dict):
        request_headers.update({str(key): str(value) for key, value in custom_headers.items()})

    try:
        effective_timeout_ms = _resolve_effective_timeout_ms(
            provider_profile=provider_profile,
            extra_config=extra_config,
            requested_timeout_ms=timeout_ms,
        )
        raw_request = request.Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        with request.urlopen(raw_request, timeout=effective_timeout_ms / 1000) as response:
            response_text = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ProviderRuntimeError(_map_http_status_to_error_code(exc.code), detail or str(exc)) from exc
    except socket.timeout as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            raise ProviderRuntimeError("timeout", "provider request timeout") from exc
        raise ProviderRuntimeError("provider_failed", str(exc.reason)) from exc
    except TimeoutError as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError("validation_error", "provider returned invalid json") from exc

    normalized_text = _extract_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_finish_reason(response_json)
    return ProviderInvokeResult(
        provider_code=provider_profile.provider_code,
        model_name=response_model_name,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        normalized_output={
            "text": normalized_text,
            "provider_code": provider_profile.provider_code,
            "model_name": response_model_name,
        },
        raw_response_ref=f"http://{provider_profile.provider_code}/chat-completions",
    )


def _invoke_simulated(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
) -> ProviderInvokeResult:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    normalized_output = _build_simulated_output(
        capability=capability,
        provider_code=provider_profile.provider_code,
        model_name=model_name,
        payload=payload,
    )
    latency_ms = max(int((perf_counter() - started_at) * 1000), int(extra_config.get("simulate_latency_ms") or 5))
    return ProviderInvokeResult(
        provider_code=provider_profile.provider_code,
        model_name=model_name,
        latency_ms=latency_ms,
        finish_reason="stop",
        normalized_output=normalized_output,
        raw_response_ref=f"simulated://{provider_profile.provider_code}/{capability}",
    )


def _resolve_model_name(provider_profile: AiProviderProfile) -> str:
    extra_config = load_json(provider_profile.extra_config_json) or {}
    return str(
        extra_config.get("model_name")
        or extra_config.get("default_model")
        or provider_profile.api_version
        or provider_profile.provider_code
    )


def _resolve_provider_secret(
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
) -> str | None:
    secret_ref = provider_profile.secret_ref
    if secret_ref:
        if secret_ref.startswith(settings.ai_runtime.secret_ref_prefix):
            env_key = secret_ref[len(settings.ai_runtime.secret_ref_prefix):]
            secret_value = os.getenv(env_key)
            if secret_value:
                return secret_value
        else:
            secret_value = os.getenv(secret_ref)
            if secret_value:
                return secret_value
            return secret_ref

    runtime_config = settings.ai_runtime.provider_configs.get(provider_profile.provider_code)
    if runtime_config and runtime_config.secret_env_var:
        secret_value = os.getenv(runtime_config.secret_env_var)
        if secret_value:
            return secret_value

    env_key_from_extra = extra_config.get("secret_env_var")
    if isinstance(env_key_from_extra, str):
        secret_value = os.getenv(env_key_from_extra)
        if secret_value:
            return secret_value

    if provider_profile.transport_type == "local_gateway" or bool(extra_config.get("allow_anonymous")):
        return None

    raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的密钥")


def _resolve_chat_endpoint(
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
) -> str:
    endpoint = str(extra_config.get("chat_completions_url") or provider_profile.base_url or "").strip()
    if not endpoint:
        runtime_config = settings.ai_runtime.provider_configs.get(provider_profile.provider_code)
        endpoint = (runtime_config.base_url or "").strip() if runtime_config else ""
    if not endpoint:
        return ""
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return endpoint.rstrip("/") + "/chat/completions"


def _default_max_tokens_for_capability(capability: AiCapability) -> int:
    if capability == "qa_generation":
        return 256
    if capability == "scene_explanation":
        return 256
    if capability == "reminder_copywriting":
        return 128
    return 256


def _apply_provider_specific_defaults(
    *,
    request_body: dict[str, object],
    provider_profile: AiProviderProfile,
    model_name: str,
    capability: AiCapability,
) -> None:
    base_url = (provider_profile.base_url or "").lower()
    normalized_model_name = model_name.lower()

    is_siliconflow = "siliconflow.cn" in base_url
    is_qwen_reasoning_model = "qwen/" in normalized_model_name or normalized_model_name.startswith("qwen/")

    if is_siliconflow and is_qwen_reasoning_model:
        request_body.setdefault("enable_thinking", False)
        if capability == "qa_generation":
            request_body["max_tokens"] = min(int(request_body.get("max_tokens") or 256), 256)
        elif capability in {"scene_explanation", "reminder_copywriting"}:
            request_body["max_tokens"] = min(int(request_body.get("max_tokens") or 128), 128)


def _resolve_effective_timeout_ms(
    *,
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
    requested_timeout_ms: int | None,
) -> int:
    runtime_config = settings.ai_runtime.provider_configs.get(provider_profile.provider_code)
    candidates = [
        int(value)
        for value in [
            requested_timeout_ms,
            provider_profile.latency_budget_ms,
            runtime_config.timeout_ms if runtime_config else None,
            extra_config.get("timeout_ms"),
        ]
        if isinstance(value, int) and value > 0
    ]
    timeout_ms = max(candidates) if candidates else 15000

    if provider_profile.transport_type == "openai_compatible" and provider_profile.privacy_level != "local_only":
        timeout_ms = max(timeout_ms, 60000)

    return timeout_ms


def _build_messages(
    *,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> list[dict[str, str]]:
    if capability == "qa_generation":
        answer_draft = str(payload.get("answer_draft") or "")
        question = str(payload.get("question") or "")
        agent_prompt = _build_agent_prompt(payload)
        memory_prompt = _build_agent_memory_prompt(payload)
        return [
            {
                "role": "system",
                "content": f"你是家庭服务助手。请基于提供的结构化事实，用中文输出简洁、可靠、可解释的回答。不要编造事实。{agent_prompt}{memory_prompt}",
            },
            {
                "role": "user",
                "content": f"用户问题：{question}\n当前规则回答草稿：{answer_draft}\n请在不改变事实的前提下润色成自然中文。",
            },
        ]
    if capability == "reminder_copywriting":
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
    if capability == "scene_explanation":
        scene_name = str(payload.get("scene_name") or "当前场景")
        blocked_guards = payload.get("blocked_guards") or []
        return [
            {
                "role": "system",
                "content": "你是家庭场景解释助手。请用中文解释场景为什么执行或为什么被阻断，保持保守清晰。",
            },
            {
                "role": "user",
                "content": f"场景名：{scene_name}\n阻断原因：{blocked_guards}\n步骤数：{payload.get('step_count') or 0}",
            },
        ]
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


def _extract_response_text(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderRuntimeError("validation_error", "provider response missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ProviderRuntimeError("validation_error", "provider response invalid choice item")
    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            if text_parts:
                return "\n".join(text_parts)
        reasoning_content = message.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            return reasoning_content
    raise ProviderRuntimeError("validation_error", "provider response missing message content")


def _extract_finish_reason(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason:
            return finish_reason
    return "stop"


def _map_http_status_to_error_code(status_code: int) -> str:
    if status_code == 408 or status_code == 504:
        return "timeout"
    if status_code == 429:
        return "rate_limited"
    if status_code == 422:
        return "validation_error"
    return "provider_failed"


def _should_fail(
    *,
    extra_config: dict[str, object],
    payload: Mapping[str, object],
    capability: AiCapability,
    provider_code: str,
) -> bool:
    if bool(extra_config.get("simulate_failure")):
        return True
    fail_capabilities = set(extra_config.get("simulate_fail_capabilities") or [])
    if capability in fail_capabilities:
        return True
    payload_failures = set(payload.get("_simulate_fail_provider_codes") or [])
    return provider_code in payload_failures


def _build_simulated_output(
    *,
    capability: AiCapability,
    provider_code: str,
    model_name: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    if capability == "qa_generation":
        question = str(payload.get("question") or "当前问题")
        agent_name = _read_agent_name_from_payload(payload)
        memory_summary = _read_agent_memory_summary(payload)
        return {
            "text": f"[{provider_code}] {agent_name}已根据结构化事实生成回答草稿：{question}{memory_summary}",
            "provider_code": provider_code,
            "model_name": model_name,
        }
    if capability == "reminder_copywriting":
        title = str(payload.get("title") or "提醒")
        return {
            "text": f"[{provider_code}] {title}，请尽快处理。",
            "provider_code": provider_code,
            "model_name": model_name,
        }
    if capability == "scene_explanation":
        scene_name = str(payload.get("scene_name") or "场景")
        return {
            "text": f"[{provider_code}] {scene_name} 将按模板步骤执行。",
            "provider_code": provider_code,
            "model_name": model_name,
        }
    return {
        "text": f"[{provider_code}] 已完成 {capability} 模拟调用。",
        "provider_code": provider_code,
        "model_name": model_name,
    }


def _build_agent_prompt(payload: Mapping[str, object]) -> str:
    runtime_context = payload.get("agent_runtime_context")
    if not isinstance(runtime_context, Mapping):
        return ""

    prompt_parts: list[str] = []
    agent = runtime_context.get("agent")
    identity = runtime_context.get("identity")
    requester_cognition = runtime_context.get("requester_member_cognition")

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
        care_notes = requester_cognition.get("care_notes")

        if display_address:
            prompt_parts.append(f"当前对用户的称呼建议：{display_address}。")
        if communication_style:
            prompt_parts.append(f"与当前用户沟通时建议采用：{communication_style}。")
        if prompt_notes:
            prompt_parts.append(f"补充注意事项：{prompt_notes}。")
        if isinstance(care_notes, Mapping) and care_notes:
            prompt_parts.append(f"成员关怀说明：{json.dumps(care_notes, ensure_ascii=False)}。")

    if not prompt_parts:
        return ""
    return "\n" + "\n".join(prompt_parts)


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


def _read_agent_memory_summary(payload: Mapping[str, object]) -> str:
    memory_context = payload.get("agent_memory_context")
    if not isinstance(memory_context, Mapping):
        return ""
    summary = str(memory_context.get("summary") or "").strip()
    if not summary:
        return ""
    return f" 当前记忆视角：{summary}"
