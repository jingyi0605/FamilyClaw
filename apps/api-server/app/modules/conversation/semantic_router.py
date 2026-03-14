import json
import math
from dataclasses import dataclass
from pathlib import Path

from app.core.config import BASE_DIR, settings
from app.modules.conversation.capability_descriptors import (
    CAPABILITY_DESCRIPTOR_VERSION,
    CapabilityDescriptor,
    get_all_descriptors,
    get_descriptor_document_hash,
    get_lane_descriptors,
    get_proposal_descriptors,
)
from app.modules.embedding.service import EmbeddingExecutionResult, EmbeddingService, EmbeddingServiceUnavailableError

LANE_SCORE_THRESHOLD = 0.55
LANE_SCORE_MARGIN = 0.08
PROPOSAL_GATE_THRESHOLD = 0.62


@dataclass(frozen=True)
class LaneScore:
    lane: str
    descriptor_id: str
    score: float


@dataclass(frozen=True)
class ProposalGateScore:
    proposal_kind: str
    descriptor_id: str
    score: float
    passed: bool


@dataclass(frozen=True)
class SemanticRoutingResult:
    lane: str
    confidence: float
    reason: str
    target_kind: str
    requires_clarification: bool
    lane_scores: list[LaneScore]
    proposal_gate_scores: list[ProposalGateScore]
    provider_code: str | None
    fallback_used: bool
    descriptor_cache_hit: bool
    enabled: bool


@dataclass(frozen=True)
class _DescriptorEmbeddingBundle:
    descriptor_vectors: dict[str, list[float]]
    provider_code: str
    model_name: str
    vector_dimension: int
    cache_hit: bool


