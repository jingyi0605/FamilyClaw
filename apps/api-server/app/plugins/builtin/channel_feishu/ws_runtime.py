from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import json
import logging
import random
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import websockets

from .common import decode_callback_payload, first_int, first_text, load_account_config, resolve_open_base_url
from .event_parser import extract_challenge, normalize_feishu_message_event, validate_verification_token
from .ws_protocol import (
    FRAME_TYPE_CONTROL,
    FRAME_TYPE_DATA,
    HEADER_MESSAGE_ID,
    HEADER_SEQ,
    HEADER_SUM,
    HEADER_TYPE,
    MESSAGE_TYPE_EVENT,
    MESSAGE_TYPE_PING,
    MESSAGE_TYPE_PONG,
    FeishuWsClientConfig,
    FeishuWsFrame,
    build_ack_frame,
    build_ping_frame,
    decode_frame,
    encode_frame,
    get_header_value,
    parse_client_config,
)


logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 200
DEFAULT_BATCH_SIZE = 50
DEFAULT_IDLE_TIMEOUT_SECONDS = 600
RECEIVE_WAIT_TIMEOUT_SECONDS = 1.0
CHUNK_EXPIRE_SECONDS = 5.0
WS_CONNECT_TIMEOUT_SECONDS = 15.0
WS_MAX_MESSAGE_BYTES = 4 * 1024 * 1024


@dataclass(slots=True, frozen=True)
class FeishuWsAccountSpec:
    account_id: str
    household_id: str
    app_id: str
    app_secret: str
    open_base_url: str
    encrypt_key: str | None
    verification_token: str | None
    queue_size: int
    batch_size: int
    idle_timeout_seconds: int


@dataclass(slots=True)
class _ChunkBuffer:
    total: int
    parts: list[bytes]
    expires_at: float


