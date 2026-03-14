from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.modules.embedding.provider import (
    EmbeddingProviderError,
    EmbeddingProviderMetadata,
    EmbeddingProviderUnavailableError,
)

BUILTIN_PROVIDER_CODE = "builtin_bge_small_zh_v15"
BUILTIN_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
BUILTIN_VECTOR_DIMENSION = 512
BUILTIN_MAX_TOKENS = 512


class BuiltinBgeSmallZhV15Provider:
    def __init__(
        self,
        *,
        cache_dir: str,
        model_name: str = BUILTIN_MODEL_NAME,
        timeout_ms: int = 3000,
    ) -> None:
        self.cache_dir = self._resolve_cache_dir(cache_dir)
        self.timeout_ms = timeout_ms
        self.metadata = EmbeddingProviderMetadata(
            provider_code=BUILTIN_PROVIDER_CODE,
            model_name=model_name,
            vector_dimension=BUILTIN_VECTOR_DIMENSION,
            max_tokens=BUILTIN_MAX_TOKENS,
            is_builtin=True,
        )
        self._encoder: Any | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoder = self._get_encoder()
        try:
            raw_vectors = encoder.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=False,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingProviderError(f"{self.metadata.provider_code} 推理失败：{exc}") from exc
        return [[float(value) for value in item] for item in raw_vectors]

    def _get_encoder(self) -> Any:
        if self._encoder is not None:
            return self._encoder
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise EmbeddingProviderUnavailableError(
                "内置 Embedding provider 依赖缺失，请安装 `sentence-transformers` 后再加载 BAAI/bge-small-zh-v1.5。"
            ) from exc
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._encoder = SentenceTransformer(self.metadata.model_name, cache_folder=str(self.cache_dir))
        except Exception as exc:
            raise EmbeddingProviderUnavailableError(
                f"加载内置 Embedding 模型 `{self.metadata.model_name}` 失败：{exc}"
            ) from exc
        return self._encoder

    @staticmethod
    def _resolve_cache_dir(cache_dir: str) -> Path:
        cache_path = Path(cache_dir)
        if cache_path.is_absolute():
            return cache_path
        return BASE_DIR.parents[1] / cache_path
