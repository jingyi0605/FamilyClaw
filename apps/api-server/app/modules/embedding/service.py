from dataclasses import dataclass

from app.core.config import EmbeddingRuntimeConfig, settings
from app.modules.embedding.provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderMetadata,
    EmbeddingProviderUnavailableError,
)
from app.modules.embedding.provider_registry import EmbeddingProviderRegistry
from app.modules.embedding.providers.builtin_bge_small_zh_v15 import BUILTIN_PROVIDER_CODE


class EmbeddingServiceUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingExecutionResult:
    vectors: list[list[float]]
    metadata: EmbeddingProviderMetadata
    requested_provider_code: str
    fallback_used: bool = False
    fallback_reason: str | None = None


class EmbeddingService:
    def __init__(
        self,
        runtime_config: EmbeddingRuntimeConfig | None = None,
        *,
        registry: EmbeddingProviderRegistry | None = None,
        builtin_fallback_enabled: bool | None = None,
    ) -> None:
        self.runtime_config = runtime_config or settings.embedding_runtime
        self.registry = registry or EmbeddingProviderRegistry(self.runtime_config)
        if builtin_fallback_enabled is None:
            builtin_fallback_enabled = settings.conversation_embedding_fallback_to_builtin_enabled
        self.builtin_fallback_enabled = builtin_fallback_enabled

    def embed_texts(
        self,
        texts: list[str],
        *,
        provider_code: str | None = None,
        allow_builtin_fallback: bool | None = None,
    ) -> EmbeddingExecutionResult:
        requested_provider_code = (provider_code or self.runtime_config.default_provider_code or BUILTIN_PROVIDER_CODE).strip()
        if not requested_provider_code:
            requested_provider_code = BUILTIN_PROVIDER_CODE
        if allow_builtin_fallback is None:
            allow_builtin_fallback = self._should_fallback_to_builtin(requested_provider_code)
        provider = self._build_provider_with_optional_fallback(
            requested_provider_code,
            allow_builtin_fallback=allow_builtin_fallback,
        )
        try:
            vectors = provider.embed_texts(texts)
            return EmbeddingExecutionResult(
                vectors=vectors,
                metadata=provider.metadata,
                requested_provider_code=requested_provider_code,
                fallback_used=provider.metadata.provider_code != requested_provider_code,
                fallback_reason=None if provider.metadata.provider_code == requested_provider_code else "provider_build_failed",
            )
        except EmbeddingProviderError as exc:
            if provider.metadata.provider_code != BUILTIN_PROVIDER_CODE and allow_builtin_fallback:
                builtin_provider = self.registry.build_builtin_provider()
                try:
                    vectors = builtin_provider.embed_texts(texts)
                except EmbeddingProviderError as builtin_exc:
                    raise EmbeddingServiceUnavailableError(str(builtin_exc)) from builtin_exc
                return EmbeddingExecutionResult(
                    vectors=vectors,
                    metadata=builtin_provider.metadata,
                    requested_provider_code=requested_provider_code,
                    fallback_used=True,
                    fallback_reason=str(exc),
                )
            raise EmbeddingServiceUnavailableError(str(exc)) from exc

    def _build_provider_with_optional_fallback(
        self,
        provider_code: str,
        *,
        allow_builtin_fallback: bool,
    ) -> EmbeddingProvider:
        try:
            return self.registry.build_provider(provider_code)
        except EmbeddingProviderUnavailableError as exc:
            if provider_code != BUILTIN_PROVIDER_CODE and allow_builtin_fallback:
                return self.registry.build_builtin_provider()
            raise EmbeddingServiceUnavailableError(str(exc)) from exc

    def _should_fallback_to_builtin(self, provider_code: str) -> bool:
        if provider_code == BUILTIN_PROVIDER_CODE:
            return False
        provider_config = self.registry.get_provider_config(provider_code)
        if provider_config is not None:
            return self.builtin_fallback_enabled and provider_config.fallback_to_builtin
        return self.builtin_fallback_enabled
