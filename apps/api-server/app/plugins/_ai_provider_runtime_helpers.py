from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
import json

from app.db.utils import load_json
from app.modules.ai_gateway.models import AiProviderProfile
from app.modules.ai_gateway.provider_driver import AiProviderDriver
from app.modules.ai_gateway.schemas import AiCapability


PrepareRequest = Callable[
    [AiProviderProfile, AiCapability, Mapping[str, object]],
    tuple[AiProviderProfile, Mapping[str, object]],
]


@dataclass(slots=True)
class WrappedAiProviderDriver:
    base_driver: AiProviderDriver
    prepare_request: PrepareRequest

    def invoke(
        self,
        *,
        capability: AiCapability,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ):
        prepared_profile, prepared_payload = self.prepare_request(provider_profile, capability, payload)
        return self.base_driver.invoke(
            capability=capability,
            provider_profile=prepared_profile,
            payload=prepared_payload,
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
    ):
        prepared_profile, prepared_payload = self.prepare_request(provider_profile, capability, payload)
        return await self.base_driver.ainvoke(
            capability=capability,
            provider_profile=prepared_profile,
            payload=prepared_payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        )

    async def stream(
        self,
        *,
        provider_profile: AiProviderProfile,
        payload: Mapping[str, object],
        timeout_ms: int | None = None,
        honor_timeout_override: bool = False,
    ) -> AsyncIterator[str]:
        prepared_profile, prepared_payload = self.prepare_request(provider_profile, "text", payload)
        async for chunk in self.base_driver.stream(
            provider_profile=prepared_profile,
            payload=prepared_payload,
            timeout_ms=timeout_ms,
            honor_timeout_override=honor_timeout_override,
        ):
            yield chunk


def read_provider_extra_config(provider_profile: AiProviderProfile) -> dict[str, object]:
    value = load_json(provider_profile.extra_config_json) or {}
    if not isinstance(value, dict):
        return {}
    return dict(value)


def clone_provider_profile_with_extra_config(
    provider_profile: AiProviderProfile,
    extra_config: dict[str, object],
    *,
    base_url: str | None = None,
) -> AiProviderProfile:
    return AiProviderProfile(
        id=provider_profile.id,
        provider_code=provider_profile.provider_code,
        display_name=provider_profile.display_name,
        transport_type=provider_profile.transport_type,
        api_family=provider_profile.api_family,
        base_url=provider_profile.base_url if base_url is None else base_url,
        api_version=provider_profile.api_version,
        secret_ref=provider_profile.secret_ref,
        enabled=provider_profile.enabled,
        supported_capabilities_json=provider_profile.supported_capabilities_json,
        privacy_level=provider_profile.privacy_level,
        latency_budget_ms=provider_profile.latency_budget_ms,
        cost_policy_json=provider_profile.cost_policy_json,
        extra_config_json=json.dumps(extra_config, ensure_ascii=False) if extra_config else None,
        updated_at=provider_profile.updated_at,
    )


def read_int_value(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default
