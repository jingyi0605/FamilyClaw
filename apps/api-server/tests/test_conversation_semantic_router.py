import tempfile
import unittest
from pathlib import Path

from app.core.config import EmbeddingProviderRuntimeConfig, EmbeddingRuntimeConfig
from app.modules.conversation.semantic_router import SemanticRouter
from app.modules.embedding.provider import EmbeddingProviderError, EmbeddingProviderMetadata
from app.modules.embedding.provider_registry import EmbeddingProviderRegistry
from app.modules.embedding.providers.builtin_bge_small_zh_v15 import BUILTIN_PROVIDER_CODE
from app.modules.embedding.service import EmbeddingService


class _KeywordEmbeddingProvider:
    def __init__(self, provider_code: str = BUILTIN_PROVIDER_CODE) -> None:
        self.metadata = EmbeddingProviderMetadata(
            provider_code=provider_code,
            model_name="test-keyword-model",
            vector_dimension=6,
            is_builtin=provider_code == BUILTIN_PROVIDER_CODE,
        )
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        normalized = text.lower()
        return [
            float(self._count(normalized, ("打开", "关掉", "关闭", "停止", "执行", "灯", "空调", "门锁", "窗帘"))),
            float(self._count(normalized, ("现在", "状态", "多少", "谁在家", "温度", "还有", "锁了吗", "提醒"))),
            float(self._count(normalized, ("故事", "聊天", "笑话", "心情", "聊会", "春天", "累"))),
            float(self._count(normalized, ("记住", "喜欢", "习惯", "过敏", "早餐", "周末", "带孩子"))),
            float(self._count(normalized, ("以后", "默认", "改成", "别播报", "称呼", "先发消息", "通知"))),
            float(self._count(normalized, ("明天", "周五", "下午", "晚上", "提醒", "记得", "下周一"))),
        ]

    @staticmethod
    def _count(text: str, keywords: tuple[str, ...]) -> int:
        return sum(text.count(keyword) for keyword in keywords)


class _FailingProvider:
    def __init__(self, provider_code: str) -> None:
        self.metadata = EmbeddingProviderMetadata(
            provider_code=provider_code,
            model_name="broken-provider",
            vector_dimension=6,
            is_builtin=False,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderError("remote provider down")


class ConversationSemanticRouterTests(unittest.TestCase):
    def test_semantic_router_hits_fast_action_descriptor(self) -> None:
        provider = _KeywordEmbeddingProvider()
        router = self._build_router(provider=provider)

        result = router.route("把客厅灯关掉")

        self.assertTrue(result.enabled)
        self.assertEqual("fast_action", result.lane)
        self.assertEqual("device_action", result.target_kind)
        self.assertGreaterEqual(result.confidence, 0.55)
        self.assertEqual("fast_action.device_control", result.lane_scores[0].descriptor_id)

    def test_semantic_router_falls_back_when_scores_too_close(self) -> None:
        provider = _KeywordEmbeddingProvider()
        router = self._build_router(provider=provider)

        result = router.route("现在看看家里状态，顺便把灯关掉")

        self.assertEqual("free_chat", result.lane)
        self.assertTrue(result.requires_clarification)
        self.assertIn("分差不足", result.reason)

    def test_semantic_router_reuses_descriptor_cache(self) -> None:
        provider = _KeywordEmbeddingProvider()
        with tempfile.TemporaryDirectory() as tempdir:
            router = self._build_router(provider=provider, cache_dir=tempdir)
            first_result = router.route("把客厅灯关掉")
            self.assertFalse(first_result.descriptor_cache_hit)
            self.assertEqual(2, len(provider.calls))

            second_router = self._build_router(provider=provider, cache_dir=tempdir)
            second_result = second_router.route("现在家里有人吗")
            self.assertTrue(second_result.descriptor_cache_hit)
            self.assertEqual(3, len(provider.calls))
            self.assertTrue(any(Path(tempdir).iterdir()))

    def test_embedding_service_falls_back_to_builtin_when_remote_unavailable(self) -> None:
        builtin_provider = _KeywordEmbeddingProvider()
        registry = EmbeddingProviderRegistry(
            runtime_config=EmbeddingRuntimeConfig(
                default_provider_code="remote-openai",
                builtin_model_name="BAAI/bge-small-zh-v1.5",
                builtin_cache_dir="apps/api-server/data/models/embeddings",
                default_timeout_ms=3000,
                provider_configs={
                    "remote-openai": EmbeddingProviderRuntimeConfig(
                        provider_code="remote-openai",
                        model_name="remote-embedding",
                        endpoint="https://example.com",
                        enabled=True,
                        fallback_to_builtin=True,
                    )
                },
            ),
            builtin_factory=lambda runtime: builtin_provider,
            remote_factory=lambda provider_config, runtime, provider_code: _FailingProvider(provider_code),
        )
        service = EmbeddingService(
            runtime_config=registry.runtime_config,
            registry=registry,
            builtin_fallback_enabled=True,
        )

        result = service.embed_texts(["把客厅灯关掉"])

        self.assertTrue(result.fallback_used)
        self.assertEqual(BUILTIN_PROVIDER_CODE, result.metadata.provider_code)
        self.assertEqual(1, len(builtin_provider.calls))

    @staticmethod
    def _build_router(provider: _KeywordEmbeddingProvider, cache_dir: str | None = None) -> SemanticRouter:
        runtime_config = EmbeddingRuntimeConfig(
            default_provider_code=BUILTIN_PROVIDER_CODE,
            builtin_model_name="BAAI/bge-small-zh-v1.5",
            builtin_cache_dir="apps/api-server/data/models/embeddings",
            default_timeout_ms=3000,
            provider_configs={},
        )
        registry = EmbeddingProviderRegistry(
            runtime_config=runtime_config,
            builtin_factory=lambda runtime: provider,
            remote_factory=lambda provider_config, runtime, provider_code: provider,
        )
        service = EmbeddingService(
            runtime_config=runtime_config,
            registry=registry,
            builtin_fallback_enabled=True,
        )
        return SemanticRouter(
            embedding_service=service,
            cache_dir=cache_dir,
            enabled=True,
        )
