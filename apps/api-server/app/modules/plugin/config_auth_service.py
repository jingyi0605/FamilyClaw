from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.utils import dump_json, load_json, new_uuid, utc_now_iso

from . import repository
from .models import PluginConfigAuthSession
from .schemas import PluginConfigAuthSessionMutation, PluginConfigAuthSessionRead
from .service import PluginServiceError


PLUGIN_CONFIG_AUTH_SESSION_NOT_FOUND = "plugin_config_auth_session_not_found"
PLUGIN_CONFIG_AUTH_SESSION_INVALID = "plugin_config_auth_session_invalid"
PLUGIN_CONFIG_AUTH_SESSION_EXPIRED = "plugin_config_auth_session_expired"
DEFAULT_PLUGIN_CONFIG_AUTH_SESSION_TTL_SECONDS = 10 * 60
PLUGIN_CONFIG_AUTH_SESSION_TERMINAL_STATUSES = {"completed", "failed", "expired", "cancelled"}


def resolve_plugin_config_callback_base_url(request_base_url: str | None) -> str:
    configured_base_url = str(getattr(settings, "base_url", "") or "").strip()
    if configured_base_url:
        return configured_base_url.rstrip("/")

    normalized_request_base_url = (request_base_url or "").strip()
    if normalized_request_base_url:
        return normalized_request_base_url.rstrip("/")

    raise PluginServiceError(
        "当前服务没有可公网访问的 base_url，无法生成插件认证回调地址。",
        error_code=PLUGIN_CONFIG_AUTH_SESSION_INVALID,
        status_code=400,
    )


def prepare_plugin_config_auth_session(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    scope_type: str,
    scope_key: str,
    action_key: str,
    callback_base_url: str,
    auth_session_id: str | None,
) -> PluginConfigAuthSession:
    del callback_base_url

    if auth_session_id:
        row = repository.get_plugin_config_auth_session(db, auth_session_id)
        if row is None or row.household_id != household_id or row.plugin_id != plugin_id:
            raise PluginServiceError(
                "指定的插件认证会话不存在。",
                error_code=PLUGIN_CONFIG_AUTH_SESSION_NOT_FOUND,
                field="auth_session_id",
                status_code=404,
            )
        if row.scope_type != scope_type or row.scope_key != scope_key or row.action_key != action_key:
            raise PluginServiceError(
                "指定的插件认证会话与当前配置动作不匹配。",
                error_code=PLUGIN_CONFIG_AUTH_SESSION_INVALID,
                field="auth_session_id",
                status_code=400,
            )
        _expire_auth_session_if_needed(row)
        return row

    now = utc_now_iso()
    row = PluginConfigAuthSession(
        id=new_uuid(),
        household_id=household_id,
        plugin_id=plugin_id,
        scope_type=scope_type,
        scope_key=scope_key,
        action_key=action_key,
        status="pending",
        callback_token=new_uuid().replace("-", ""),
        state_token=new_uuid().replace("-", ""),
        session_payload_json="{}",
        callback_payload_json=None,
        error_code=None,
        error_message=None,
        expires_at=_add_seconds(now, DEFAULT_PLUGIN_CONFIG_AUTH_SESSION_TTL_SECONDS),
        callback_received_at=None,
        finished_at=None,
        created_at=now,
        updated_at=now,
    )
    repository.add_plugin_config_auth_session(db, row)
    return row


def get_plugin_config_auth_session_read(
    db: Session,
    *,
    household_id: str,
    plugin_id: str,
    session_id: str,
    callback_base_url: str,
) -> PluginConfigAuthSessionRead:
    row = repository.get_plugin_config_auth_session(db, session_id)
    if row is None or row.household_id != household_id or row.plugin_id != plugin_id:
        raise PluginServiceError(
            "指定的插件认证会话不存在。",
            error_code=PLUGIN_CONFIG_AUTH_SESSION_NOT_FOUND,
            field="session_id",
            status_code=404,
        )

    _expire_auth_session_if_needed(row)
    return build_plugin_config_auth_session_read(row, callback_base_url=callback_base_url)


def build_plugin_config_auth_session_read(
    row: PluginConfigAuthSession,
    *,
    callback_base_url: str,
) -> PluginConfigAuthSessionRead:
    return PluginConfigAuthSessionRead(
        id=row.id,
        plugin_id=row.plugin_id,
        scope_type=row.scope_type,
        scope_key=row.scope_key,
        action_key=row.action_key,
        status=row.status,
        callback_url=build_plugin_config_auth_session_callback_url(
            callback_base_url=callback_base_url,
            session_id=row.id,
            callback_token=row.callback_token,
        ),
        expires_at=row.expires_at,
        callback_received_at=row.callback_received_at,
        finished_at=row.finished_at,
        error_code=row.error_code,
        error_message=row.error_message,
    )


def build_plugin_config_auth_session_context(
    row: PluginConfigAuthSession,
    *,
    callback_base_url: str,
) -> dict[str, Any]:
    _expire_auth_session_if_needed(row)
    session_payload = load_json(row.session_payload_json)
    callback_payload = load_json(row.callback_payload_json)
    return {
        "id": row.id,
        "plugin_id": row.plugin_id,
        "scope_type": row.scope_type,
        "scope_key": row.scope_key,
        "action_key": row.action_key,
        "status": row.status,
        "state_token": row.state_token,
        "callback_url": build_plugin_config_auth_session_callback_url(
            callback_base_url=callback_base_url,
            session_id=row.id,
            callback_token=row.callback_token,
        ),
        "expires_at": row.expires_at,
        "callback_received_at": row.callback_received_at,
        "finished_at": row.finished_at,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "session_payload": session_payload if isinstance(session_payload, dict) else {},
        "callback_payload": callback_payload if isinstance(callback_payload, dict) else None,
    }


