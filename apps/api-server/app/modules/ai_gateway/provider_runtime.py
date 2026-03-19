from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
import asyncio
import json
import logging
import os
import socket
from time import perf_counter
from urllib import error, request

import httpx

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


@dataclass(frozen=True)
class ProviderRequestContext:
    request_id: str
    trace_id: str
    session_id: str
    channel: str


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
        honor_timeout_override: bool = False,
    ) -> ProviderInvokeResult:
        extra_config = load_json(provider_profile.extra_config_json) or {}
        api_family = str(getattr(provider_profile, "api_family", "") or "").strip().lower()
        if _should_fail(
            extra_config=extra_config,
            payload=payload,
            capability=capability,
            provider_code=provider_profile.provider_code,
        ):
            error_code = str(extra_config.get("simulate_error_code") or "provider_failed")
            raise ProviderRuntimeError(error_code, f"{provider_profile.provider_code} simulated failure")

        if api_family == "openai_chat_completions" or self.transport_type in {"openai_compatible", "local_gateway"}:
                return _invoke_openai_compatible(
                    capability=capability,
                    provider_profile=provider_profile,
                    payload=payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                )

        if self.transport_type == "native_sdk":
            if api_family == "anthropic_messages":
                return _invoke_anthropic_messages(
                    capability=capability,
                    provider_profile=provider_profile,
                    payload=payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                )
            if api_family == "gemini_generate_content":
                return _invoke_gemini_generate_content(
                    capability=capability,
                    provider_profile=provider_profile,
                    payload=payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                )

        return _invoke_simulated(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )

    async def ainvoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> ProviderInvokeResult:
        extra_config = load_json(provider_profile.extra_config_json) or {}
        api_family = str(getattr(provider_profile, "api_family", "") or "").strip().lower()
        if _should_fail(
            extra_config=extra_config,
            payload=payload,
            capability=capability,
            provider_code=provider_profile.provider_code,
        ):
            error_code = str(extra_config.get("simulate_error_code") or "provider_failed")
            raise ProviderRuntimeError(error_code, f"{provider_profile.provider_code} simulated failure")

        if api_family == "openai_chat_completions" or self.transport_type in {"openai_compatible", "local_gateway"}:
            return await _ainvoke_openai_compatible(
                capability=capability,
                provider_profile=provider_profile,
                payload=payload,
                timeout_ms=timeout_ms,
                honor_timeout_override=honor_timeout_override,
            )

        return await asyncio.to_thread(
            self.invoke,
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
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


def _invoke_openai_compatible(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> ProviderInvokeResult:
    started_at = perf_counter()
    logger = logging.getLogger(__name__)
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
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
            honor_requested_timeout=honor_timeout_override,
        )
        logger.info(
            "[Invoke] Calling provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s",
            provider_profile.provider_code,
            model_name,
            effective_timeout_ms,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            request_context.channel,
            endpoint,
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
        logger.exception(
            "[Invoke] HTTPError provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s detail=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            exc.code,
            detail[:300],
        )
        raise ProviderRuntimeError(_map_http_status_to_error_code(exc.code), detail or str(exc)) from exc
    except socket.timeout as exc:
        logger.exception(
            "[Invoke] socket.timeout provider=%s model=%s request_id=%s trace_id=%s session_id=%s timeout_ms=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            effective_timeout_ms,
        )
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            logger.exception(
                "[Invoke] URLError timeout provider=%s model=%s request_id=%s trace_id=%s session_id=%s timeout_ms=%s",
                provider_profile.provider_code,
                model_name,
                request_context.request_id,
                request_context.trace_id,
                request_context.session_id,
                effective_timeout_ms,
            )
            raise ProviderRuntimeError("timeout", "provider request timeout") from exc
        logger.exception(
            "[Invoke] URLError provider=%s model=%s request_id=%s trace_id=%s session_id=%s reason=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            exc.reason,
        )
        raise ProviderRuntimeError("provider_failed", str(exc.reason)) from exc

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError("validation_error", "provider returned invalid json") from exc

    normalized_text = _extract_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_finish_reason(response_json)
    logger.info(
        "[Invoke] Completed provider=%s model=%s request_id=%s trace_id=%s session_id=%s total_ms=%s finish_reason=%s chars=%s",
        provider_profile.provider_code,
        response_model_name,
        request_context.request_id,
        request_context.trace_id,
        request_context.session_id,
        latency_ms,
        finish_reason,
        len(normalized_text),
    )
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


async def _ainvoke_openai_compatible(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> ProviderInvokeResult:
    started_at = perf_counter()
    logger = logging.getLogger(__name__)
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
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

    request_headers = {"Content-Type": "application/json"}
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    custom_headers = extra_config.get("headers")
    if isinstance(custom_headers, dict):
        request_headers.update({str(key): str(value) for key, value in custom_headers.items()})

    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )
    try:
        logger.info(
            "[AsyncInvoke] Calling provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s",
            provider_profile.provider_code,
            model_name,
            effective_timeout_ms,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            request_context.channel,
            endpoint,
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            response = await client.post(endpoint, json=request_body, headers=request_headers)
        response.raise_for_status()
        response_text = response.text
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        logger.exception(
            "[AsyncInvoke] HTTPError provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s detail=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            exc.response.status_code,
            detail[:300],
        )
        raise ProviderRuntimeError(_map_http_status_to_error_code(exc.response.status_code), detail or str(exc)) from exc
    except httpx.TimeoutException as exc:
        logger.exception(
            "[AsyncInvoke] timeout provider=%s model=%s request_id=%s trace_id=%s session_id=%s timeout_ms=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            effective_timeout_ms,
        )
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        logger.exception(
            "[AsyncInvoke] RequestError provider=%s model=%s request_id=%s trace_id=%s session_id=%s reason=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            str(exc),
        )
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError("validation_error", "provider returned invalid json") from exc

    normalized_text = _extract_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_finish_reason(response_json)
    logger.info(
        "[AsyncInvoke] Completed provider=%s model=%s request_id=%s trace_id=%s session_id=%s total_ms=%s finish_reason=%s chars=%s",
        provider_profile.provider_code,
        response_model_name,
        request_context.request_id,
        request_context.trace_id,
        request_context.session_id,
        latency_ms,
        finish_reason,
        len(normalized_text),
    )
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


async def _stream_openai_compatible(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
)-> AsyncIterator[str]:
    """流式调用 OpenAI 兼容 API，生成器模式"""
    logger = logging.getLogger(__name__)

    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    endpoint = _resolve_chat_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的接口地址")

    messages = _build_messages(capability="text", payload=payload)
    request_body: dict[str, object] = {
        "model": model_name,
        "messages": messages,
        "temperature": payload.get("temperature", extra_config.get("temperature", 0.7)),
        "max_tokens": payload.get("max_tokens", extra_config.get("max_tokens", 512)),
        "stream": True,
    }
    if isinstance(extra_config.get("default_request_body"), dict):
        request_body = {
            **extra_config["default_request_body"],
            **request_body,
        }

    # 应用供应商特定默认值（如关闭硅基流动 Qwen 的 think 模式）
    logger.info(
        "[Stream] Calling provider=%s model=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s body_keys=%s",
        provider_profile.provider_code,
        model_name,
        request_context.request_id,
        request_context.trace_id,
        request_context.session_id,
        request_context.channel,
        endpoint,
        list(request_body.keys()),
    )

    request_headers = {"Content-Type": "application/json"}
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    custom_headers = extra_config.get("headers")
    if isinstance(custom_headers, dict):
        request_headers.update({str(key): str(value) for key, value in custom_headers.items()})

    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )
    logger.info(
        "[Stream] Timeout provider=%s model=%s request_id=%s trace_id=%s timeout_ms=%s",
        provider_profile.provider_code,
        model_name,
        request_context.request_id,
        request_context.trace_id,
        effective_timeout_ms,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream(
                "POST",
                endpoint,
                json=request_body,
                headers=request_headers,
            ) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    logger.exception(
                        "[Stream] HTTPError provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s detail=%s",
                        provider_profile.provider_code,
                        model_name,
                        request_context.request_id,
                        request_context.trace_id,
                        request_context.session_id,
                        response.status_code,
                        detail[:300],
                    )
                    raise ProviderRuntimeError(_map_http_status_to_error_code(response.status_code), detail or response.reason_phrase)

                connected_ms = max(int((perf_counter() - started_at) * 1000), 1)
                logger.info(
                    "[Stream] Connected provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s connected_ms=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    response.status_code,
                    connected_ms,
                )
                buffer = ""
                chunk_count = 0
                yielded_char_count = 0
                first_chunk_logged = False
                first_content_ms: int | None = None
                async for chunk in response.aiter_text():
                    chunk_count += 1
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line == "data: [DONE]":
                            total_ms = max(int((perf_counter() - started_at) * 1000), 1)
                            logger.info(
                                "[Stream] Done provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunks=%s chars=%s first_content_ms=%s total_ms=%s",
                                provider_profile.provider_code,
                                model_name,
                                request_context.request_id,
                                request_context.trace_id,
                                request_context.session_id,
                                chunk_count,
                                yielded_char_count,
                                first_content_ms,
                                total_ms,
                            )
                            return
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices", [])
                        if not choices or not isinstance(choices, list):
                            continue
                        delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
                        content = delta.get("content", "") if isinstance(delta, dict) else ""
                        if not content:
                            continue
                        yielded_char_count += len(content)
                        if not first_chunk_logged:
                            first_chunk_logged = True
                            first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                            logger.info(
                                "[Stream] First content chunk provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunk_index=%s first_content_ms=%s preview=%s",
                                provider_profile.provider_code,
                                model_name,
                                request_context.request_id,
                                request_context.trace_id,
                                request_context.session_id,
                                chunk_count,
                                first_content_ms,
                                content[:80],
                            )
                        yield str(content)
    except httpx.TimeoutException as exc:
        logger.exception(
            "[Stream] timeout provider=%s model=%s request_id=%s trace_id=%s session_id=%s timeout_ms=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            effective_timeout_ms,
        )
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        logger.exception(
            "[Stream] URLError provider=%s model=%s request_id=%s trace_id=%s session_id=%s reason=%s",
            provider_profile.provider_code,
            model_name,
            request_context.request_id,
            request_context.trace_id,
            request_context.session_id,
            str(exc),
        )
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


async def stream_provider_invoke(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None = None,
    honor_timeout_override: bool = False,
) -> AsyncIterator[str]:
    """流式调用供应商 API"""
    api_family = str(getattr(provider_profile, "api_family", "") or "").strip().lower()
    transport_type = str(getattr(provider_profile, "transport_type", "") or "").strip().lower()

    if api_family == "openai_chat_completions" or transport_type in {"openai_compatible", "local_gateway"}:
        async for chunk in _stream_openai_compatible(
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk
        return

    if api_family == "anthropic_messages":
        async for chunk in _stream_anthropic_messages(
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk
        return

    if api_family == "gemini_generate_content":
        async for chunk in _stream_gemini_generate_content(
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk
        return
    raise ProviderRuntimeError(
            "stream_not_supported",
            f"{provider_profile.provider_code} 不支持流式调用，不能用于实时对话",
        )

async def _stream_anthropic_messages(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> AsyncIterator[str]:
    logger = logging.getLogger(__name__)
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缂哄皯鍙敤鐨勫瘑閽?")

    endpoint = _resolve_native_endpoint(provider_profile, extra_config, "/messages")
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缂哄皯鍙敤鐨勬帴鍙ｅ湴鍧€")

    system_prompt, messages = _split_system_and_messages(_build_messages(capability="text", payload=payload))
    request_body: dict[str, object] = {
        "model": model_name,
        "messages": [
            {"role": item["role"], "content": [{"type": "text", "text": item["content"]}]}
            for item in messages
        ],
        "max_tokens": payload.get("max_tokens", extra_config.get("max_tokens", 512)),
        "stream": True,
    }
    if system_prompt:
        request_body["system"] = system_prompt

    request_headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": str(extra_config.get("anthropic_version") or "2023-06-01"),
    }
    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream("POST", endpoint, json=request_body, headers=request_headers) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(_map_http_status_to_error_code(response.status_code), detail or response.reason_phrase)

                logger.info(
                    "[Stream] Connected provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s connected_ms=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    response.status_code,
                    max(int((perf_counter() - started_at) * 1000), 1),
                )

                yielded_char_count = 0
                event_count = 0
                first_content_ms: int | None = None
                async for event_name, data_str in _iter_sse_events(response):
                    event_count += 1
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("type") == "error":
                        raise ProviderRuntimeError("provider_failed", json.dumps(data, ensure_ascii=False))
                    content = _extract_anthropic_stream_text(data)
                    if not content:
                        continue
                    yielded_char_count += len(content)
                    if first_content_ms is None:
                        first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                        logger.info(
                            "[Stream] First content chunk provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunk_index=%s first_content_ms=%s event=%s preview=%s",
                            provider_profile.provider_code,
                            model_name,
                            request_context.request_id,
                            request_context.trace_id,
                            request_context.session_id,
                            event_count,
                            first_content_ms,
                            event_name,
                            content[:80],
                        )
                    yield content

                logger.info(
                    "[Stream] Done provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunks=%s chars=%s first_content_ms=%s total_ms=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    event_count,
                    yielded_char_count,
                    first_content_ms,
                    max(int((perf_counter() - started_at) * 1000), 1),
                )
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


async def _stream_gemini_generate_content(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> AsyncIterator[str]:
    logger = logging.getLogger(__name__)
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缂哄皯鍙敤鐨勫瘑閽?")

    endpoint_base = _resolve_native_endpoint(provider_profile, extra_config, "")
    if not endpoint_base:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缂哄皯鍙敤鐨勬帴鍙ｅ湴鍧€")

    system_prompt, messages = _split_system_and_messages(_build_messages(capability="text", payload=payload))
    endpoint = f"{endpoint_base.rstrip('/')}/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
    request_body: dict[str, object] = {
        "contents": [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in messages
        ],
        "generationConfig": {
            "temperature": payload.get("temperature", extra_config.get("temperature", 0.7)),
            "maxOutputTokens": payload.get("max_tokens", extra_config.get("max_tokens", 512)),
        },
    }
    if system_prompt:
        request_body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream("POST", endpoint, json=request_body, headers={"Content-Type": "application/json"}) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(_map_http_status_to_error_code(response.status_code), detail or response.reason_phrase)

                logger.info(
                    "[Stream] Connected provider=%s model=%s request_id=%s trace_id=%s session_id=%s status=%s connected_ms=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    response.status_code,
                    max(int((perf_counter() - started_at) * 1000), 1),
                )

                yielded_char_count = 0
                event_count = 0
                first_content_ms: int | None = None
                async for _event_name, data_str in _iter_sse_events(response):
                    event_count += 1
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    content = _extract_gemini_stream_text(data)
                    if not content:
                        continue
                    yielded_char_count += len(content)
                    if first_content_ms is None:
                        first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                        logger.info(
                            "[Stream] First content chunk provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunk_index=%s first_content_ms=%s preview=%s",
                            provider_profile.provider_code,
                            model_name,
                            request_context.request_id,
                            request_context.trace_id,
                            request_context.session_id,
                            event_count,
                            first_content_ms,
                            content[:80],
                        )
                    yield content

                logger.info(
                    "[Stream] Done provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunks=%s chars=%s first_content_ms=%s total_ms=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    event_count,
                    yielded_char_count,
                    first_content_ms,
                    max(int((perf_counter() - started_at) * 1000), 1),
                )
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


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
    latency_ms = max(int((perf_counter() - started_at) * 1000), _read_int_value(extra_config.get("simulate_latency_ms"), 5))
    return ProviderInvokeResult(
        provider_code=provider_profile.provider_code,
        model_name=model_name,
        latency_ms=latency_ms,
        finish_reason="stop",
        normalized_output=normalized_output,
        raw_response_ref=f"simulated://{provider_profile.provider_code}/{capability}",
    )


def _invoke_anthropic_messages(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> ProviderInvokeResult:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的密钥")

    endpoint = _resolve_native_endpoint(provider_profile, extra_config, "/messages")
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的接口地址")

    system_prompt, messages = _split_system_and_messages(_build_messages(capability=capability, payload=payload))
    request_body: dict[str, object] = {
        "model": model_name,
        "messages": [
            {"role": item["role"], "content": [{"type": "text", "text": item["content"]}]}
            for item in messages
        ],
        "max_tokens": _default_max_tokens_for_capability(capability),
    }
    if system_prompt:
        request_body["system"] = system_prompt

    response_json = _post_json(
        endpoint=endpoint,
        request_body=request_body,
        request_headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": str(extra_config.get("anthropic_version") or "2023-06-01"),
        },
        provider_profile=provider_profile,
        extra_config=extra_config,
        timeout_ms=timeout_ms,
        honor_timeout_override=honor_timeout_override,
    )

    normalized_text = _extract_anthropic_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    finish_reason = str(response_json.get("stop_reason") or "stop")
    return ProviderInvokeResult(
        provider_code=provider_profile.provider_code,
        model_name=str(response_json.get("model") or model_name),
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        normalized_output={
            "text": normalized_text,
            "provider_code": provider_profile.provider_code,
            "model_name": str(response_json.get("model") or model_name),
        },
        raw_response_ref=f"http://{provider_profile.provider_code}/messages",
    )


def _invoke_gemini_generate_content(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> ProviderInvokeResult:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的密钥")

    endpoint_base = _resolve_native_endpoint(provider_profile, extra_config, "")
    if not endpoint_base:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} 缺少可用的接口地址")

    system_prompt, messages = _split_system_and_messages(_build_messages(capability=capability, payload=payload))
    endpoint = f"{endpoint_base.rstrip('/')}/models/{model_name}:generateContent?key={api_key}"
    request_body: dict[str, object] = {
        "contents": [
            {
                "role": "model" if item["role"] == "assistant" else "user",
                "parts": [{"text": item["content"]}],
            }
            for item in messages
        ],
        "generationConfig": {
            "temperature": extra_config.get("temperature", 0.2),
            "maxOutputTokens": _default_max_tokens_for_capability(capability),
        },
    }
    if system_prompt:
        request_body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    response_json = _post_json(
        endpoint=endpoint,
        request_body=request_body,
        request_headers={"Content-Type": "application/json"},
        provider_profile=provider_profile,
        extra_config=extra_config,
        timeout_ms=timeout_ms,
        honor_timeout_override=honor_timeout_override,
    )

    normalized_text = _extract_gemini_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    finish_reason = _extract_gemini_finish_reason(response_json)
    return ProviderInvokeResult(
        provider_code=provider_profile.provider_code,
        model_name=model_name,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        normalized_output={
            "text": normalized_text,
            "provider_code": provider_profile.provider_code,
            "model_name": model_name,
        },
        raw_response_ref=f"http://{provider_profile.provider_code}/generateContent",
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


def _resolve_native_endpoint(
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
    suffix: str,
) -> str:
    endpoint = str(extra_config.get("native_api_base") or provider_profile.base_url or "").strip()
    if not endpoint:
        runtime_config = settings.ai_runtime.provider_configs.get(provider_profile.provider_code)
        endpoint = (runtime_config.base_url or "").strip() if runtime_config else ""
    if not endpoint:
        return ""
    if not suffix:
        return endpoint.rstrip("/")
    return endpoint.rstrip("/") + suffix


def _post_json(
    *,
    endpoint: str,
    request_body: dict[str, object],
    request_headers: dict[str, str],
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> dict[str, object]:
    try:
        effective_timeout_ms = _resolve_effective_timeout_ms(
            provider_profile=provider_profile,
            extra_config=extra_config,
            requested_timeout_ms=timeout_ms,
            honor_requested_timeout=honor_timeout_override,
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

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError("validation_error", "provider returned invalid json") from exc
    if not isinstance(parsed, dict):
        raise ProviderRuntimeError("validation_error", "provider returned invalid payload")
    return parsed


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[tuple[str | None, str]]:
    event_name: str | None = None
    data_lines: list[str] = []

    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if not line:
            if data_lines:
                yield (event_name, "\n".join(data_lines))
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            candidate = line[6:].strip()
            event_name = candidate or None
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if data_lines:
        yield (event_name, "\n".join(data_lines))


def _split_system_and_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    if messages and messages[0].get("role") == "system":
        return messages[0].get("content", ""), messages[1:]
    return "", messages


def _default_max_tokens_for_capability(capability: AiCapability) -> int:
    if capability == "audio_generation":
        return 512
    return 256


def _resolve_effective_timeout_ms(
    *,
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
    requested_timeout_ms: int | None,
    honor_requested_timeout: bool = False,
) -> int:
    if honor_requested_timeout and isinstance(requested_timeout_ms, int) and requested_timeout_ms > 0:
        return requested_timeout_ms

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


def _resolve_text_task_kind(payload: Mapping[str, object]) -> str:
    task_type = str(payload.get("task_type") or "").strip()
    if task_type in {"reminder_copywriting", "scene_explanation"}:
        return task_type
    if "title" in payload and "question" not in payload and "scene_name" not in payload:
        return "reminder_copywriting"
    if "scene_name" in payload:
        return "scene_explanation"
    return "general_text"


def _build_messages(
    *,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> list[dict[str, str]]:
    # 支持 payload 中直接传入 messages（llm_task 模块使用）
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
                    "content": "你是家庭场景解释助手。请用中文解释场景为什么执行或为什么被阻断，保持保守清晰。",
                },
                {
                    "role": "user",
                    "content": f"场景名：{scene_name}\n阻断原因：{blocked_guards}\n步骤数：{payload.get('step_count') or 0}",
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


def _extract_anthropic_response_text(response_json: dict[str, object]) -> str:
    content = response_json.get("content")
    if not isinstance(content, list) or not content:
        raise ProviderRuntimeError("validation_error", "provider response missing content")
    text_parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            text_parts.append(str(item.get("text")))
    if text_parts:
        return "\n".join(text_parts)
    raise ProviderRuntimeError("validation_error", "provider response missing text content")


def _extract_anthropic_stream_text(response_json: object) -> str:
    if not isinstance(response_json, dict):
        return ""
    if response_json.get("type") != "content_block_delta":
        return ""
    delta = response_json.get("delta")
    if not isinstance(delta, dict):
        return ""
    if delta.get("type") != "text_delta":
        return ""
    text = delta.get("text")
    return text if isinstance(text, str) else ""


def _extract_gemini_response_text(response_json: dict[str, object]) -> str:
    candidates = response_json.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ProviderRuntimeError("validation_error", "provider response missing candidates")
    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        raise ProviderRuntimeError("validation_error", "provider response invalid candidate")
    content = first_candidate.get("content")
    if not isinstance(content, dict):
        raise ProviderRuntimeError("validation_error", "provider response missing content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ProviderRuntimeError("validation_error", "provider response missing parts")
    text_parts: list[str] = []
    for item in parts:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            text_parts.append(str(item.get("text")))
    if text_parts:
        return "\n".join(text_parts)
    raise ProviderRuntimeError("validation_error", "provider response missing text part")


def _extract_gemini_stream_text(response_json: object) -> str:
    if not isinstance(response_json, dict):
        return ""

    candidates = response_json.get("candidates")
    if not isinstance(candidates, list):
        return ""

    text_parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for item in parts:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(str(item.get("text")))

    return "".join(text_parts)


def _extract_finish_reason(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason:
            return finish_reason
    return "stop"


def _extract_gemini_finish_reason(response_json: dict[str, object]) -> str:
    candidates = response_json.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        finish_reason = candidates[0].get("finishReason")
        if isinstance(finish_reason, str) and finish_reason:
            return finish_reason.lower()
    return "stop"


def _map_http_status_to_error_code(status_code: int) -> str:
    if status_code == 408 or status_code == 504:
        return "timeout"
    if status_code == 401 or status_code == 403:
        return "auth_failed"
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
    raw_fail_capabilities = extra_config.get("simulate_fail_capabilities")
    fail_capabilities = {
        str(item)
        for item in raw_fail_capabilities
    } if isinstance(raw_fail_capabilities, list) else set()
    if capability in fail_capabilities:
        return True
    raw_payload_failures = payload.get("_simulate_fail_provider_codes")
    payload_failures = {
        str(item)
        for item in raw_payload_failures
    } if isinstance(raw_payload_failures, list) else set()
    return provider_code in payload_failures


def _read_int_value(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default


def _build_simulated_output(
    *,
    capability: AiCapability,
    provider_code: str,
    model_name: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    if capability == "text":
        text_task_kind = _resolve_text_task_kind(payload)
        if text_task_kind == "reminder_copywriting":
            title = str(payload.get("title") or "提醒")
            return {
                "text": f"[{provider_code}] {title}，请尽快处理。",
                "provider_code": provider_code,
                "model_name": model_name,
            }
        if text_task_kind == "scene_explanation":
            scene_name = str(payload.get("scene_name") or "场景")
            return {
                "text": f"[{provider_code}] {scene_name} 将按模板步骤执行。",
                "provider_code": provider_code,
                "model_name": model_name,
            }

        question = str(payload.get("question") or "当前问题")
        agent_name = _read_agent_name_from_payload(payload)
        memory_summary = _read_agent_memory_summary(payload)
        return {
            "text": f"[{provider_code}] {agent_name}已根据结构化事实生成回答草稿：{question}{memory_summary}",
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


def _build_device_context_prompt(payload: Mapping[str, object]) -> str:
    summary_text = str(payload.get("device_context_summary_text") or "").strip()
    if not summary_text:
        return ""
    return (
        "\n最近设备上下文只用于理解用户这轮可能在指哪个设备，不能当成这轮已经执行成功的证据。"
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


def _read_agent_memory_summary(payload: Mapping[str, object]) -> str:
    memory_context = payload.get("agent_memory_context")
    if not isinstance(memory_context, Mapping):
        return ""
    summary = str(memory_context.get("summary") or "").strip()
    if not summary:
        return ""
    return f" 当前记忆视角：{summary}"


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


def _read_request_context(payload: Mapping[str, object]) -> ProviderRequestContext:
    raw_context = payload.get("request_context")
    if not isinstance(raw_context, Mapping):
        return ProviderRequestContext(
            request_id="-",
            trace_id="-",
            session_id="-",
            channel="-",
        )
    return ProviderRequestContext(
        request_id=str(raw_context.get("request_id") or "-"),
        trace_id=str(raw_context.get("trace_id") or "-"),
        session_id=str(raw_context.get("session_id") or "-"),
        channel=str(raw_context.get("channel") or "-"),
    )
