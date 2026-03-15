from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from threading import Lock
from typing import Sequence

from app.core.config import settings


DEFAULT_VOICEPRINT_PROVIDER_CODE = "sherpa_onnx_wespeaker_resnet34"


class VoiceprintProviderError(RuntimeError):
    """声纹 provider 的显式失败。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class VoiceprintEmbedding:
    provider: str
    vector: list[float]
    dimension: int
    audio_path: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceprintProfileData:
    provider: str
    provider_profile_ref: str
    embedding: list[float]
    sample_count: int
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceprintProfileCandidate:
    profile_id: str
    member_id: str
    embedding: list[float]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class VoiceprintSearchHit:
    profile_id: str
    member_id: str
    score: float


@dataclass(slots=True)
class VoiceprintSearchResult:
    provider: str
    status: str
    threshold: float
    hits: list[VoiceprintSearchHit]

    @property
    def top_hit(self) -> VoiceprintSearchHit | None:
        return self.hits[0] if self.hits else None


@dataclass(slots=True)
class VoiceprintVerifyResult:
    provider: str
    status: str
    threshold: float
    matched: bool
    score: float


class VoiceprintProvider:
    provider_code = DEFAULT_VOICEPRINT_PROVIDER_CODE

    def extract_embedding(self, audio_path: str) -> VoiceprintEmbedding:
        raise NotImplementedError

    def build_profile(
        self,
        *,
        member_id: str,
        embeddings: Sequence[VoiceprintEmbedding],
        source_sample_ids: Sequence[str],
        source_profile_id: str | None,
    ) -> VoiceprintProfileData:
        if not embeddings:
            raise VoiceprintProviderError("voiceprint_provider_invalid_input", "没有可用样本，无法构建声纹档案")
        aggregated = aggregate_embedding_vectors([item.vector for item in embeddings])
        return VoiceprintProfileData(
            provider=self.provider_code,
            provider_profile_ref=f"local:{member_id}:{len(source_sample_ids)}",
            embedding=aggregated,
            sample_count=len(embeddings),
            metadata={
                "source_sample_ids": list(source_sample_ids),
                "source_profile_id": source_profile_id,
                "query_window_ms": {
                    "min": settings.voiceprint_query_window_min_ms,
                    "max": settings.voiceprint_query_window_max_ms,
                },
            },
        )

    def search(
        self,
        *,
        query_embedding: Sequence[float],
        candidates: Sequence[VoiceprintProfileCandidate],
        threshold: float | None = None,
        limit: int = 3,
    ) -> VoiceprintSearchResult:
        normalized_query = normalize_embedding(query_embedding)
        score_threshold = threshold if threshold is not None else settings.voiceprint_search_score_threshold
        hits = [
            VoiceprintSearchHit(
                profile_id=item.profile_id,
                member_id=item.member_id,
                score=round(cosine_similarity(normalized_query, item.embedding), 4),
            )
            for item in candidates
        ]
        hits.sort(key=lambda item: item.score, reverse=True)
        limited_hits = hits[: max(limit, 1)]
        status = "no_profile"
        if limited_hits:
            status = "matched" if limited_hits[0].score >= score_threshold else "low_confidence"
        return VoiceprintSearchResult(
            provider=self.provider_code,
            status=status,
            threshold=score_threshold,
            hits=limited_hits,
        )

    def verify(
        self,
        *,
        query_embedding: Sequence[float],
        profile_embedding: Sequence[float],
        threshold: float | None = None,
    ) -> VoiceprintVerifyResult:
        score_threshold = threshold if threshold is not None else settings.voiceprint_verify_score_threshold
        score = round(cosine_similarity(query_embedding, profile_embedding), 4)
        return VoiceprintVerifyResult(
            provider=self.provider_code,
            status="matched" if score >= score_threshold else "low_confidence",
            threshold=score_threshold,
            matched=score >= score_threshold,
            score=score,
        )


class SherpaOnnxVoiceprintProvider(VoiceprintProvider):
    """首版固定使用 sherpa-onnx + weSpeaker/ResNet34。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._extractor: object | None = None
        self._loaded_model_path: str | None = None

    def extract_embedding(self, audio_path: str) -> VoiceprintEmbedding:
        model_path = Path(settings.voiceprint_model_path).expanduser().resolve()
        waveform_path = Path(audio_path).expanduser().resolve()
        if not settings.voiceprint_provider_enabled:
            raise VoiceprintProviderError("voiceprint_provider_disabled", "声纹 provider 当前被关闭")
        if not waveform_path.is_file():
            raise VoiceprintProviderError("voiceprint_artifact_missing", f"样本文件不存在: {waveform_path}")
        if not model_path.is_file():
            raise VoiceprintProviderError("voiceprint_model_missing", f"声纹模型不存在: {model_path}")

        try:
            import soundfile as sf
            import sherpa_onnx
        except ModuleNotFoundError as exc:
            raise VoiceprintProviderError(
                "voiceprint_provider_unavailable",
                f"缺少声纹依赖，无法加载 sherpa-onnx provider: {exc.name}",
            ) from exc

        samples, sample_rate = sf.read(str(waveform_path), dtype="float32", always_2d=False)
        if hasattr(samples, "ndim") and getattr(samples, "ndim") > 1:
            samples = samples.mean(axis=1)

        extractor = self._get_or_create_extractor(sherpa_onnx=sherpa_onnx, model_path=str(model_path))
        stream = extractor.create_stream()
        stream.accept_waveform(sample_rate, samples)
        stream.input_finished()
        vector = normalize_embedding([float(item) for item in extractor.compute(stream)])
        return VoiceprintEmbedding(
            provider=self.provider_code,
            vector=vector,
            dimension=len(vector),
            audio_path=str(waveform_path),
            metadata={
                "model_path": str(model_path),
                "sample_rate": int(sample_rate),
                "execution_provider": settings.voiceprint_execution_provider,
            },
        )

    def _get_or_create_extractor(self, *, sherpa_onnx: object, model_path: str) -> object:
        with self._lock:
            if self._extractor is not None and self._loaded_model_path == model_path:
                return self._extractor

            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=model_path,
                num_threads=settings.voiceprint_num_threads,
                provider=settings.voiceprint_execution_provider,
            )
            if hasattr(config, "validate") and not config.validate():
                raise VoiceprintProviderError("voiceprint_provider_invalid_config", "sherpa-onnx 声纹配置无效")

            self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            self._loaded_model_path = model_path
            return self._extractor