def apply_plugin_config_auth_session_mutation(
    row: PluginConfigAuthSession,
    mutation: PluginConfigAuthSessionMutation | None,
) -> None:
    if mutation is None:
        return

    now = utc_now_iso()
    current_payload = load_json(row.session_payload_json)
    next_payload = current_payload if isinstance(current_payload, dict) else {}
    if mutation.clear_payload:
        next_payload = {}
    if mutation.payload:
        next_payload = dict(next_payload)
        next_payload.update(mutation.payload)
    row.session_payload_json = dump_json(next_payload) or "{}"

    if mutation.clear_callback_payload:
        row.callback_payload_json = None
        row.callback_received_at = None

    if mutation.status is not None:
        row.status = mutation.status
        if mutation.status in PLUGIN_CONFIG_AUTH_SESSION_TERMINAL_STATUSES:
            row.finished_at = now
        else:
            row.finished_at = None

    if mutation.expires_in_seconds is not None:
        row.expires_at = _add_seconds(now, mutation.expires_in_seconds)

    if mutation.error_code is not None:
        row.error_code = mutation.error_code
    elif mutation.status in {"pending", "callback_received", "completed"}:
        row.error_code = None

    if mutation.error_message is not None:
        row.error_message = mutation.error_message
    elif mutation.status in {"pending", "callback_received", "completed"}:
        row.error_message = None

    row.updated_at = now


def cleanup_unused_plugin_config_auth_session(db: Session, row: PluginConfigAuthSession) -> None:
    session_payload = load_json(row.session_payload_json)
    has_session_payload = isinstance(session_payload, dict) and bool(session_payload)
    if has_session_payload or row.callback_payload_json or row.callback_received_at:
        return
    if row.status != "pending":
        return
    row_state = sa_inspect(row)
    if row_state.pending:
        owning_session = row_state.session
        if owning_session is not None:
            owning_session.expunge(row)
        return
    if not row_state.persistent:
        return
    repository.delete_plugin_config_auth_session(db, row)


def record_plugin_config_auth_callback(
    db: Session,
    *,
    session_id: str,
    callback_token: str,
    method: str,
    headers: dict[str, str],
    query_params: dict[str, str],
    body: bytes,
) -> PluginConfigAuthSession:
    row = repository.get_plugin_config_auth_session(db, session_id)
    if row is None:
        raise PluginServiceError(
            "指定的插件认证会话不存在。",
            error_code=PLUGIN_CONFIG_AUTH_SESSION_NOT_FOUND,
            field="session_id",
            status_code=404,
        )

    if row.callback_token != callback_token:
        raise PluginServiceError(
            "插件认证回调 token 无效。",
            error_code=PLUGIN_CONFIG_AUTH_SESSION_INVALID,
            field="token",
            status_code=400,
        )

    _expire_auth_session_if_needed(row)
    if row.status == "expired":
        raise PluginServiceError(
            "插件认证会话已过期，请返回宿主页面重新发起认证。",
            error_code=PLUGIN_CONFIG_AUTH_SESSION_EXPIRED,
            field="token",
            status_code=410,
        )

    if row.status in PLUGIN_CONFIG_AUTH_SESSION_TERMINAL_STATUSES:
        return row

    now = utc_now_iso()
    row.callback_payload_json = dump_json(
        {
            "method": method.upper(),
            "query_params": dict(query_params),
            "headers": dict(headers),
            "body_text": body.decode("utf-8", errors="ignore"),
            "body_base64": base64.b64encode(body).decode("ascii"),
        }
    )
    row.callback_received_at = now
    row.updated_at = now
    row.status = "callback_received"
    row.finished_at = None
    row.error_code = None
    row.error_message = None
    return row


def build_plugin_config_auth_session_callback_url(
    *,
    callback_base_url: str,
    session_id: str,
    callback_token: str,
) -> str:
    query = urlencode({"token": callback_token})
    return (
        f"{callback_base_url}{settings.api_v1_prefix}"
        f"/ai-config/plugin-config-auth-sessions/{session_id}/callback?{query}"
    )


def _expire_auth_session_if_needed(row: PluginConfigAuthSession) -> bool:
    if row.status not in {"pending", "callback_received"}:
        return False

    expires_at = _parse_utc_iso(row.expires_at)
    if expires_at > datetime.now(UTC):
        return False

    now = utc_now_iso()
    row.status = "expired"
    row.finished_at = now
    row.updated_at = now
    row.error_code = row.error_code or PLUGIN_CONFIG_AUTH_SESSION_EXPIRED
    row.error_message = row.error_message or "插件认证会话已过期，请重新发起认证。"
    return True


def _parse_utc_iso(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value[:-1] + "+00:00")
    return datetime.fromisoformat(value)


def _add_seconds(value: str, seconds: int) -> str:
    return (_parse_utc_iso(value) + timedelta(seconds=seconds)).isoformat(timespec="microseconds").replace("+00:00", "Z")
