from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from threading import Lock
from typing import Iterator

from sqlalchemy.orm import Session

from app.modules.scene import repository
from app.modules.scene.schemas import SceneTemplateRead

_execution_lock_registry: set[str] = set()
_execution_lock_guard = Lock()


def build_trigger_key(
    template: SceneTemplateRead,
    *,
    trigger_source: str,
    trigger_payload: dict[str, object] | None = None,
) -> str:
    normalized_payload = trigger_payload or {}
    fingerprint = {
        "template_code": template.template_code,
        "template_version": template.version,
        "trigger_source": trigger_source,
        "payload": normalized_payload,
    }
    digest = hashlib.sha256(
        json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return f"{template.template_code}:{digest}"


def build_execution_lock_key(template_id: str, trigger_key: str) -> str:
    return f"{template_id}:{trigger_key}"


def is_trigger_blocked_by_cooldown(
    db: Session,
    *,
    template: SceneTemplateRead,
    trigger_key: str,
    now: datetime | None = None,
) -> bool:
    if template.cooldown_seconds <= 0:
        return False

    latest_execution = repository.get_latest_execution_by_trigger(
        db,
        template_id=template.id,
        trigger_key=trigger_key,
    )
    if latest_execution is None:
        return False

    latest_started_at = _parse_utc_iso(latest_execution.started_at)
    if now is None:
        now = datetime.now(timezone.utc)
    return now < latest_started_at + timedelta(seconds=template.cooldown_seconds)


def acquire_execution_lock(lock_key: str) -> bool:
    with _execution_lock_guard:
        if lock_key in _execution_lock_registry:
            return False
        _execution_lock_registry.add(lock_key)
        return True


def release_execution_lock(lock_key: str) -> None:
    with _execution_lock_guard:
        _execution_lock_registry.discard(lock_key)


@contextmanager
def scene_execution_lock(lock_key: str) -> Iterator[bool]:
    acquired = acquire_execution_lock(lock_key)
    try:
        yield acquired
    finally:
        if acquired:
            release_execution_lock(lock_key)


def can_start_scene_execution(
    db: Session,
    *,
    template: SceneTemplateRead,
    trigger_source: str,
    trigger_payload: dict[str, object] | None = None,
    now: datetime | None = None,
) -> tuple[bool, str | None, str, str]:
    trigger_key = build_trigger_key(
        template,
        trigger_source=trigger_source,
        trigger_payload=trigger_payload,
    )
    lock_key = build_execution_lock_key(template.id, trigger_key)

    if is_trigger_blocked_by_cooldown(
        db,
        template=template,
        trigger_key=trigger_key,
        now=now,
    ):
        return False, "命中场景冷却时间，当前不重复执行", trigger_key, lock_key

    if not acquire_execution_lock(lock_key):
        return False, "相同场景正在执行，当前不重复启动", trigger_key, lock_key

    release_execution_lock(lock_key)
    return True, None, trigger_key, lock_key


def _parse_utc_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
