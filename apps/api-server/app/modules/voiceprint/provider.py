from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from threading import Lock
from typing import Sequence

from app.core.config import settings


DEFAULT_VOICEPRINT_PROVIDER_CODE = "sherpa_onnx_wespeaker_resnet34"
_PREPROCESS_TRIM_RATIO = 0.02
_PREPROCESS_TRIM_MIN_AMPLITUDE = 0.005
_PREPROCESS_TRIM_PAD_MS = 80
_PREPROCESS_VAD_FRAME_MS = 30
_PREPROCESS_VAD_HOP_MS = 10
_PREPROCESS_VAD_PAD_MS = 120
_PREPROCESS_VAD_MIN_KEEP_MS = 400
_PREPROCESS_TARGET_RMS = 0.08
_PREPROCESS_MAX_GAIN = 8.0
_PREPROCESS_PEAK_LIMIT = 0.95


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


def _trim_silence(samples, sample_rate: int):
    abs_samples = samples.__abs__()
    if int(abs_samples.size) == 0:
        return samples, {"applied": False, "reason": "empty"}
    peak = float(abs_samples.max())
    threshold = max(_PREPROCESS_TRIM_MIN_AMPLITUDE, peak * _PREPROCESS_TRIM_RATIO)
    non_silent = abs_samples >= threshold
    if not bool(non_silent.any()):
        return samples, {"applied": False, "reason": "no_non_silent", "threshold": round(threshold, 6)}

    indices = non_silent.nonzero()[0]
    pad = max(int(sample_rate * _PREPROCESS_TRIM_PAD_MS / 1000), 0)
    start = max(int(indices[0]) - pad, 0)
    end = min(int(indices[-1]) + pad + 1, int(samples.shape[0]))
    trimmed = samples[start:end]
    return trimmed, {
        "applied": start > 0 or end < int(samples.shape[0]),
        "threshold": round(threshold, 6),
        "start": start,
        "end": end,
        "output_frames": int(trimmed.shape[0]),
    }


def _apply_energy_vad(samples, sample_rate: int):
    total_frames = int(samples.shape[0])
    if total_frames <= 0:
        return samples, {"applied": False, "reason": "empty"}

    frame_size = max(int(sample_rate * _PREPROCESS_VAD_FRAME_MS / 1000), 1)
    hop_size = max(int(sample_rate * _PREPROCESS_VAD_HOP_MS / 1000), 1)
    if total_frames <= frame_size:
        return samples, {"applied": False, "reason": "too_short"}

    energies = []
    starts = []
    start = 0
    while start < total_frames:
        end = min(start + frame_size, total_frames)
        frame = samples[start:end]
        energies.append(float((frame * frame).mean()))
        starts.append(start)
        if end >= total_frames:
            break
        start += hop_size

    if not energies:
        return samples, {"applied": False, "reason": "no_frames"}

    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise VoiceprintProviderError("voiceprint_provider_unavailable", f"missing numpy dependency: {exc.name}") from exc

    energy_array = np.asarray(energies, dtype="float32")
    max_energy = float(energy_array.max())
    noise_floor = float(np.percentile(energy_array, 20))
    threshold = max(noise_floor * 2.5, max_energy * 0.1, 1e-5)
    voiced_frames = energy_array >= threshold
    if not bool(voiced_frames.any()):
        return samples, {"applied": False, "reason": "no_voiced_frame", "threshold": round(threshold, 6)}

    mask = np.zeros(total_frames, dtype=bool)
    pad = max(int(sample_rate * _PREPROCESS_VAD_PAD_MS / 1000), 0)
    for index, is_voiced in enumerate(voiced_frames.tolist()):
        if not is_voiced:
            continue
        frame_start = max(starts[index] - pad, 0)
        frame_end = min(starts[index] + frame_size + pad, total_frames)
        mask[frame_start:frame_end] = True

    kept = samples[mask]
    min_keep_frames = max(int(sample_rate * _PREPROCESS_VAD_MIN_KEEP_MS / 1000), 1)
    if int(kept.shape[0]) < min_keep_frames:
        return samples, {
            "applied": False,
            "reason": "kept_too_short",
            "threshold": round(threshold, 6),
            "kept_frames": int(kept.shape[0]),
        }

    return kept, {
        "applied": True,
        "threshold": round(threshold, 6),
        "kept_frames": int(kept.shape[0]),
        "original_frames": total_frames,
    }


def _normalize_loudness(samples):
    rms = float(sqrt(float((samples * samples).mean())))
    peak = float(samples.__abs__().max()) if int(samples.shape[0]) > 0 else 0.0
    if rms <= 0 or peak <= 0:
        return samples, {"applied": False, "reason": "silent", "rms": round(rms, 6), "peak": round(peak, 6)}

    target_gain = min(_PREPROCESS_TARGET_RMS / rms, _PREPROCESS_MAX_GAIN)
    peak_gain = _PREPROCESS_PEAK_LIMIT / peak
    gain = min(target_gain, peak_gain)
    if gain <= 0:
        return samples, {"applied": False, "reason": "invalid_gain", "rms": round(rms, 6), "peak": round(peak, 6)}

    normalized = samples * gain
    normalized_peak = float(normalized.__abs__().max()) if int(normalized.shape[0]) > 0 else 0.0
    if normalized_peak > _PREPROCESS_PEAK_LIMIT and normalized_peak > 0:
        normalized = normalized * (_PREPROCESS_PEAK_LIMIT / normalized_peak)
        normalized_peak = float(normalized.__abs__().max())

    normalized_rms = float(sqrt(float((normalized * normalized).mean())))
    return normalized, {
        "applied": abs(gain - 1.0) > 1e-3,
        "gain": round(gain, 6),
        "rms_before": round(rms, 6),
        "rms_after": round(normalized_rms, 6),
        "peak_after": round(normalized_peak, 6),
    }


def preprocess_waveform(samples, sample_rate: int):
    trimmed, trim_meta = _trim_silence(samples, sample_rate)
    voiced, vad_meta = _apply_energy_vad(trimmed, sample_rate)
    normalized, loudness_meta = _normalize_loudness(voiced)
    return normalized, {
        "trim": trim_meta,
        "vad": vad_meta,
        "loudness": loudness_meta,
        "input_frames": int(samples.shape[0]),
        "output_frames": int(normalized.shape[0]),
    }


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
            import numpy as np
            import soundfile as sf
            import sherpa_onnx
        except ModuleNotFoundError as exc:
            raise VoiceprintProviderError(
                "voiceprint_provider_unavailable",
                f"缺少声纹依赖，无法加载 sherpa-onnx provider: {exc.name}",
            ) from exc

        samples, sample_rate = sf.read(str(waveform_path), dtype="float32", always_2d=False)
        samples = np.asarray(samples, dtype="float32")
        if hasattr(samples, "ndim") and getattr(samples, "ndim") > 1:
            samples = samples.mean(axis=1)
        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        samples, preprocess_metadata = preprocess_waveform(samples, int(sample_rate))

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
                "preprocess": preprocess_metadata,
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
