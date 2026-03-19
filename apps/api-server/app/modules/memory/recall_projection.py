from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, datetime
from typing import Any

from app.db.utils import load_json

MEMORY_RECALL_PROJECTION_VERSION = 1
MEMORY_RECALL_EMBEDDING_DIMENSION = 16
RECENT_EVENT_MEMORY_TYPES = {"event", "growth", "observation"}
STABLE_FACT_MEMORY_TYPES = {"fact", "preference", "relation"}
SEARCH_STOP_TERMS = {"什么", "一下", "请问", "吗", "呢", "呀", "最近"}


def extract_search_terms(text: str | None) -> list[str]:
    normalized_text = normalize_search_text(text)
    if not normalized_text:
        return []

    terms: list[str] = [normalized_text]
    parts = [
        part.strip()
        for part in re.split(r"[\s,，。！？?、;；:：/\\|()（）]+", normalized_text)
        if part.strip()
    ]
    terms.extend(parts)

    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", normalized_text)
    for chunk in chinese_chunks:
        terms.append(chunk)
        if len(chunk) >= 2:
            for index in range(len(chunk) - 1):
                terms.append(chunk[index : index + 2])

    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = normalize_search_text(term)
        if len(cleaned) < 2:
            continue
        if cleaned in SEARCH_STOP_TERMS:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        unique_terms.append(cleaned)
    return unique_terms


def normalize_search_text(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(str(text).strip().lower().split())


def build_memory_card_search_text(
    *,
    memory_type: str,
    title: str,
    summary: str,
    normalized_text: str | None,
    content_json: str | None = None,
    content: Any | None = None,
) -> str:
    content_value = content if content is not None else load_json(content_json)
    raw_parts: list[str] = [memory_type, title, summary]
    if normalized_text:
        raw_parts.append(normalized_text)
    raw_parts.extend(_flatten_search_text(content_value))

    original_text = " ".join(part for part in raw_parts if normalize_search_text(part))
    expanded_terms: list[str] = []
    for part in raw_parts:
        expanded_terms.extend(extract_search_terms(part))
    merged = " ".join(filter(None, [normalize_search_text(original_text), " ".join(expanded_terms)]))
    return normalize_search_text(merged)


def build_text_embedding(search_text: str | None, *, dimension: int = MEMORY_RECALL_EMBEDDING_DIMENSION) -> list[float] | None:
    normalized_text = normalize_search_text(search_text)
    if not normalized_text:
        return None

    tokens = extract_search_terms(normalized_text)
    if not tokens:
        tokens = [normalized_text]

    vector = [0.0] * dimension
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
        index = int(digest[:8], 16) % dimension
        sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
        weight = max(1.0, min(float(len(token)), 6.0))
        vector[index] += sign * weight

    norm = math.sqrt(sum(item * item for item in vector))
    if norm <= 0:
        return None

    return [round(item / norm, 6) for item in vector]


def to_vector_literal(vector: list[float] | None) -> str | None:
    if not vector:
        return None
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def derive_memory_group(memory_type: str) -> str:
    if memory_type in RECENT_EVENT_MEMORY_TYPES:
        return "recent_events"
    return "stable_facts"


def compute_recency_score(*timestamps: str | None, now: datetime | None = None) -> float:
    baseline = now or datetime.now(UTC)
    parsed_times = [parsed for parsed in (_parse_iso_datetime(item) for item in timestamps) if parsed is not None]
    if not parsed_times:
        return 0.0

    latest = max(parsed_times)
    age_seconds = max(0.0, (baseline - latest).total_seconds())
    half_life_seconds = 30 * 24 * 60 * 60
    score = math.exp(-age_seconds / half_life_seconds)
    return round(max(0.0, min(score, 1.0)), 6)


def build_tsquery_text(query: str | None) -> str | None:
    terms = extract_search_terms(query)
    if not terms:
        return None
    escaped_terms = [term.replace("'", "''") for term in terms[:24]]
    return " | ".join(f"'{term}'" for term in escaped_terms)


def _flatten_search_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        normalized = normalize_search_text(value)
        return [normalized] if normalized else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(_flatten_search_text(item))
        return parts
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_flatten_search_text(item))
        return parts
    return []


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