class SemanticRouter:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        *,
        lane_descriptors: tuple[CapabilityDescriptor, ...] | None = None,
        proposal_descriptors: tuple[CapabilityDescriptor, ...] | None = None,
        cache_dir: str | Path | None = None,
        enabled: bool | None = None,
        lane_score_threshold: float = LANE_SCORE_THRESHOLD,
        lane_score_margin: float = LANE_SCORE_MARGIN,
        proposal_gate_threshold: float = PROPOSAL_GATE_THRESHOLD,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.enabled = settings.conversation_embedding_provider_enabled if enabled is None else enabled
        self.lane_descriptors = lane_descriptors or get_lane_descriptors()
        self.proposal_descriptors = proposal_descriptors or get_proposal_descriptors()
        self.cache_dir = self._resolve_cache_dir(cache_dir)
        self.lane_score_threshold = lane_score_threshold
        self.lane_score_margin = lane_score_margin
        self.proposal_gate_threshold = proposal_gate_threshold
        self._memory_cache: dict[str, _DescriptorEmbeddingBundle] = {}

    def warmup_descriptor_embeddings(self, *, provider_code: str) -> bool:
        bundle = self._get_descriptor_bundle(provider_code)
        return bundle.cache_hit

    def route(self, user_message: str) -> SemanticRoutingResult:
        normalized_message = user_message.strip()
        if not self.enabled:
            return self._build_disabled_result("Embedding descriptor 路由开关关闭，继续保留 004.1 基线。")
        if not normalized_message:
            return self._build_disabled_result("用户消息为空，保守回到 free_chat。")
        try:
            message_embedding = self.embedding_service.embed_texts([normalized_message])
        except EmbeddingServiceUnavailableError as exc:
            return self._build_disabled_result(f"Embedding provider 不可用：{exc}")
        descriptor_bundle = self._get_descriptor_bundle(message_embedding.metadata.provider_code)
        lane_scores = self._score_lanes(message_embedding, descriptor_bundle)
        proposal_gate_scores = self._score_proposals(message_embedding, descriptor_bundle)
        lane, confidence, reason, requires_clarification = self._decide_lane(lane_scores)
        target_kind = {
            "fast_action": "device_action",
            "realtime_query": "state_query",
            "free_chat": "none",
        }[lane]
        return SemanticRoutingResult(
            lane=lane,
            confidence=confidence,
            reason=reason,
            target_kind=target_kind,
            requires_clarification=requires_clarification,
            lane_scores=lane_scores,
            proposal_gate_scores=proposal_gate_scores,
            provider_code=message_embedding.metadata.provider_code,
            fallback_used=message_embedding.fallback_used,
            descriptor_cache_hit=descriptor_bundle.cache_hit,
            enabled=True,
        )

    def _get_descriptor_bundle(self, provider_code: str) -> _DescriptorEmbeddingBundle:
        descriptor_hash = get_descriptor_document_hash(get_all_descriptors())
        memory_cache_key = f"{provider_code}:{descriptor_hash}"
        cached_bundle = self._memory_cache.get(memory_cache_key)
        if cached_bundle is not None:
            return cached_bundle
        cache_path = self._build_cache_path(provider_code, descriptor_hash)
        if cache_path.exists():
            cached = self._load_bundle_from_disk(cache_path)
            if cached is not None:
                bundle = _DescriptorEmbeddingBundle(
                    descriptor_vectors=cached["descriptor_vectors"],
                    provider_code=cached["provider_code"],
                    model_name=cached["model_name"],
                    vector_dimension=cached["vector_dimension"],
                    cache_hit=True,
                )
                self._memory_cache[memory_cache_key] = bundle
                return bundle
        documents = [descriptor.build_document() for descriptor in get_all_descriptors()]
        embedding_result = self.embedding_service.embed_texts(
            documents,
            provider_code=provider_code,
            allow_builtin_fallback=False,
        )
        descriptor_vectors = {
            descriptor.descriptor_id: vector
            for descriptor, vector in zip(get_all_descriptors(), embedding_result.vectors, strict=True)
        }
        payload = {
            "descriptor_version": CAPABILITY_DESCRIPTOR_VERSION,
            "provider_code": embedding_result.metadata.provider_code,
            "model_name": embedding_result.metadata.model_name,
            "vector_dimension": embedding_result.metadata.vector_dimension,
            "descriptor_vectors": descriptor_vectors,
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        bundle = _DescriptorEmbeddingBundle(
            descriptor_vectors=descriptor_vectors,
            provider_code=embedding_result.metadata.provider_code,
            model_name=embedding_result.metadata.model_name,
            vector_dimension=embedding_result.metadata.vector_dimension,
            cache_hit=False,
        )
        self._memory_cache[memory_cache_key] = bundle
        return bundle

    def _score_lanes(
        self,
        message_embedding: EmbeddingExecutionResult,
        descriptor_bundle: _DescriptorEmbeddingBundle,
    ) -> list[LaneScore]:
        message_vector = message_embedding.vectors[0]
        scored = [
            LaneScore(
                lane=descriptor.lane or "free_chat",
                descriptor_id=descriptor.descriptor_id,
                score=_cosine_similarity(message_vector, descriptor_bundle.descriptor_vectors[descriptor.descriptor_id]),
            )
            for descriptor in self.lane_descriptors
        ]
        return sorted(scored, key=lambda item: item.score, reverse=True)

    def _score_proposals(
        self,
        message_embedding: EmbeddingExecutionResult,
        descriptor_bundle: _DescriptorEmbeddingBundle,
    ) -> list[ProposalGateScore]:
        message_vector = message_embedding.vectors[0]
        scored: list[ProposalGateScore] = []
        for descriptor in self.proposal_descriptors:
            score = _cosine_similarity(message_vector, descriptor_bundle.descriptor_vectors[descriptor.descriptor_id])
            scored.append(
                ProposalGateScore(
                    proposal_kind=descriptor.proposal_kind or "",
                    descriptor_id=descriptor.descriptor_id,
                    score=score,
                    passed=score >= self.proposal_gate_threshold,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)

    def _decide_lane(self, lane_scores: list[LaneScore]) -> tuple[str, float, str, bool]:
        top_score = lane_scores[0]
        second_score = lane_scores[1] if len(lane_scores) > 1 else LaneScore(lane="free_chat", descriptor_id="", score=0.0)
        if top_score.score < self.lane_score_threshold:
            return "free_chat", top_score.score, "语义相似度不足，保守回到 free_chat。", False
        if top_score.lane != "free_chat" and (top_score.score - second_score.score) < self.lane_score_margin:
            return "free_chat", top_score.score, "Top1 与 Top2 分差不足，先澄清或保守回落。", True
        if top_score.lane == "free_chat":
            return "free_chat", top_score.score, "普通聊天命中 free_chat descriptor。", False
        return top_score.lane, top_score.score, f"命中 {top_score.descriptor_id}。", False

    @staticmethod
    def _resolve_cache_dir(cache_dir: str | Path | None) -> Path:
        if cache_dir is None:
            cache_dir = Path(settings.embedding_builtin_cache_dir) / "descriptor_cache"
        cache_path = Path(cache_dir)
        if cache_path.is_absolute():
            return cache_path
        return BASE_DIR.parents[1] / cache_path

    def _build_cache_path(self, provider_code: str, descriptor_hash: str) -> Path:
        normalized_provider_code = provider_code.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{normalized_provider_code}-{descriptor_hash}.json"

    @staticmethod
    def _load_bundle_from_disk(cache_path: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if payload.get("descriptor_version") != CAPABILITY_DESCRIPTOR_VERSION:
            return None
        descriptor_vectors = payload.get("descriptor_vectors")
        if not isinstance(descriptor_vectors, dict):
            return None
        vector_dimension = payload.get("vector_dimension")
        provider_code = payload.get("provider_code")
        model_name = payload.get("model_name")
        if not isinstance(vector_dimension, int) or not isinstance(provider_code, str) or not isinstance(model_name, str):
            return None
        normalized_vectors: dict[str, list[float]] = {}
        for key, value in descriptor_vectors.items():
            if not isinstance(key, str) or not isinstance(value, list):
                return None
            normalized_vectors[key] = [float(item) for item in value]
        return {
            "descriptor_vectors": normalized_vectors,
            "provider_code": provider_code,
            "model_name": model_name,
            "vector_dimension": vector_dimension,
        }

    @staticmethod
    def _build_disabled_result(reason: str) -> SemanticRoutingResult:
        return SemanticRoutingResult(
            lane="free_chat",
            confidence=0.0,
            reason=reason,
            target_kind="none",
            requires_clarification=False,
            lane_scores=[],
            proposal_gate_scores=[],
            provider_code=None,
            fallback_used=False,
            descriptor_cache_hit=False,
            enabled=False,
        )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_item * right_item for left_item, right_item in zip(left, right, strict=True))
    return dot / (left_norm * right_norm)
