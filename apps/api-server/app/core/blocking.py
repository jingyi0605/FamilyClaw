from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Executor
from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeVar

from sqlalchemy.orm import Session, sessionmaker


T = TypeVar("T")
BlockingCallKind = Literal["sync_db", "sync_network", "plugin_code", "cpu_bound"]


@dataclass(slots=True, frozen=True)
class BlockingCallPolicy:
    label: str
    kind: BlockingCallKind
    timeout_seconds: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("label 不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")


class BlockingCallTimeoutError(TimeoutError):
    def __init__(self, policy: BlockingCallPolicy):
        super().__init__(f"阻塞调用超时: {policy.label}")
        self.policy = policy


async def run_blocking(
    func: Callable[[], T],
    *,
    policy: BlockingCallPolicy,
    executor: Executor | None = None,
    logger: logging.Logger | None = None,
    context: dict[str, Any] | None = None,
) -> T:
    logger = logger or logging.getLogger(__name__)
    if executor is None:
        awaitable = asyncio.to_thread(func)
    else:
        loop = asyncio.get_running_loop()
        awaitable = loop.run_in_executor(executor, func)

    try:
        return await asyncio.wait_for(awaitable, timeout=policy.timeout_seconds)
    except asyncio.TimeoutError as exc:
        logger.warning(
            "阻塞调用超时 label=%s kind=%s timeout_seconds=%s context=%s",
            policy.label,
            policy.kind,
            policy.timeout_seconds,
            context or {},
        )
        raise BlockingCallTimeoutError(policy) from exc


async def run_blocking_db(
    func: Callable[[Session], T],
    *,
    session_factory: sessionmaker[Session],
    policy: BlockingCallPolicy,
    commit: bool = False,
    executor: Executor | None = None,
    logger: logging.Logger | None = None,
    context: dict[str, Any] | None = None,
) -> T:
    # 线程池里的数据库逻辑必须自己拿 Session，不能复用调用方线程里的 Session。
    def _run_with_thread_session() -> T:
        with session_factory() as db:
            try:
                result = func(db)
                if commit:
                    db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    return await run_blocking(
        _run_with_thread_session,
        policy=policy,
        executor=executor,
        logger=logger,
        context=context,
    )
