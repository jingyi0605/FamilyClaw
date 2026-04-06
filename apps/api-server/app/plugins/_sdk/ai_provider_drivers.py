from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
import asyncio
from dataclasses import dataclass
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
from app.modules.ai_gateway.provider_runtime import ProviderInvokeResult, ProviderRuntimeError, _should_fail
from app.modules.ai_gateway.schemas import AiCapability
from app.modules.plugin.schemas import PluginRegistryItem
from app.plugins._sdk.ai_provider_messages import build_messages, split_system_and_messages


SyncInvoke = Callable[..., ProviderInvokeResult]
StreamInvoke = Callable[..., AsyncIterator[str]]


@dataclass(frozen=True)
class ProviderRequestContext:
    request_id: str
    trace_id: str
    session_id: str
    channel: str


@dataclass(slots=True)
class ProtocolBackedAiProviderDriver:
    sync_invoke: SyncInvoke
    async_invoke: Callable[..., object]
    stream_invoke: StreamInvoke

    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> ProviderInvokeResult:
        _raise_if_simulated_failure(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )
        return self.sync_invoke(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
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
        _raise_if_simulated_failure(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
        )
        result = self.async_invoke(
            capability=capability,
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        )
        if asyncio.iscoroutine(result):
            return await result
        return result  # type: ignore[return-value]

    async def stream(
        self,
        *,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> AsyncIterator[str]:
        _raise_if_simulated_failure(
            capability=_resolve_stream_capability(provider_profile),
            provider_profile=provider_profile,
            payload=payload,
        )
        async for chunk in self.stream_invoke(
            provider_profile=provider_profile,
            payload=payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk


def build_openai_compatible_driver(plugin: PluginRegistryItem | None = None) -> ProtocolBackedAiProviderDriver:
    _ = plugin
    return ProtocolBackedAiProviderDriver(
        sync_invoke=_invoke_openai_compatible,
        async_invoke=_ainvoke_openai_compatible,
        stream_invoke=_stream_openai_compatible,
    )


def build_openai_responses_driver(plugin: PluginRegistryItem | None = None) -> ProtocolBackedAiProviderDriver:
    _ = plugin
    return ProtocolBackedAiProviderDriver(
        sync_invoke=_invoke_openai_responses,
        async_invoke=_ainvoke_openai_responses,
        stream_invoke=_stream_openai_responses,
    )


def build_anthropic_messages_driver(plugin: PluginRegistryItem | None = None) -> ProtocolBackedAiProviderDriver:
    _ = plugin
    return ProtocolBackedAiProviderDriver(
        sync_invoke=_invoke_anthropic_messages,
        async_invoke=_build_threaded_async_invoke(_invoke_anthropic_messages),
        stream_invoke=_stream_anthropic_messages,
    )


def build_gemini_generate_content_driver(plugin: PluginRegistryItem | None = None) -> ProtocolBackedAiProviderDriver:
    _ = plugin
    return ProtocolBackedAiProviderDriver(
        sync_invoke=_invoke_gemini_generate_content,
        async_invoke=_build_threaded_async_invoke(_invoke_gemini_generate_content),
        stream_invoke=_stream_gemini_generate_content,
    )


def _build_threaded_async_invoke(sync_invoke: SyncInvoke) -> Callable[..., object]:
    async def _invoke_async(**kwargs):
        return await asyncio.to_thread(sync_invoke, **kwargs)

    return _invoke_async


def _raise_if_simulated_failure(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
) -> None:
    extra_config = load_json(provider_profile.extra_config_json) or {}
    if not _should_fail(
        extra_config=extra_config,
        payload=payload,
        capability=capability,
        provider_code=provider_profile.provider_code,
    ):
        return
    error_code = str(extra_config.get("simulate_error_code") or "provider_failed")
    raise ProviderRuntimeError(error_code, f"{provider_profile.provider_code} simulated failure")


def _resolve_stream_capability(provider_profile: AiProviderProfile) -> AiCapability:
    supported_capabilities = load_json(provider_profile.supported_capabilities_json) or []
    if "text" in supported_capabilities:
        return "text"
    if supported_capabilities:
        return supported_capabilities[0]
    return "text"


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
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_request_body(
        capability=capability,
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=False,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)

    try:
        effective_timeout_ms = _resolve_effective_timeout_ms(
            provider_profile=provider_profile,
            extra_config=extra_config,
            requested_timeout_ms=timeout_ms,
            honor_requested_timeout=honor_timeout_override,
        )
        logger.info(
            "[Invoke] provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s",
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
        raise ProviderRuntimeError(_map_http_status_to_error_code(exc.code), detail or str(exc)) from exc
    except socket.timeout as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            raise ProviderRuntimeError("timeout", "provider request timeout") from exc
        raise ProviderRuntimeError("provider_failed", str(exc.reason)) from exc

    response_json = _parse_json_object(response_text)
    normalized_text = _extract_openai_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_openai_finish_reason(response_json)
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
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_request_body(
        capability=capability,
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=False,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)
    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    try:
        logger.info(
            "[AsyncInvoke] provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s",
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
        raise ProviderRuntimeError(
            _map_http_status_to_error_code(exc.response.status_code),
            exc.response.text or str(exc),
        ) from exc
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc

    response_json = _parse_json_object(response_text)
    normalized_text = _extract_openai_response_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_openai_finish_reason(response_json)
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
) -> AsyncIterator[str]:
    logger = logging.getLogger(__name__)
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    request_context = _read_request_context(payload)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    endpoint = _resolve_chat_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_request_body(
        capability="text",
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=True,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)
    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    logger.info(
        "[Stream] provider=%s model=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s body_keys=%s",
        provider_profile.provider_code,
        model_name,
        request_context.request_id,
        request_context.trace_id,
        request_context.session_id,
        request_context.channel,
        endpoint,
        list(request_body.keys()),
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream("POST", endpoint, json=request_body, headers=request_headers) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(
                        _map_http_status_to_error_code(response.status_code),
                        detail or response.reason_phrase,
                    )

                chunk_count = 0
                yielded_char_count = 0
                first_content_ms: int | None = None
                buffer = ""
                async for chunk in response.aiter_text():
                    chunk_count += 1
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line == "data: [DONE]":
                            return
                        if not line.startswith("data:"):
                            continue
                        data = _parse_optional_json(line[5:].strip())
                        if not isinstance(data, dict):
                            continue
                        content = _extract_openai_stream_text(data)
                        if not content:
                            continue
                        yielded_char_count += len(content)
                        if first_content_ms is None:
                            first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                            logger.info(
                                "[Stream] first_content provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunk_index=%s first_content_ms=%s",
                                provider_profile.provider_code,
                                model_name,
                                request_context.request_id,
                                request_context.trace_id,
                                request_context.session_id,
                                chunk_count,
                                first_content_ms,
                            )
                        yield content
                logger.info(
                    "[Stream] done provider=%s model=%s request_id=%s trace_id=%s session_id=%s chunks=%s chars=%s",
                    provider_profile.provider_code,
                    model_name,
                    request_context.request_id,
                    request_context.trace_id,
                    request_context.session_id,
                    chunk_count,
                    yielded_char_count,
                )
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


def _invoke_openai_responses(
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
    endpoint = _resolve_responses_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_responses_request_body(
        capability=capability,
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=False,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)

    try:
        effective_timeout_ms = _resolve_effective_timeout_ms(
            provider_profile=provider_profile,
            extra_config=extra_config,
            requested_timeout_ms=timeout_ms,
            honor_requested_timeout=honor_timeout_override,
        )
        logger.info(
            "[Invoke] provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s api=responses",
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
        raise ProviderRuntimeError(_map_http_status_to_error_code(exc.code), detail or str(exc)) from exc
    except socket.timeout as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            raise ProviderRuntimeError("timeout", "provider request timeout") from exc
        raise ProviderRuntimeError("provider_failed", str(exc.reason)) from exc

    response_json = _parse_json_object(response_text)
    normalized_text = _extract_openai_responses_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_openai_responses_finish_reason(response_json)
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
        raw_response_ref=f"http://{provider_profile.provider_code}/responses",
    )


async def _ainvoke_openai_responses(
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
    endpoint = _resolve_responses_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_responses_request_body(
        capability=capability,
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=False,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)
    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    try:
        logger.info(
            "[AsyncInvoke] provider=%s model=%s timeout_ms=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s api=responses",
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
        raise ProviderRuntimeError(
            _map_http_status_to_error_code(exc.response.status_code),
            exc.response.text or str(exc),
        ) from exc
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc

    response_json = _parse_json_object(response_text)
    normalized_text = _extract_openai_responses_text(response_json)
    latency_ms = max(int((perf_counter() - started_at) * 1000), 1)
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = _extract_openai_responses_finish_reason(response_json)
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
        raw_response_ref=f"http://{provider_profile.provider_code}/responses",
    )


async def _stream_openai_responses(
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
    endpoint = _resolve_responses_endpoint(provider_profile, extra_config)
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    request_body = _build_openai_responses_request_body(
        capability="text",
        provider_profile=provider_profile,
        payload=payload,
        extra_config=extra_config,
        stream=True,
    )
    request_headers = _build_openai_headers(api_key=api_key, extra_config=extra_config)
    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    logger.info(
        "[Stream] provider=%s model=%s request_id=%s trace_id=%s session_id=%s channel=%s endpoint=%s body_keys=%s api=responses",
        provider_profile.provider_code,
        model_name,
        request_context.request_id,
        request_context.trace_id,
        request_context.session_id,
        request_context.channel,
        endpoint,
        list(request_body.keys()),
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream("POST", endpoint, json=request_body, headers=request_headers) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(
                        _map_http_status_to_error_code(response.status_code),
                        detail or response.reason_phrase,
                    )

                event_count = 0
                first_content_ms: int | None = None
                async for _event_name, data_str in _iter_sse_events(response):
                    event_count += 1
                    if data_str == "[DONE]":
                        return
                    data = _parse_optional_json(data_str)
                    if not isinstance(data, dict):
                        continue
                    content = _extract_openai_responses_stream_text(data)
                    if not content:
                        continue
                    if first_content_ms is None:
                        first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                        logger.info(
                            "[Stream] first_content provider=%s model=%s first_content_ms=%s event_count=%s api=responses",
                            provider_profile.provider_code,
                            model_name,
                            first_content_ms,
                            event_count,
                        )
                    yield content
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


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
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing api key")

    endpoint = _resolve_native_endpoint(provider_profile, extra_config, "/messages")
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    system_prompt, messages = split_system_and_messages(build_messages(capability=capability, payload=payload))
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
    response_model_name = str(response_json.get("model") or model_name)
    finish_reason = str(response_json.get("stop_reason") or "stop")
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
        raw_response_ref=f"http://{provider_profile.provider_code}/messages",
    )


async def _stream_anthropic_messages(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> AsyncIterator[str]:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing api key")

    endpoint = _resolve_native_endpoint(provider_profile, extra_config, "/messages")
    if not endpoint:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    system_prompt, messages = split_system_and_messages(build_messages(capability="text", payload=payload))
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

    effective_timeout_ms = _resolve_effective_timeout_ms(
        provider_profile=provider_profile,
        extra_config=extra_config,
        requested_timeout_ms=timeout_ms,
        honor_requested_timeout=honor_timeout_override,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(effective_timeout_ms / 1000)) as client:
            async with client.stream(
                "POST",
                endpoint,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": str(extra_config.get("anthropic_version") or "2023-06-01"),
                },
            ) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(
                        _map_http_status_to_error_code(response.status_code),
                        detail or response.reason_phrase,
                    )

                yielded_char_count = 0
                event_count = 0
                first_content_ms: int | None = None
                async for event_name, data_str in _iter_sse_events(response):
                    event_count += 1
                    if data_str == "[DONE]":
                        return
                    data = _parse_optional_json(data_str)
                    if not isinstance(data, dict):
                        continue
                    if data.get("type") == "error":
                        raise ProviderRuntimeError("provider_failed", json.dumps(data, ensure_ascii=False))
                    content = _extract_anthropic_stream_text(data)
                    if not content:
                        continue
                    yielded_char_count += len(content)
                    if first_content_ms is None:
                        first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                        logging.getLogger(__name__).info(
                            "[Stream] first_content provider=%s model=%s event=%s first_content_ms=%s chars=%s",
                            provider_profile.provider_code,
                            model_name,
                            event_name,
                            first_content_ms,
                            yielded_char_count,
                        )
                    yield content
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


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
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing api key")

    endpoint_base = _resolve_native_endpoint(provider_profile, extra_config, "")
    if not endpoint_base:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    system_prompt, messages = split_system_and_messages(build_messages(capability=capability, payload=payload))
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


async def _stream_gemini_generate_content(
    *,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    timeout_ms: int | None,
    honor_timeout_override: bool = False,
) -> AsyncIterator[str]:
    started_at = perf_counter()
    extra_config = load_json(provider_profile.extra_config_json) or {}
    model_name = _resolve_model_name(provider_profile)
    api_key = _resolve_provider_secret(provider_profile, extra_config)
    if not api_key:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing api key")

    endpoint_base = _resolve_native_endpoint(provider_profile, extra_config, "")
    if not endpoint_base:
        raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing endpoint")

    system_prompt, messages = split_system_and_messages(build_messages(capability="text", payload=payload))
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
            async with client.stream(
                "POST",
                endpoint,
                json=request_body,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.is_error:
                    detail = (await response.aread()).decode("utf-8", errors="ignore")
                    raise ProviderRuntimeError(
                        _map_http_status_to_error_code(response.status_code),
                        detail or response.reason_phrase,
                    )

                event_count = 0
                first_content_ms: int | None = None
                async for _event_name, data_str in _iter_sse_events(response):
                    event_count += 1
                    if data_str == "[DONE]":
                        return
                    data = _parse_optional_json(data_str)
                    if not isinstance(data, dict):
                        continue
                    content = _extract_gemini_stream_text(data)
                    if not content:
                        continue
                    if first_content_ms is None:
                        first_content_ms = max(int((perf_counter() - started_at) * 1000), 1)
                        logging.getLogger(__name__).info(
                            "[Stream] first_content provider=%s model=%s first_content_ms=%s event_count=%s",
                            provider_profile.provider_code,
                            model_name,
                            first_content_ms,
                            event_count,
                        )
                    yield content
    except httpx.TimeoutException as exc:
        raise ProviderRuntimeError("timeout", "provider request timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderRuntimeError("provider_failed", str(exc)) from exc


def _build_openai_request_body(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    extra_config: dict[str, object],
    stream: bool,
) -> dict[str, object]:
    model_name = _resolve_model_name(provider_profile)
    request_body: dict[str, object] = {
        "model": model_name,
        "messages": build_messages(capability=capability, payload=payload),
        "temperature": payload.get("temperature", extra_config.get("temperature", 0.2 if not stream else 0.7)),
        "stream": stream,
    }
    if stream:
        request_body["max_tokens"] = payload.get("max_tokens", extra_config.get("max_tokens", 512))
    elif "max_tokens" in extra_config:
        request_body["max_tokens"] = extra_config["max_tokens"]
    else:
        request_body["max_tokens"] = _default_max_tokens_for_capability(capability)

    if isinstance(extra_config.get("default_request_body"), dict):
        request_body = {
            **extra_config["default_request_body"],
            **request_body,
        }
    return request_body


def _build_openai_responses_request_body(
    *,
    capability: AiCapability,
    provider_profile: AiProviderProfile,
    payload: Mapping[str, object],
    extra_config: dict[str, object],
    stream: bool,
) -> dict[str, object]:
    model_name = _resolve_model_name(provider_profile)
    system_prompt, messages = split_system_and_messages(build_messages(capability=capability, payload=payload))
    request_body: dict[str, object] = {
        "model": model_name,
        "input": messages,
        "temperature": payload.get("temperature", extra_config.get("temperature", 0.2 if not stream else 0.7)),
        "stream": stream,
    }
    if system_prompt:
        request_body["instructions"] = system_prompt

    if stream:
        request_body["max_output_tokens"] = payload.get("max_tokens", extra_config.get("max_tokens", 512))
    elif "max_tokens" in extra_config:
        request_body["max_output_tokens"] = extra_config["max_tokens"]
    else:
        request_body["max_output_tokens"] = _default_max_tokens_for_capability(capability)

    if isinstance(extra_config.get("default_request_body"), dict):
        request_body = {
            **extra_config["default_request_body"],
            **request_body,
        }
    return request_body


def _build_openai_headers(*, api_key: str | None, extra_config: dict[str, object]) -> dict[str, str]:
    request_headers = {"Content-Type": "application/json"}
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    custom_headers = extra_config.get("headers")
    if isinstance(custom_headers, dict):
        request_headers.update({str(key): str(value) for key, value in custom_headers.items()})
    return request_headers


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

    raise ProviderRuntimeError("provider_failed", f"{provider_profile.provider_code} missing api key")


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


def _resolve_responses_endpoint(
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
) -> str:
    endpoint = str(extra_config.get("responses_url") or provider_profile.base_url or "").strip()
    if not endpoint:
        runtime_config = settings.ai_runtime.provider_configs.get(provider_profile.provider_code)
        endpoint = (runtime_config.base_url or "").strip() if runtime_config else ""
    if not endpoint:
        return ""
    if endpoint.endswith("/responses"):
        return endpoint
    if endpoint.endswith("/chat/completions"):
        return endpoint[: -len("/chat/completions")] + "/responses"
    return endpoint.rstrip("/") + "/responses"


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
    return _parse_json_object(response_text)


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


def _default_max_tokens_for_capability(capability: AiCapability) -> int:
    if capability == "audio_generation":
        return 512
    return 256


def _parse_json_object(text: str) -> dict[str, object]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeError("validation_error", "provider returned invalid json") from exc
    if not isinstance(parsed, dict):
        raise ProviderRuntimeError("validation_error", "provider returned invalid payload")
    return parsed


def _parse_optional_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_openai_responses_text(response_json: dict[str, object]) -> str:
    output = response_json.get("output")
    if not isinstance(output, list) or not output:
        raise ProviderRuntimeError("validation_error", "provider response missing output")
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                text_parts.append(str(part.get("text")))
    if text_parts:
        return "\n".join(text_parts)
    raise ProviderRuntimeError("validation_error", "provider response missing output text")


def _extract_openai_responses_stream_text(response_json: dict[str, object]) -> str:
    event_type = response_json.get("type")
    if event_type != "response.output_text.delta":
        return ""
    delta = response_json.get("delta")
    return delta if isinstance(delta, str) else ""


def _extract_openai_responses_finish_reason(response_json: dict[str, object]) -> str:
    status = response_json.get("status")
    if isinstance(status, str) and status == "completed":
        return "stop"
    if isinstance(status, str) and status:
        return status
    return "stop"


def _extract_openai_response_text(response_json: dict[str, object]) -> str:
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


def _extract_openai_stream_text(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    delta = choices[0].get("delta", {})
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content", "")
    return content if isinstance(content, str) else ""


def _extract_openai_finish_reason(response_json: dict[str, object]) -> str:
    choices = response_json.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason:
            return finish_reason
    return "stop"


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


def _extract_gemini_finish_reason(response_json: dict[str, object]) -> str:
    candidates = response_json.get("candidates")
    if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
        finish_reason = candidates[0].get("finishReason")
        if isinstance(finish_reason, str) and finish_reason:
            return finish_reason.lower()
    return "stop"


def _map_http_status_to_error_code(status_code: int) -> str:
    if status_code in {408, 504}:
        return "timeout"
    if status_code in {401, 403}:
        return "auth_failed"
    if status_code == 429:
        return "rate_limited"
    if status_code == 422:
        return "validation_error"
    return "provider_failed"


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
