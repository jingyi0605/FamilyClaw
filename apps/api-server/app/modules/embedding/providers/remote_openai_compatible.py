import os

import httpx

from app.core.config import settings
from app.modules.embedding.provider import (
    EmbeddingProviderError,
    EmbeddingProviderMetadata,
    EmbeddingProviderUnavailableError,
)


class RemoteOpenAiCompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        provider_code: str,
        model_name: str,
        endpoint: str,
        api_key: str | None,
        timeout_ms: int,
        vector_dimension: int | None = None,
    ) -> None:
        self._raw_api_key = api_key
        self.timeout_ms = timeout_ms
        self.endpoint = self._resolve_endpoint(endpoint)
        self.metadata = EmbeddingProviderMetadata(
            provider_code=provider_code,
            model_name=model_name,
            vector_dimension=vector_dimension or 0,
            max_tokens=None,
            is_builtin=False,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.endpoint:
            raise EmbeddingProviderUnavailableError(f"{self.metadata.provider_code} 缺少可用的 endpoint。")
        headers = {"Content-Type": "application/json"}
        api_key = self._resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": self.metadata.model_name, "input": texts}
        try:
            with httpx.Client(timeout=self.timeout_ms / 1000) as client:
                response = client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingProviderUnavailableError(f"{self.metadata.provider_code} 调用失败：{exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingProviderError(f"{self.metadata.provider_code} 返回了非法 JSON。") from exc
        raw_items = body.get("data")
        if not isinstance(raw_items, list):
            raise EmbeddingProviderError(f"{self.metadata.provider_code} 返回缺少 data。")
        ordered_items = sorted(
            raw_items,
            key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0,
        )
        vectors: list[list[float]] = []
        for item in ordered_items:
            if not isinstance(item, dict):
                raise EmbeddingProviderError(f"{self.metadata.provider_code} 返回了非法 embedding 项。")
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise EmbeddingProviderError(f"{self.metadata.provider_code} 返回缺少 embedding。")
            vectors.append([float(value) for value in embedding])
        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"{self.metadata.provider_code} 返回数量不匹配：请求 {len(texts)} 条，收到 {len(vectors)} 条。"
            )
        expected_dimension = self.metadata.vector_dimension
        actual_dimension = len(vectors[0]) if vectors else 0
        if expected_dimension and actual_dimension != expected_dimension:
            raise EmbeddingProviderError(
                f"{self.metadata.provider_code} 向量维度不匹配：期望 {expected_dimension}，实际 {actual_dimension}。"
            )
        if actual_dimension and self.metadata.vector_dimension == 0:
            self.metadata = EmbeddingProviderMetadata(
                provider_code=self.metadata.provider_code,
                model_name=self.metadata.model_name,
                vector_dimension=actual_dimension,
                max_tokens=self.metadata.max_tokens,
                is_builtin=self.metadata.is_builtin,
            )
        return vectors

    def _resolve_api_key(self) -> str | None:
        if not self._raw_api_key:
            return None
        prefix = settings.ai_secret_ref_prefix
        if self._raw_api_key.startswith(prefix):
            return os.getenv(self._raw_api_key[len(prefix):])
        if self._raw_api_key.startswith("env://"):
            return os.getenv(self._raw_api_key[len("env://"):])
        return self._raw_api_key

    @staticmethod
    def _resolve_endpoint(endpoint: str) -> str:
        normalized = endpoint.strip()
        if not normalized:
            return ""
        if normalized.endswith("/embeddings"):
            return normalized
        if normalized.endswith("/v1"):
            return normalized + "/embeddings"
        return normalized.rstrip("/") + "/v1/embeddings"
