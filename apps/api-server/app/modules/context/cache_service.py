from __future__ import annotations

from threading import Lock
from typing import Any

from app.core.config import settings

_CACHE_LOCK = Lock()
_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}


class ContextCacheUnavailableError(RuntimeError):
    pass


def refresh_household_context_cache(household_id: str, payload: dict[str, Any]) -> bool:
    if not settings.context_cache_enabled:
        raise ContextCacheUnavailableError("context cache disabled")

    with _CACHE_LOCK:
        _CONTEXT_CACHE[household_id] = payload
    return True


def get_household_context_cache(household_id: str) -> dict[str, Any] | None:
    if not settings.context_cache_enabled:
        raise ContextCacheUnavailableError("context cache disabled")

    with _CACHE_LOCK:
        payload = _CONTEXT_CACHE.get(household_id)
        return dict(payload) if payload is not None else None