class FeishuWsAccountRuntime:
    """账号级长连接运行时。

    核心只会周期性调用 poll；真正的长连接、重连、收包和排队都留在插件内部。
    """

    def __init__(self, spec: FeishuWsAccountSpec) -> None:
        self._spec = spec
        self._state_lock = threading.Lock()
        self._queue: deque[dict[str, Any]] = deque()
        self._chunks: dict[str, _ChunkBuffer] = {}
        self._client_config = FeishuWsClientConfig()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = False
        self._last_error: str | None = None
        self._last_status = "starting"
        self._last_poll_monotonic = time.monotonic()
        self._last_event_id: str | None = None
        self._dropped_event_count = 0
        self._service_id = 0

    @property
    def spec(self) -> FeishuWsAccountSpec:
        return self._spec

    def ensure_started(self) -> None:
        self.touch()
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name=f"feishu-ws-{self._spec.account_id[:8]}",
                daemon=True,
            )
            self._thread.start()
        logger.info(
            "feishu-debug ws_runtime_started account_id=%s household_id=%s queue_size=%s batch_size=%s idle_timeout_seconds=%s",
            self._spec.account_id,
            self._spec.household_id,
            self._spec.queue_size,
            self._spec.batch_size,
            self._spec.idle_timeout_seconds,
        )

    def stop(self, reason: str) -> None:
        self._stop_event.set()
        with self._state_lock:
            self._connected = False
            self._last_status = reason
        logger.info(
            "feishu-debug ws_runtime_stopped account_id=%s household_id=%s reason=%s",
            self._spec.account_id,
            self._spec.household_id,
            reason,
        )

    def touch(self) -> None:
        with self._state_lock:
            self._last_poll_monotonic = time.monotonic()

    def drain_poll_batch(self) -> dict[str, Any]:
        self.touch()
        events: list[dict[str, Any]] = []
        next_cursor: str | None = None
        drained_count = 0
        with self._state_lock:
            while self._queue and len(events) < self._spec.batch_size:
                event = self._queue.popleft()
                events.append(event)
                drained_count += 1
                external_event_id = event.get("external_event_id")
                if isinstance(external_event_id, str) and external_event_id.strip():
                    next_cursor = external_event_id.strip()
            message = self._build_status_message_locked()
            queued_after_drain = len(self._queue)

        if drained_count > 0:
            logger.info(
                "feishu-debug ws_poll_drain account_id=%s drained_count=%s queued_after_drain=%s next_cursor=%s",
                self._spec.account_id,
                drained_count,
                queued_after_drain,
                next_cursor,
            )

        return {
            "events": events,
            "next_cursor": next_cursor,
            "message": message,
        }

    def is_dead(self) -> bool:
        with self._state_lock:
            return self._thread is not None and not self._thread.is_alive() and not self._queue

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run_forever())
        except Exception:
            logger.exception("feishu websocket runtime crashed account_id=%s", self._spec.account_id)
            with self._state_lock:
                self._connected = False
                self._last_error = "runtime crashed"
                self._last_status = "crashed"

    async def _run_forever(self) -> None:
        reconnect_attempt = 0
        while not self._should_stop():
            if self._is_idle_expired():
                self.stop("idle timeout")
                return
            try:
                endpoint_url, client_config = await self._fetch_ws_endpoint()
                self._apply_client_config(client_config)
                await self._connect_and_consume(endpoint_url)
                reconnect_attempt = 0
            except Exception as exc:
                reconnect_attempt += 1
                self._record_connection_error(exc)
                if self._should_stop():
                    break
                await self._sleep_with_stop(self._build_reconnect_delay(reconnect_attempt))

        self.stop("stopped")

    async def _fetch_ws_endpoint(self) -> tuple[str, FeishuWsClientConfig]:
        logger.info(
            "feishu-debug ws_endpoint_fetch_start account_id=%s household_id=%s base_url=%s",
            self._spec.account_id,
            self._spec.household_id,
            self._spec.open_base_url,
        )
        async with httpx.AsyncClient(timeout=WS_CONNECT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self._spec.open_base_url}/callback/ws/endpoint",
                headers={"locale": "zh"},
                json={
                    "AppID": self._spec.app_id,
                    "AppSecret": self._spec.app_secret,
                },
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("feishu websocket endpoint response must be a JSON object")
        code = payload.get("code")
        if code != 0:
            message = first_text(payload, "msg") or f"feishu websocket endpoint rejected: {code}"
            raise ValueError(message)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("feishu websocket endpoint data is missing")
        endpoint_url = first_text(data, "URL", "url")
        if not endpoint_url:
            raise ValueError("feishu websocket endpoint URL is missing")
        logger.info(
            "feishu-debug ws_endpoint_fetch_success account_id=%s household_id=%s has_client_config=%s",
            self._spec.account_id,
            self._spec.household_id,
            isinstance(data.get("ClientConfig"), dict),
        )
        return endpoint_url, _parse_client_config_dict(data.get("ClientConfig"))

    async def _connect_and_consume(self, endpoint_url: str) -> None:
        self._set_service_id_from_url(endpoint_url)
        async with websockets.connect(
            endpoint_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=5,
            max_size=WS_MAX_MESSAGE_BYTES,
        ) as websocket:
            with self._state_lock:
                self._connected = True
                self._last_error = None
                self._last_status = "connected"
            logger.info(
                "feishu-debug ws_connected account_id=%s household_id=%s service_id=%s",
                self._spec.account_id,
                self._spec.household_id,
                self._extract_service_id(),
            )

            ping_task = asyncio.create_task(self._ping_loop(websocket))
            try:
                while not self._should_stop():
                    if self._is_idle_expired():
                        self.stop("idle timeout")
                        return
                    try:
                        raw_message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=RECEIVE_WAIT_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(raw_message, str):
                        raw_bytes = raw_message.encode("utf-8")
                    else:
                        raw_bytes = raw_message
                    await self._handle_ws_message(websocket, raw_bytes)
            finally:
                ping_task.cancel()
                await asyncio.gather(ping_task, return_exceptions=True)
                with self._state_lock:
                    self._connected = False
                    if not self._stop_event.is_set():
                        self._last_status = "reconnecting"
                logger.info(
                    "feishu-debug ws_disconnected account_id=%s household_id=%s stop_requested=%s",
                    self._spec.account_id,
                    self._spec.household_id,
                    self._stop_event.is_set(),
                )

    async def _ping_loop(self, websocket) -> None:
        while not self._should_stop():
            await self._sleep_with_stop(max(self._client_config.ping_interval, 1))
            if self._should_stop():
                return
            ping_frame = build_ping_frame(self._extract_service_id())
            await websocket.send(encode_frame(ping_frame))

    async def _handle_ws_message(self, websocket, raw_message: bytes) -> None:
        frame = decode_frame(raw_message)
        if frame.method == FRAME_TYPE_CONTROL:
            self._handle_control_frame(frame)
            return
        if frame.method == FRAME_TYPE_DATA:
            await self._handle_data_frame(websocket, frame)

    def _handle_control_frame(self, frame: FeishuWsFrame) -> None:
        message_type = get_header_value(frame.headers, HEADER_TYPE)
        if message_type == MESSAGE_TYPE_PONG:
            client_config = parse_client_config(frame.payload)
            if client_config is not None:
                self._apply_client_config(client_config)
        elif message_type == MESSAGE_TYPE_PING:
            logger.debug("feishu websocket received ping account_id=%s", self._spec.account_id)

    async def _handle_data_frame(self, websocket, frame: FeishuWsFrame) -> None:
        message_type = get_header_value(frame.headers, HEADER_TYPE)
        if message_type != MESSAGE_TYPE_EVENT:
            return

        payload = frame.payload
        message_id = get_header_value(frame.headers, HEADER_MESSAGE_ID)
        chunk_total = _parse_positive_int(get_header_value(frame.headers, HEADER_SUM), default=1)
        chunk_index = _parse_positive_int(get_header_value(frame.headers, HEADER_SEQ), default=0)
        if chunk_total > 1 and message_id:
            payload = self._combine_payload(message_id, chunk_total, chunk_index, payload)
            if payload is None:
                return

        ack_code = 200
        start_time = time.perf_counter()
        try:
            body = decode_callback_payload(payload, encrypt_key=self._spec.encrypt_key)
            validate_verification_token(body, self._spec.verification_token)
            challenge = extract_challenge(body)
            if challenge is not None:
                logger.info(
                    "feishu-debug ws_event_challenge_ignored account_id=%s household_id=%s",
                    self._spec.account_id,
                    self._spec.household_id,
                )
            else:
                normalized_event = normalize_feishu_message_event(body)
                if normalized_event is not None:
                    self._append_event(normalized_event)
                    logger.info(
                        "feishu-debug ws_event_queued account_id=%s household_id=%s external_event_id=%s external_user_id=%s",
                        self._spec.account_id,
                        self._spec.household_id,
                        first_text(normalized_event, "external_event_id"),
                        first_text(normalized_event, "external_user_id"),
                    )
                else:
                    logger.info(
                        "feishu-debug ws_event_ignored account_id=%s household_id=%s reason=normalize_returned_none",
                        self._spec.account_id,
                        self._spec.household_id,
                    )
        except Exception:
            ack_code = 500
            logger.exception("feishu websocket message handling failed account_id=%s", self._spec.account_id)
        finally:
            biz_rt_ms = int((time.perf_counter() - start_time) * 1000)
            ack_frame = build_ack_frame(frame, code=ack_code, biz_rt_ms=biz_rt_ms)
            await websocket.send(encode_frame(ack_frame))
            logger.info(
                "feishu-debug ws_event_acked account_id=%s household_id=%s ack_code=%s biz_rt_ms=%s",
                self._spec.account_id,
                self._spec.household_id,
                ack_code,
                biz_rt_ms,
            )

    def _combine_payload(self, message_id: str, total: int, seq: int, chunk: bytes) -> bytes | None:
        now = time.monotonic()
        with self._state_lock:
            expired_keys = [key for key, buffer in self._chunks.items() if buffer.expires_at <= now]
            for key in expired_keys:
                self._chunks.pop(key, None)

            buffer = self._chunks.get(message_id)
            if buffer is None or buffer.total != total:
                buffer = _ChunkBuffer(total=total, parts=[b""] * total, expires_at=now + CHUNK_EXPIRE_SECONDS)
                self._chunks[message_id] = buffer
            if 0 <= seq < total:
                buffer.parts[seq] = chunk
                buffer.expires_at = now + CHUNK_EXPIRE_SECONDS
            if any(not item for item in buffer.parts):
                return None
            self._chunks.pop(message_id, None)
            return b"".join(buffer.parts)

    def _append_event(self, event: dict[str, Any]) -> None:
        with self._state_lock:
            if len(self._queue) >= self._spec.queue_size:
                self._queue.popleft()
                self._dropped_event_count += 1
                logger.warning(
                    "feishu-debug ws_queue_drop_oldest account_id=%s household_id=%s queue_size=%s dropped_total=%s",
                    self._spec.account_id,
                    self._spec.household_id,
                    self._spec.queue_size,
                    self._dropped_event_count,
                )
            self._queue.append(event)
            external_event_id = event.get("external_event_id")
            if isinstance(external_event_id, str) and external_event_id.strip():
                self._last_event_id = external_event_id.strip()

    def _apply_client_config(self, client_config: FeishuWsClientConfig) -> None:
        with self._state_lock:
            self._client_config = client_config

    def _record_connection_error(self, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "feishu websocket reconnect scheduled account_id=%s error=%s",
            self._spec.account_id,
            message,
        )
        with self._state_lock:
            self._connected = False
            self._last_error = message
            self._last_status = "reconnecting"

    def _set_service_id_from_url(self, endpoint_url: str) -> None:
        query = parse_qs(urlparse(endpoint_url).query)
        service_id_raw = None
        values = query.get("service_id")
        if values:
            service_id_raw = values[0]
        try:
            service_id = int(service_id_raw) if service_id_raw is not None else 0
        except ValueError:
            service_id = 0
        with self._state_lock:
            self._service_id = max(service_id, 0)

    def _extract_service_id(self) -> int:
        with self._state_lock:
            return self._service_id

    def _build_reconnect_delay(self, reconnect_attempt: int) -> float:
        base = float(max(self._client_config.reconnect_interval, 1))
        if reconnect_attempt == 1 and self._client_config.reconnect_nonce > 0:
            return base + random.random() * float(self._client_config.reconnect_nonce)
        return base

    async def _sleep_with_stop(self, seconds: float) -> None:
        deadline = time.monotonic() + max(seconds, 0.0)
        while not self._should_stop():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 0.5))

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def _is_idle_expired(self) -> bool:
        with self._state_lock:
            return (time.monotonic() - self._last_poll_monotonic) > self._spec.idle_timeout_seconds

    def _build_status_message_locked(self) -> str:
        queue_size = len(self._queue)
        if self._connected:
            if self._dropped_event_count > 0:
                return (
                    f"feishu websocket active, queued={queue_size}, "
                    f"dropped={self._dropped_event_count}"
                )
            return f"feishu websocket active, queued={queue_size}"
        if self._last_error:
            return f"feishu websocket reconnecting, queued={queue_size}, last_error={self._last_error}"
        return f"feishu websocket {self._last_status}, queued={queue_size}"


class FeishuWsRuntimeManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runtimes: dict[str, FeishuWsAccountRuntime] = {}

    def poll(self, account_payload: dict[str, Any]) -> dict[str, Any]:
        runtime = self._ensure_runtime(_build_account_spec(account_payload))
        return runtime.drain_poll_batch()

    def probe_long_connection(self, account_payload: dict[str, Any]) -> None:
        spec = _build_account_spec(account_payload)
        runtime = FeishuWsAccountRuntime(spec)
        asyncio.run(runtime._fetch_ws_endpoint())

    def _ensure_runtime(self, spec: FeishuWsAccountSpec) -> FeishuWsAccountRuntime:
        with self._lock:
            current = self._runtimes.get(spec.account_id)
            if current is not None and current.spec != spec:
                current.stop("config changed")
                current = None
                self._runtimes.pop(spec.account_id, None)

            if current is None:
                current = FeishuWsAccountRuntime(spec)
                self._runtimes[spec.account_id] = current

            # 顺手清掉已经死亡的旧 runtime，避免模块级状态越积越脏。
            stale_ids = [account_id for account_id, item in self._runtimes.items() if item is not current and item.is_dead()]
            for account_id in stale_ids:
                self._runtimes.pop(account_id, None)

            current.ensure_started()
            return current


