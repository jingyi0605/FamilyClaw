from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from websockets.sync.client import ClientConnection, connect as websocket_connect


logger = logging.getLogger(__name__)

_DINGTALK_API_BASE_URL = "https://api.dingtalk.com"
_DINGTALK_OAUTH_URL = f"{_DINGTALK_API_BASE_URL}/v1.0/oauth2/accessToken"
_DINGTALK_STREAM_OPEN_URL = f"{_DINGTALK_API_BASE_URL}/v1.0/gateway/connections/open"
_DINGTALK_DIRECT_SEND_URL = f"{_DINGTALK_API_BASE_URL}/v1.0/robot/oToMessages/batchSend"
_DINGTALK_GROUP_SEND_URL = f"{_DINGTALK_API_BASE_URL}/v1.0/robot/groupMessages/send"
_DINGTALK_STREAM_TOPIC = "/v1.0/im/bot/messages/get"
_DINGTALK_HTTP_TIMEOUT_SECONDS = 10.0
_DINGTALK_SEND_TIMEOUT_SECONDS = 15.0
_DINGTALK_STREAM_RECV_TIMEOUT_SECONDS = 5.0
_DINGTALK_POLL_BATCH_SIZE = 20
_DINGTALK_POLLER_IDLE_SLEEP_SECONDS = 1.0
_DINGTALK_POLLER_MAX_BACKOFF_SECONDS = 15.0
_DINGTALK_EVENT_DEDUPE_TTL_SECONDS = 300.0
_DINGTALK_EVENT_DEDUPE_MAX_ENTRIES = 2048
_DINGTALK_TOKEN_REFRESH_BUFFER_SECONDS = 300

_STREAM_POLLERS: dict[str, "_DingTalkStreamPoller"] = {}
_STREAM_POLLERS_LOCK = threading.Lock()
_TOKEN_CACHE: dict[str, "_TokenCacheEntry"] = {}
_TOKEN_CACHE_LOCK = threading.Lock()


@dataclass(slots=True)
class _TokenCacheEntry:
    access_token: str
    expires_at: float


@dataclass(slots=True)
class _StreamConnectionTicket:
    endpoint: str
    ticket: str


class _StreamDisconnected(RuntimeError):
    """钉钉主动要求断开连接时，用一个明确异常把重连路径拉直。"""


