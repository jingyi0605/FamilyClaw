from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os

import httpx

from app.core.config import settings
from app.modules.ai_gateway.provider_driver import build_openai_compatible_driver
from app.plugins._ai_provider_runtime_helpers import WrappedAiProviderDriver


def build_local_openai_driver(*, model_discovery_strategy: str):
    return DiscoverableLocalOpenAiDriver(
        base_driver=build_openai_compatible_driver(),
        prepare_request=_prepare_request,
        model_discovery_strategy=model_discovery_strategy,
    )


def _prepare_request(provider_profile, capability, payload: Mapping[str, object]):
    _ = capability
    return provider_profile, payload


@dataclass(slots=True)
class DiscoverableLocalOpenAiDriver(WrappedAiProviderDriver):
    model_discovery_strategy: str

    def discover_models(self, *, values: Mapping[str, object]) -> list[str]:
        if self.model_discovery_strategy == "ollama_tags":
            return discover_ollama_models(values=values)
        return discover_openai_compatible_models(values=values)


def discover_openai_compatible_models(*, values: Mapping[str, object]) -> list[str]:
    base_url = _require_base_url(values)
    endpoint = _build_openai_models_endpoint(base_url)
    payload = _request_json(endpoint, api_key=_resolve_secret_ref(values, allow_anonymous=True))
    return _extract_model_names_from_openai_list(payload)


def discover_ollama_models(*, values: Mapping[str, object]) -> list[str]:
    base_url = _require_base_url(values)
    endpoint = _build_ollama_tags_endpoint(base_url)
    payload = _request_json(endpoint, api_key=_resolve_secret_ref(values, allow_anonymous=True))
    return _extract_model_names_from_ollama_tags(payload)


def _require_base_url(values: Mapping[str, object]) -> str:
    base_url = str(values.get("base_url") or "").strip()
    if not base_url:
        raise ValueError("请先填写 Base URL。")
    return base_url


def _build_openai_models_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized[: -len("/chat/completions")] + "/models"
    if normalized.endswith("/models"):
        return normalized
    return normalized + "/models"


def _build_ollama_tags_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    if normalized.endswith("/v1"):
        normalized = normalized[: -len("/v1")]
    return normalized.rstrip("/") + "/api/tags"


def _resolve_secret_ref(values: Mapping[str, object], *, allow_anonymous: bool) -> str | None:
    secret_ref = str(values.get("secret_ref") or values.get("api_key") or "").strip()
    if secret_ref:
        if secret_ref.startswith(settings.ai_runtime.secret_ref_prefix):
            env_key = secret_ref[len(settings.ai_runtime.secret_ref_prefix):]
            if env_key:
                secret_value = os.getenv(env_key)
                if secret_value:
                    return secret_value
        secret_value = os.getenv(secret_ref)
        if secret_value:
            return secret_value
        return secret_ref
    if allow_anonymous:
        return None
    raise ValueError("当前供应商需要 API Key。")


def _request_json(url: str, *, api_key: str | None) -> object:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = httpx.get(url, headers=headers, timeout=httpx.Timeout(10.0))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        response_text = exc.response.text[:200].strip()
        if response_text:
            raise RuntimeError(f"模型列表请求失败（HTTP {status_code}）：{response_text}") from exc
        raise RuntimeError(f"模型列表请求失败（HTTP {status_code}）。") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"无法连接模型服务：{exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("模型列表返回的不是合法 JSON。") from exc


def _extract_model_names_from_openai_list(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise RuntimeError("模型列表格式不合法。")
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("模型列表格式不合法，缺少 data 数组。")
    return _dedupe_model_names(
        str(item.get("id") or item.get("model") or item.get("name") or "").strip()
        for item in data
        if isinstance(item, dict)
    )


def _extract_model_names_from_ollama_tags(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise RuntimeError("模型列表格式不合法。")
    data = payload.get("models")
    if not isinstance(data, list):
        raise RuntimeError("模型列表格式不合法，缺少 models 数组。")
    return _dedupe_model_names(
        str(item.get("name") or item.get("model") or "").strip()
        for item in data
        if isinstance(item, dict)
    )


def _dedupe_model_names(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
