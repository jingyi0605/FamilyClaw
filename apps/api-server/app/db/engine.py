from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url

DEFAULT_DB_POOL_SIZE = 10
DEFAULT_DB_MAX_OVERFLOW = 20
DEFAULT_DB_POOL_TIMEOUT_SECONDS = 30
DEFAULT_DB_POOL_RECYCLE_SECONDS = 1800


def make_database_url(database_url: str | URL) -> URL:
    return database_url if isinstance(database_url, URL) else make_url(database_url)


def is_postgresql_url(database_url: str | URL) -> bool:
    return make_database_url(database_url).get_backend_name() == "postgresql"


def ensure_postgresql_url(database_url: str | URL) -> URL:
    url = make_database_url(database_url)
    if not is_postgresql_url(url):
        raise ValueError(f"仅支持 PostgreSQL 数据库连接，当前收到: {url.get_backend_name()}")
    return url


def build_database_engine_kwargs(
    database_url: str | URL,
    *,
    pool_size: int = DEFAULT_DB_POOL_SIZE,
    max_overflow: int = DEFAULT_DB_MAX_OVERFLOW,
    pool_timeout_seconds: int = DEFAULT_DB_POOL_TIMEOUT_SECONDS,
    pool_recycle_seconds: int = DEFAULT_DB_POOL_RECYCLE_SECONDS,
) -> dict[str, Any]:
    ensure_postgresql_url(database_url)
    return {
        "future": True,
        "pool_pre_ping": True,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout_seconds,
        "pool_recycle": pool_recycle_seconds,
    }


def build_database_engine(
    database_url: str | URL,
    *,
    pool_size: int = DEFAULT_DB_POOL_SIZE,
    max_overflow: int = DEFAULT_DB_MAX_OVERFLOW,
    pool_timeout_seconds: int = DEFAULT_DB_POOL_TIMEOUT_SECONDS,
    pool_recycle_seconds: int = DEFAULT_DB_POOL_RECYCLE_SECONDS,
) -> Engine:
    kwargs = build_database_engine_kwargs(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout_seconds=pool_timeout_seconds,
        pool_recycle_seconds=pool_recycle_seconds,
    )
    return create_engine(str(database_url), **kwargs)