class _DingTalkStreamPoller:
    """插件内自持的钉钉 Stream 长连接。

    主项目核心只认识 `poll`，所以这里把真实的长连接完全封在插件内部：
    - 后台线程负责持续连钉钉 Stream
    - 收到消息后先落到内存队列
    - `poll` 动作只负责把队列里的消息吐给主项目
    """

    def __init__(self, *, account_key: str, app_key: str, app_secret: str) -> None:
        self.account_key = account_key
        self.app_key = app_key
        self.app_secret = app_secret
        self.config_signature = f"{app_key}:{app_secret}"
        self._stop_event = threading.Event()
        self._queue_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._pending_events: deque[dict[str, Any]] = deque()
        self._recent_event_ids: dict[str, float] = {}
        self._thread = threading.Thread(
            target=self._run,
            name=f"dingtalk-stream-{account_key}",
            daemon=True,
        )
        self._started = False
        self._state: dict[str, Any] = {
            "state": "idle",
            "last_error": None,
            "last_connected_at": None,
            "last_message_at": None,
        }
        self._empty_poll_count = 0

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        logger.info("启动钉钉 Stream 轮询器 account=%s", self.account_key)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def drain_events(self, *, limit: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with self._queue_lock:
            while self._pending_events and len(events) < limit:
                events.append(self._pending_events.popleft())
        if events:
            self._empty_poll_count = 0
            logger.info(
                "钉钉 Stream 出队消息 account=%s count=%s",
                self.account_key,
                len(events),
            )
        else:
            self._empty_poll_count += 1
            if self._empty_poll_count % 20 == 0:
                logger.info(
                    "钉钉 Stream 暂无新消息 account=%s consecutive_empty_polls=%s",
                    self.account_key,
                    self._empty_poll_count,
                )
        return events

    def _run(self) -> None:
        backoff_seconds = 1.0
        while not self._stop_event.is_set():
            try:
                ticket = _open_stream_connection_ticket(
                    app_key=self.app_key,
                    app_secret=self.app_secret,
                )
                websocket_url = _build_stream_websocket_url(ticket)
                logger.info("钉钉 Stream 已拿到连接票据 account=%s endpoint=%s", self.account_key, ticket.endpoint)
                self._set_state(
                    state="connecting",
                    last_error=None,
                )
                with websocket_connect(
                    websocket_url,
                    open_timeout=_DINGTALK_HTTP_TIMEOUT_SECONDS,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=32,
                ) as websocket:
                    self._set_state(
                        state="connected",
                        last_connected_at=time.time(),
                        last_error=None,
                    )
                    logger.info("钉钉 Stream 已连接 account=%s", self.account_key)
                    backoff_seconds = 1.0
                    self._consume_socket(websocket)
            except _StreamDisconnected as exc:
                if self._stop_event.is_set():
                    break
                logger.info("钉钉 Stream 主动断开 account=%s detail=%s", self.account_key, exc)
            except Exception as exc:  # noqa: BLE001
                if self._stop_event.is_set():
                    break
                logger.warning("钉钉 Stream 连接异常 account=%s detail=%s", self.account_key, exc)
                self._set_state(state="reconnecting", last_error=str(exc))
                if self._sleep_with_stop(backoff_seconds):
                    backoff_seconds = min(backoff_seconds * 2, _DINGTALK_POLLER_MAX_BACKOFF_SECONDS)
                    continue
                break
            if self._sleep_with_stop(_DINGTALK_POLLER_IDLE_SLEEP_SECONDS):
                continue
            break
        self._set_state(state="stopped")

    def _consume_socket(self, websocket: ClientConnection) -> None:
        while not self._stop_event.is_set():
            try:
                message = websocket.recv(timeout=_DINGTALK_STREAM_RECV_TIMEOUT_SECONDS)
            except TimeoutError:
                continue
            if not isinstance(message, str) or not message.strip():
                continue
            self._handle_socket_message(websocket, message)

    def _handle_socket_message(self, websocket: ClientConnection, raw_message: str) -> None:
        frame = _load_json_object(raw_message, error_message="dingtalk stream frame is not valid JSON")
        headers = frame.get("headers")
        message_id = _first_text(headers, "messageId")
        topic = _first_text(headers, "topic")
        frame_type = (_first_text(frame, "type") or "").upper()

        if frame_type == "SYSTEM":
            self._handle_system_frame(websocket, message_id=message_id, topic=topic, frame=frame)
            return
        if frame_type == "CALLBACK":
            self._handle_callback_frame(websocket, message_id=message_id, topic=topic, frame=frame)
            return

        if message_id:
            _send_stream_ack(websocket, message_id=message_id)

    def _handle_system_frame(
        self,
        websocket: ClientConnection,
        *,
        message_id: str | None,
        topic: str | None,
        frame: dict[str, Any],
    ) -> None:
        if topic == "ping":
            opaque = None
            data = frame.get("data")
            if isinstance(data, str) and data.strip():
                parsed = _safe_parse_json(data)
                opaque = _first_text(parsed, "opaque")
            if message_id:
                _send_stream_ack(
                    websocket,
                    message_id=message_id,
                    data={"opaque": opaque} if opaque else {},
                )
            return
        if topic == "disconnect":
            raise _StreamDisconnected("remote requested disconnect")

        if message_id:
            _send_stream_ack(websocket, message_id=message_id)

    def _handle_callback_frame(
        self,
        websocket: ClientConnection,
        *,
        message_id: str | None,
        topic: str | None,
        frame: dict[str, Any],
    ) -> None:
        if message_id:
            _send_stream_ack(websocket, message_id=message_id, data={"response": None})
        if topic != _DINGTALK_STREAM_TOPIC:
            return

        data = frame.get("data")
        payload = _load_json_object_from_value(data)
        if payload is None:
            return
        event = _build_event_from_stream_message(payload, stream_message_id=message_id)
        if event is None:
            return
        event_id = _first_text(event, "external_event_id")
        if event_id and not self._remember_event_id(event_id):
            return
        with self._queue_lock:
            self._pending_events.append(event)
            queue_size = len(self._pending_events)
        logger.info(
            "钉钉 Stream 收到消息 account=%s event_id=%s conversation=%s queue_size=%s",
            self.account_key,
            event_id,
            _first_text(event, "external_conversation_key"),
            queue_size,
        )
        self._set_state(last_message_at=time.time())

    def _remember_event_id(self, event_id: str) -> bool:
        now = time.time()
        with self._queue_lock:
            expired = [
                key
                for key, seen_at in self._recent_event_ids.items()
                if now - seen_at > _DINGTALK_EVENT_DEDUPE_TTL_SECONDS
            ]
            for key in expired:
                self._recent_event_ids.pop(key, None)
            if event_id in self._recent_event_ids:
                return False
            self._recent_event_ids[event_id] = now
            while len(self._recent_event_ids) > _DINGTALK_EVENT_DEDUPE_MAX_ENTRIES:
                oldest_key = next(iter(self._recent_event_ids))
                self._recent_event_ids.pop(oldest_key, None)
        return True

    def _set_state(self, **changes: Any) -> None:
        with self._state_lock:
            self._state.update(changes)

    def _sleep_with_stop(self, seconds: float) -> bool:
        deadline = time.time() + max(seconds, 0.0)
        while time.time() < deadline:
            if self._stop_event.wait(timeout=0.2):
                return False
        return not self._stop_event.is_set()


def handle(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload or {}
    action = str(data.get("action") or "").strip()
    if action == "poll":
        return _handle_poll(data)
    if action == "webhook":
        return _handle_webhook(data)
    if action == "send":
        return _handle_send(data)
    if action == "probe":
        return _handle_probe(data)
    raise ValueError("dingtalk channel action is not supported")


def _handle_poll(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("dingtalk channel account payload is missing")
    config = _load_account_config(account.get("config"))
    app_key = _first_text(config, "app_key", "appKey", "client_id", "clientId")
    app_secret = _first_text(config, "app_secret", "appSecret", "client_secret", "clientSecret")
    if not app_key or not app_secret:
        raise ValueError("dingtalk polling mode requires app_key and app_secret")

    poller = _ensure_stream_poller(account=account, app_key=app_key, app_secret=app_secret)
    events = poller.drain_events(limit=_DINGTALK_POLL_BATCH_SIZE)
    next_cursor = None
    if events:
        next_cursor = _first_text(events[-1], "external_event_id")
    return {
        "message": "dingtalk polling completed",
        "events": events,
        "next_cursor": next_cursor,
    }


def _handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    # 保留旧 webhook 兼容层，避免已经存在的账号立即失效。
    request = payload.get("request")
    body = _load_request_json(request)
    event = _extract_legacy_webhook_event(body)
    if event is None:
        return {"message": "dingtalk event ignored"}

    text = _extract_text(event)
    if not text:
        return {"message": "dingtalk text message is missing"}

    external_user_id = _first_text(
        event,
        "senderStaffId",
        "senderUserId",
        "senderUserid",
        "staffId",
        "senderId",
    )
    conversation_id = _first_text(
        event,
        "conversationId",
        "conversation_id",
        "openConversationId",
    )
    message_id = _first_text(event, "msgId", "messageId")
    if not external_user_id or not conversation_id or not message_id:
        return {"message": "dingtalk event ids are incomplete"}

    chat_type = "direct" if _is_direct_chat(event) else "group"
    sender_display_name = _first_text(event, "senderNick", "nickName", "sender_name")
    session_webhook = _first_text(event, "sessionWebhook", "session_webhook")

    return {
        "message": "dingtalk webhook accepted",
        "event": {
            "external_event_id": message_id,
            "event_type": "message",
            "external_user_id": external_user_id,
            "external_conversation_key": f"conversation:{conversation_id}",
            "normalized_payload": {
                "text": text,
                "chat_type": chat_type,
                "sender_display_name": sender_display_name,
                "metadata": {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "session_webhook": session_webhook,
                    "chat_type": chat_type,
                    "sender_staff_id": _first_text(event, "senderStaffId"),
                    "sender_user_id": _first_text(event, "senderUserId", "senderUserid", "senderId"),
                },
            },
            "status": "received",
        },
    }


def _handle_send(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    delivery = payload.get("delivery")
    if not isinstance(delivery, dict):
        raise ValueError("dingtalk delivery payload is missing")

    config = _load_account_config(None if not isinstance(account, dict) else account.get("config"))
    app_key = _first_text(config, "app_key", "appKey", "client_id", "clientId")
    app_secret = _first_text(config, "app_secret", "appSecret", "client_secret", "clientSecret")
    metadata = delivery.get("metadata")
    text = _first_text(delivery, "text")
    if not text:
        raise ValueError("dingtalk delivery text is missing")

    target = _resolve_delivery_target(
        external_conversation_key=_first_text(delivery, "external_conversation_key"),
        metadata=metadata,
    )
    if target is None:
        raise ValueError("dingtalk delivery target is missing")

    if target["transport"] == "session_webhook":
        response = httpx.post(
            target["target"],
            json={
                "msgtype": "text",
                "text": {"content": text},
            },
            timeout=_DINGTALK_SEND_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload_json = response.json()
        provider_message_ref = _first_text(payload_json, "processQueryKey", "messageId")
        return {
            "provider_message_ref": provider_message_ref,
        }

    if not app_key or not app_secret:
        raise ValueError("dingtalk OpenAPI delivery requires app_key and app_secret")

    access_token = _get_access_token(app_key=app_key, app_secret=app_secret)
    provider_message_ref = _send_openapi_message(
        app_key=app_key,
        access_token=access_token,
        target=target,
        text=text,
    )
    return {
        "provider_message_ref": provider_message_ref,
    }


def _handle_probe(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account")
    if not isinstance(account, dict):
        raise ValueError("dingtalk channel account payload is missing")
    config = _load_account_config(account.get("config"))
    app_key = _first_text(config, "app_key", "appKey", "client_id", "clientId")
    app_secret = _first_text(config, "app_secret", "appSecret", "client_secret", "clientSecret")
    connection_mode = _first_text(account, "connection_mode")

    if connection_mode == "polling":
        if not app_key or not app_secret:
            raise ValueError("dingtalk polling mode requires app_key and app_secret")
        _open_stream_connection_ticket(app_key=app_key, app_secret=app_secret)
        return {
            "probe_status": "ok",
            "message": "dingtalk stream credentials validated",
        }

    if app_key and app_secret:
        _open_stream_connection_ticket(app_key=app_key, app_secret=app_secret)
        return {
            "probe_status": "ok",
            "message": "dingtalk stream credentials validated",
        }
    if app_key:
        return {
            "probe_status": "ok",
            "message": "dingtalk legacy webhook mode does not require active probe",
        }
    raise ValueError("dingtalk app_key is missing")


def _ensure_stream_poller(*, account: dict[str, Any], app_key: str, app_secret: str) -> _DingTalkStreamPoller:
    account_key = _resolve_account_runtime_key(account)
    with _STREAM_POLLERS_LOCK:
        poller = _STREAM_POLLERS.get(account_key)
        signature = f"{app_key}:{app_secret}"
        if poller is not None and poller.config_signature != signature:
            poller.stop()
            _STREAM_POLLERS.pop(account_key, None)
            poller = None
        if poller is None:
            poller = _DingTalkStreamPoller(
                account_key=account_key,
                app_key=app_key,
                app_secret=app_secret,
            )
            _STREAM_POLLERS[account_key] = poller
            poller.start()
        return poller


def _resolve_account_runtime_key(account: dict[str, Any]) -> str:
    for key in ("id", "account_code"):
        value = _first_text(account, key)
        if value:
            return value
    household_id = _first_text(account, "household_id") or "global"
    platform_code = _first_text(account, "platform_code") or "dingtalk"
    return f"{household_id}:{platform_code}"


def _open_stream_connection_ticket(*, app_key: str, app_secret: str) -> _StreamConnectionTicket:
    response = httpx.post(
        _DINGTALK_STREAM_OPEN_URL,
        json={
            "clientId": app_key,
            "clientSecret": app_secret,
            "subscriptions": [
                {
                    "type": "CALLBACK",
                    "topic": _DINGTALK_STREAM_TOPIC,
                }
            ],
            "ua": "familyclaw-channel-dingtalk",
        },
        timeout=_DINGTALK_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    endpoint = _first_text(payload, "endpoint")
    ticket = _first_text(payload, "ticket")
    if not endpoint or not ticket:
        raise ValueError("dingtalk stream open connection response is incomplete")
    return _StreamConnectionTicket(endpoint=endpoint, ticket=ticket)


def _build_stream_websocket_url(ticket: _StreamConnectionTicket) -> str:
    query = urlencode({"ticket": ticket.ticket})
    separator = "&" if "?" in ticket.endpoint else "?"
    return f"{ticket.endpoint}{separator}{query}"


def _send_stream_ack(
    websocket: ClientConnection,
    *,
    message_id: str,
    data: dict[str, Any] | None = None,
) -> None:
    ack_payload = {
        "code": 200,
        "headers": {
            "messageId": message_id,
            "contentType": "application/json",
        },
        "message": "OK",
        "data": json.dumps(data or {"response": None}, ensure_ascii=False),
    }
    websocket.send(json.dumps(ack_payload, ensure_ascii=False))


def _get_access_token(*, app_key: str, app_secret: str) -> str:
    now = time.time()
    with _TOKEN_CACHE_LOCK:
        cached = _TOKEN_CACHE.get(app_key)
        if cached and cached.expires_at - _DINGTALK_TOKEN_REFRESH_BUFFER_SECONDS > now:
            return cached.access_token

    response = httpx.post(
        _DINGTALK_OAUTH_URL,
        json={
            "appKey": app_key,
            "appSecret": app_secret,
        },
        timeout=_DINGTALK_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = _first_text(payload, "accessToken")
    expire_in = _coerce_int(payload.get("expireIn")) or 7200
    if not access_token:
        raise ValueError("dingtalk access token response is incomplete")

    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE[app_key] = _TokenCacheEntry(
            access_token=access_token,
            expires_at=now + expire_in,
        )
    return access_token


def _send_openapi_message(
    *,
    app_key: str,
    access_token: str,
    target: dict[str, str],
    text: str,
) -> str | None:
    if target["chat_type"] == "direct":
        url = _DINGTALK_DIRECT_SEND_URL
        body = {
            "robotCode": app_key,
            "userIds": [target["target"]],
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps(
                {
                    "title": _resolve_markdown_title(text),
                    "text": text,
                },
                ensure_ascii=False,
            ),
        }
    else:
        url = _DINGTALK_GROUP_SEND_URL
        body = {
            "robotCode": app_key,
            "openConversationId": target["target"],
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps(
                {
                    "title": _resolve_markdown_title(text),
                    "text": text,
                },
                ensure_ascii=False,
            ),
        }

    response = httpx.post(
        url,
        headers={
            "x-acs-dingtalk-access-token": access_token,
            "Content-Type": "application/json",
        },
        json=body,
        timeout=_DINGTALK_SEND_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    _raise_if_delivery_failed(target=target, payload=payload)
    return _first_text(payload, "processQueryKey", "messageId")


def _raise_if_delivery_failed(*, target: dict[str, str], payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    invalid_user_ids = payload.get("invalidStaffIdList")
    if isinstance(invalid_user_ids, list) and invalid_user_ids:
        raise ValueError(
            "dingtalk direct delivery contains invalid user ids: "
            + ", ".join(str(item) for item in invalid_user_ids)
        )
    if target["chat_type"] == "direct":
        flow_controlled = payload.get("flowControlledStaffIdList")
        if isinstance(flow_controlled, list) and flow_controlled:
            raise ValueError(
                "dingtalk direct delivery was flow controlled for user ids: "
                + ", ".join(str(item) for item in flow_controlled)
            )


def _resolve_markdown_title(text: str) -> str:
    first_line = (text or "").splitlines()[0].strip() if text else ""
    if not first_line:
        return "FamilyClaw"
    return first_line.lstrip("#*- >")[:20] or "FamilyClaw"


def _resolve_delivery_target(
    *,
    external_conversation_key: str | None,
    metadata: Any,
) -> dict[str, str] | None:
    if external_conversation_key:
        if external_conversation_key.startswith("direct:"):
            target = external_conversation_key.removeprefix("direct:").strip()
            if target:
                return {
                    "transport": "openapi",
                    "chat_type": "direct",
                    "target": target,
                }
        if external_conversation_key.startswith("group:"):
            target = external_conversation_key.removeprefix("group:").strip()
            if target:
                return {
                    "transport": "openapi",
                    "chat_type": "group",
                    "target": target,
                }
        if external_conversation_key.startswith("conversation:"):
            legacy_target = _resolve_legacy_delivery_target(metadata)
            if legacy_target is not None:
                return legacy_target

    return _resolve_legacy_delivery_target(metadata)


def _resolve_legacy_delivery_target(metadata: Any) -> dict[str, str] | None:
    if not isinstance(metadata, dict):
        return None
    session_webhook = _first_text(metadata, "session_webhook", "sessionWebhook")
    if session_webhook:
        return {
            "transport": "session_webhook",
            "chat_type": _first_text(metadata, "chat_type") or "group",
            "target": session_webhook,
        }

    chat_type = _first_text(metadata, "chat_type")
    if chat_type == "direct":
        direct_target = _first_text(
            metadata,
            "sender_staff_id",
            "sender_user_id",
            "external_user_id",
            "sender_id",
        )
        if direct_target:
            return {
                "transport": "openapi",
                "chat_type": "direct",
                "target": direct_target,
            }
    conversation_id = _first_text(metadata, "conversation_id", "open_conversation_id")
    if conversation_id:
        return {
            "transport": "openapi",
            "chat_type": "group",
            "target": conversation_id,
        }
    return None


def _build_event_from_stream_message(
    message: dict[str, Any],
    *,
    stream_message_id: str | None,
) -> dict[str, Any] | None:
    text = _extract_text(message)
    if not text:
        return None

    external_user_id = _first_text(
        message,
        "senderStaffId",
        "senderUserId",
        "senderUserid",
        "senderId",
    )
    conversation_id = _first_text(message, "conversationId", "openConversationId")
    if not external_user_id or not conversation_id:
        return None

    chat_type = "direct" if _is_direct_chat(message) else "group"
    if chat_type == "direct":
        external_conversation_key = f"direct:{external_user_id}"
    else:
        external_conversation_key = f"group:{conversation_id}"

    event_id = stream_message_id or _first_text(message, "msgId", "messageId")
    if not event_id:
        event_id = f"{conversation_id}:{external_user_id}:{int(time.time() * 1000)}"

    return {
        "external_event_id": event_id,
        "event_type": "message",
        "external_user_id": external_user_id,
        "external_conversation_key": external_conversation_key,
        "normalized_payload": {
            "text": text,
            "chat_type": chat_type,
            "sender_display_name": _first_text(message, "senderNick", "nickName"),
            "metadata": {
                "conversation_id": conversation_id,
                "message_id": _first_text(message, "msgId", "messageId"),
                "stream_message_id": stream_message_id,
                "chat_type": chat_type,
                "sender_staff_id": _first_text(message, "senderStaffId"),
                "sender_user_id": _first_text(message, "senderUserId", "senderUserid", "senderId"),
                "robot_code": _first_text(message, "robotCode"),
            },
        },
        "status": "received",
    }


def _extract_legacy_webhook_event(body: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(body.get("data"), str) and body["data"].strip():
        decoded = _safe_parse_json(body["data"])
        if isinstance(decoded, dict):
            return decoded
    if isinstance(body.get("data"), dict):
        return body["data"]
    if isinstance(body.get("event"), dict):
        return body["event"]
    if any(key in body for key in ("conversationId", "msgId", "text")):
        return body
    return None


def _extract_text(event: dict[str, Any]) -> str | None:
    text_payload = event.get("text")
    if isinstance(text_payload, dict):
        text = _first_text(text_payload, "content")
        if text:
            return text

    content = event.get("content")
    if isinstance(content, dict):
        text = _first_text(content, "text", "content", "recognition")
        if text:
            return text

    if isinstance(content, str):
        parsed = _safe_parse_json(content)
        if isinstance(parsed, dict):
            text = _first_text(parsed, "text", "content", "recognition")
            if text:
                return text
        normalized = content.strip()
        if normalized:
            return normalized

    return _first_text(event, "message")


def _is_direct_chat(event: dict[str, Any]) -> bool:
    conversation_type = _first_text(event, "conversationType", "conversation_type")
    if conversation_type in {"1", "single", "private", "direct"}:
        return True
    if conversation_type in {"2", "group", "channel"}:
        return False
    return False


def _load_account_config(raw_config: Any) -> dict[str, Any]:
    if isinstance(raw_config, dict):
        return raw_config
    if isinstance(raw_config, str) and raw_config.strip():
        parsed = _safe_parse_json(raw_config)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("dingtalk account config is not valid JSON")
    return {}


def _load_request_json(raw_request: Any) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("dingtalk webhook request is missing")
    body_text = raw_request.get("body_text")
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("dingtalk webhook body is missing")
    payload = _load_json_object(body_text, error_message="dingtalk webhook body is not valid JSON")
    return payload


def _load_json_object(raw_text: str, *, error_message: str) -> dict[str, Any]:
    parsed = _safe_parse_json(raw_text)
    if not isinstance(parsed, dict):
        raise ValueError(error_message)
    return parsed


def _load_json_object_from_value(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = _safe_parse_json(value)
        if isinstance(parsed, dict):
            return parsed
    return None


def _safe_parse_json(raw_text: str) -> Any:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


def _first_text(mapping: Any, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