def _build_account_spec(account_payload: dict[str, Any]) -> FeishuWsAccountSpec:
    account_id = first_text(account_payload, "id")
    household_id = first_text(account_payload, "household_id")
    if not account_id or not household_id:
        raise ValueError("feishu channel account identifiers are missing")

    config = load_account_config(account_payload.get("config"))
    app_id = first_text(config, "app_id", "appId")
    app_secret = first_text(config, "app_secret", "appSecret")
    if not app_id or not app_secret:
        raise ValueError("feishu app credentials are missing")

    return FeishuWsAccountSpec(
        account_id=account_id,
        household_id=household_id,
        app_id=app_id,
        app_secret=app_secret,
        open_base_url=resolve_open_base_url(config),
        encrypt_key=first_text(config, "encrypt_key", "encryptKey"),
        verification_token=first_text(config, "verification_token", "verificationToken"),
        queue_size=max(first_int(config, "long_connection_queue_size", default=DEFAULT_QUEUE_SIZE), 1),
        batch_size=max(first_int(config, "poll_batch_size", default=DEFAULT_BATCH_SIZE), 1),
        idle_timeout_seconds=max(
            first_int(config, "long_connection_idle_timeout_seconds", default=DEFAULT_IDLE_TIMEOUT_SECONDS),
            30,
        ),
    )


def _parse_client_config_dict(raw_config: Any) -> FeishuWsClientConfig:
    if not isinstance(raw_config, dict):
        return FeishuWsClientConfig()
    payload = json.dumps(raw_config, ensure_ascii=False).encode("utf-8")
    return parse_client_config(payload) or FeishuWsClientConfig()


def _parse_positive_int(raw_value: str | None, *, default: int) -> int:
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value >= 0 else default


manager = FeishuWsRuntimeManager()
