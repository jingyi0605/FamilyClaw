from dataclasses import dataclass
from typing import Protocol


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingProviderUnavailableError(EmbeddingProviderError):
    pass


@dataclass(frozen=True)
class EmbeddingProviderMetadata:
    provider_code: str
    model_name: str
    vector_dimension: int
    max_tokens: int | None = None
    is_builtin: bool = False


class EmbeddingProvider(Protocol):
    metadata: EmbeddingProviderMetadata

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
