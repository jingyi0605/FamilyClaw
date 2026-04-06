from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.modules.ai_gateway.models import AiProviderProfile
from app.modules.ai_gateway.provider_driver import AiProviderDriver
from app.modules.ai_gateway.provider_runtime import ProviderRuntimeError
from app.modules.ai_gateway.schemas import AiCapability
from app.modules.plugin.schemas import PluginRegistryItem
from app.plugins._ai_provider_runtime_helpers import clone_provider_profile_with_extra_config, read_provider_extra_config
from app.plugins._sdk.ai_provider_drivers import build_openai_compatible_driver, build_openai_responses_driver

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_PROTOCOL_AUTO = "auto"
_PROTOCOL_CHAT_COMPLETIONS = "chat_completions"
_PROTOCOL_RESPONSES = "responses"


def build_driver(plugin: PluginRegistryItem | None = None):
    return ChatGptDualAdapterDriver(
        chat_driver=build_openai_compatible_driver(plugin),
        responses_driver=build_openai_responses_driver(plugin),
    )


@dataclass(frozen=True)
class PreparedChatGptRequest:
    provider_profile: AiProviderProfile
    payload: Mapping[str, object]
    protocol_mode: str


@dataclass(slots=True)
class ChatGptDualAdapterDriver:
    chat_driver: AiProviderDriver
    responses_driver: AiProviderDriver

    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ):
        prepared = _prepare_request(provider_profile, capability, payload)
        protocol_order = _iter_protocol_order(prepared.protocol_mode, capability)
        last_error: ProviderRuntimeError | None = None
        for index, protocol in enumerate(protocol_order):
            try:
                return _select_driver(self, protocol).invoke(
                    capability=capability,
                    provider_profile=prepared.provider_profile,
                    payload=prepared.payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                )
            except ProviderRuntimeError as exc:
                last_error = exc
                if index + 1 >= len(protocol_order) or not _should_try_next_protocol(exc):
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderRuntimeError("provider_failed", "chatgpt driver failed before dispatch")

    async def ainvoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ):
        prepared = _prepare_request(provider_profile, capability, payload)
        protocol_order = _iter_protocol_order(prepared.protocol_mode, capability)
        last_error: ProviderRuntimeError | None = None
        for index, protocol in enumerate(protocol_order):
            try:
                return await _select_driver(self, protocol).ainvoke(
                    capability=capability,
                    provider_profile=prepared.provider_profile,
                    payload=prepared.payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                )
            except ProviderRuntimeError as exc:
                last_error = exc
                if index + 1 >= len(protocol_order) or not _should_try_next_protocol(exc):
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderRuntimeError("provider_failed", "chatgpt driver failed before dispatch")

    async def stream(
        self,
        *,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> AsyncIterator[str]:
        prepared = _prepare_request(provider_profile, "text", payload)
        protocol_order = _iter_protocol_order(prepared.protocol_mode, "text")
        for index, protocol in enumerate(protocol_order):
            emitted = False
            try:
                async for chunk in _select_driver(self, protocol).stream(
                    provider_profile=prepared.provider_profile,
                    payload=prepared.payload,
                    timeout_ms=timeout_ms,
                    honor_timeout_override=honor_timeout_override,
                ):
                    emitted = True
                    yield chunk
                return
            except ProviderRuntimeError as exc:
                if emitted or index + 1 >= len(protocol_order) or not _should_try_next_protocol(exc):
                    raise


def _prepare_request(
    provider_profile: AiProviderProfile,
    capability: AiCapability,
    payload: Mapping[str, object],
) -> PreparedChatGptRequest:
    _ = capability
    extra_config = read_provider_extra_config(provider_profile)
    raw_base_url = str(provider_profile.base_url or "").strip()
    normalized_base_url = _normalize_chatgpt_base_url(raw_base_url)
    next_extra_config = dict(extra_config)
    next_extra_config["chat_completions_url"] = _build_chat_completions_url(normalized_base_url)
    next_extra_config["responses_url"] = _build_responses_url(normalized_base_url)

    protocol_mode = _normalize_protocol_mode(next_extra_config.get("api_protocol"))
    prepared_profile = clone_provider_profile_with_extra_config(
        provider_profile,
        next_extra_config,
        base_url=normalized_base_url,
    )
    return PreparedChatGptRequest(
        provider_profile=prepared_profile,
        payload=payload,
        protocol_mode=protocol_mode,
    )


def _normalize_chatgpt_base_url(base_url: str) -> str:
    normalized = base_url.strip() or _DEFAULT_OPENAI_BASE_URL
    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")

    # 用户经常只填站点根地址，这里直接补成 API 基址，别把请求送去网页首页。
    if not path:
        path = "/v1"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)).rstrip("/")


def _build_chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/responses"):
        return normalized[: -len("/responses")] + "/chat/completions"
    if normalized.endswith("/models"):
        return normalized[: -len("/models")] + "/chat/completions"
    return normalized + "/chat/completions"


def _build_responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")] + "/responses"
    if normalized.endswith("/models"):
        return normalized[: -len("/models")] + "/responses"
    return normalized + "/responses"


def _normalize_protocol_mode(value: object) -> str:
    protocol = str(value or _PROTOCOL_AUTO).strip().lower()
    if protocol in {_PROTOCOL_CHAT_COMPLETIONS, _PROTOCOL_RESPONSES}:
        return protocol
    return _PROTOCOL_AUTO


def _iter_protocol_order(protocol_mode: str, capability: AiCapability) -> list[str]:
    if protocol_mode == _PROTOCOL_RESPONSES:
        return [_PROTOCOL_RESPONSES]
    if protocol_mode == _PROTOCOL_CHAT_COMPLETIONS:
        return [_PROTOCOL_CHAT_COMPLETIONS]

    # 自动模式优先走 responses；一旦供应商只保留旧兼容层，再退回 chat/completions。
    if capability == "text":
        return [_PROTOCOL_RESPONSES, _PROTOCOL_CHAT_COMPLETIONS]
    return [_PROTOCOL_CHAT_COMPLETIONS, _PROTOCOL_RESPONSES]


def _select_driver(driver: ChatGptDualAdapterDriver, protocol: str) -> AiProviderDriver:
    if protocol == _PROTOCOL_RESPONSES:
        return driver.responses_driver
    return driver.chat_driver


def _should_try_next_protocol(exc: ProviderRuntimeError) -> bool:
    if exc.error_code == "validation_error":
        return True
    if exc.error_code != "provider_failed":
        return False
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "404",
            "not found",
            "invalid json",
            "failed to parse request body",
            "unsupported",
            "route",
        )
    )