def normalize_embedding(vector: Sequence[float]) -> list[float]:
    values = [float(item) for item in vector]
    if not values:
        raise VoiceprintProviderError("voiceprint_embedding_invalid", "embedding 为空")
    norm = sqrt(sum(item * item for item in values))
    if norm <= 0:
        raise VoiceprintProviderError("voiceprint_embedding_invalid", "embedding 范数非法")
    return [item / norm for item in values]


def aggregate_embedding_vectors(vectors: Sequence[Sequence[float]]) -> list[float]:
    normalized_vectors = [normalize_embedding(vector) for vector in vectors]
    dimension = len(normalized_vectors[0])
    if any(len(vector) != dimension for vector in normalized_vectors):
        raise VoiceprintProviderError("voiceprint_embedding_dimension_mismatch", "embedding 维度不一致")

    aggregated = [
        sum(vector[index] for vector in normalized_vectors) / len(normalized_vectors)
        for index in range(dimension)
    ]
    return normalize_embedding(aggregated)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    normalized_left = normalize_embedding(left)
    normalized_right = normalize_embedding(right)
    if len(normalized_left) != len(normalized_right):
        raise VoiceprintProviderError("voiceprint_embedding_dimension_mismatch", "embedding 维度不一致")
    return sum(a * b for a, b in zip(normalized_left, normalized_right, strict=True))


_default_voiceprint_provider: VoiceprintProvider = SherpaOnnxVoiceprintProvider()


def get_default_voiceprint_provider() -> VoiceprintProvider:
    return _default_voiceprint_provider
