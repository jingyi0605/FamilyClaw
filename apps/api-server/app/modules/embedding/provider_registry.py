from collections.abc import Callable

from app.core.config import EmbeddingProviderRuntimeConfig, EmbeddingRuntimeConfig, settings
from app.modules.embedding.provider import EmbeddingProvider, EmbeddingProviderUnavailableError
from app.modules.embedding.providers.builtin_bge_small_zh_v15 import (
    BUILTIN_PROVIDER_CODE,
    BuiltinBgeSmallZhV15Provider,
)
from app.modules.embedding.providers.remote_openai_compatible import RemoteOpenAiCompatibleEmbeddingProvider

BuiltinFactory = Callable[[EmbeddingRuntimeConfig], EmbeddingProvider]
RemoteFactory = Callable[[EmbeddingProviderRuntimeConfig, EmbeddingRuntimeConfig, str], EmbeddingProvider]


class EmbeddingProviderRegistry:
    def __init__(
        self,
        runtime_config: EmbeddingRuntimeConfig | None = None,
        *,
        builtin_factory: BuiltinFactory | None = None,
        remote_factory: RemoteFactory | None = None,
    ) -> None:
        self.runtime_config = runtime_config or settings.embedding_runtime
        self._builtin_factory = builtin_factory or self._default_builtin_factory
        self._remote_factory = remote_factory or self._default_remote_factory

    def build_provider(self, provider_code: str | None) -> EmbeddingProvider:
        normalized_code = (provider_code or self.runtime_config.default_provider_code or BUILTIN_PROVIDER_CODE).strip()
        if not normalized_code:
            normalized_code = BUILTIN_PROVIDER_CODE
        if normalized_code == BUILTIN_PROVIDER_CODE:
            return self.build_builtin_provider()
        provider_config = self.get_provider_config(normalized_code)
        if provider_config is None:
            raise EmbeddingProviderUnavailableError(f"Embedding provider `{normalized_code}` 未配置。")
        if not provider_config.enabled:
            raise EmbeddingProviderUnavailableError(f"Embedding provider `{normalized_code}` 已禁用。")
        return self._remote_factory(provider_config, self.runtime_config, normalized_code)

    def build_builtin_provider(self) -> EmbeddingProvider:
        return self._builtin_factory(self.runtime_config)

    def get_provider_config(self, provider_code: str) -> EmbeddingProviderRuntimeConfig | None:
        provider_config = self.runtime_config.provider_configs.get(provider_code)
        if provider_config is None:
            return None
        if provider_config.provider_code:
            return provider_config
        return provider_config.model_copy(update={"provider_code": provider_code})

    @staticmethod
    def _default_builtin_factory(runtime_config: EmbeddingRuntimeConfig) -> EmbeddingProvider:
        return BuiltinBgeSmallZhV15Provider(
            cache_dir=runtime_config.builtin_cache_dir,
            model_name=runtime_config.builtin_model_name,
            timeout_ms=runtime_config.default_timeout_ms,
        )

    @staticmethod
    def _default_remote_factory(
        provider_config: EmbeddingProviderRuntimeConfig,
        runtime_config: EmbeddingRuntimeConfig,
        provider_code: str,
    ) -> EmbeddingProvider:
        return RemoteOpenAiCompatibleEmbeddingProvider(
            provider_code=provider_code,
            model_name=provider_config.model_name or runtime_config.builtin_model_name,
            endpoint=provider_config.endpoint or "",
            api_key=provider_config.api_key,
            timeout_ms=provider_config.timeout_ms or runtime_config.default_timeout_ms,
            vector_dimension=provider_config.vector_dimension,
        )
