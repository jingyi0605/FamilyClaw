from __future__ import annotations

import asyncio
import base64
from collections import deque
import contextlib
import json
import logging
import math
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import websockets
from websockets.exceptions import ConnectionClosed

from open_xiaoai_gateway.protocol import GatewayCommand, GatewayEvent, OpenXiaoAIResponse
from open_xiaoai_gateway.settings import settings
from open_xiaoai_gateway.translator import (
    TerminalBinaryStream,
    TerminalBridgeContext,
    TerminalDiscoveryInfo,
    PendingVoiceprintEnrollment,
    TerminalRpcRequest,
    VoiceTerminalBinding,
    build_discovery_info,
    build_discovery_report_payload,
    build_playback_failed_event,
    build_playback_started_event,
    build_recording_rpc_payload,
    build_rpc_request_message,
    build_stream_message,
    build_terminal_offline_event,
    build_terminal_online_event,
    parse_open_xiaoai_stream,
    parse_open_xiaoai_text_message,
    translate_audio_chunk,
    translate_command_to_terminal,
    translate_text_message_result,
)

logger = logging.getLogger(__name__)

_TAKEOVER_KEEPALIVE_CHUNK_MS = 250
_TAKEOVER_KEEPALIVE_INTERVAL_SECONDS = 0.2
_TAKEOVER_ABORT_RECOVERY_SECONDS = 2.0
_TAKEOVER_ABORT_COMMAND = "/etc/init.d/mico_aivs_lab restart >/dev/null 2>&1"
_LOCAL_PLAYBACK_STOP_COMMAND = (
    "mphelper pause >/dev/null 2>&1; "
    "mphelper stop >/dev/null 2>&1; "
    "killall tts_play.sh >/dev/null 2>&1; "
    "killall aplay >/dev/null 2>&1; "
    "killall tinyplay >/dev/null 2>&1; "
    "killall madplay >/dev/null 2>&1; "
    "pkill -f '/usr/sbin/tts_play.sh' >/dev/null 2>&1; "
    "pkill -f '[t]ts_play.sh' >/dev/null 2>&1; "
    "pkill -f '[a]play' >/dev/null 2>&1; "
    "pkill -f '[t]inyplay' >/dev/null 2>&1; "
    "pkill -f '[m]adplay' >/dev/null 2>&1; "
    "for pid in $(pidof tts_play.sh 2>/dev/null) $(pidof aplay 2>/dev/null) $(pidof tinyplay 2>/dev/null) $(pidof madplay 2>/dev/null); do kill -9 \"$pid\" >/dev/null 2>&1; done; "
    "busybox killall tts_play.sh >/dev/null 2>&1; "
    "busybox killall aplay >/dev/null 2>&1; "
    "busybox killall tinyplay >/dev/null 2>&1; "
    "busybox killall madplay >/dev/null 2>&1; "
    "true"
)
_STOP_PHRASE_SUPPRESSION_SECONDS = 15.0
_LOCAL_PLAYBACK_STOP_PHRASES = frozenset(
    {
        "停止",
        "停下",
        "停一下",
        "不要再说了",
        "不要说了",
        "别说了",
        "别讲了",
        "闭嘴",
    }
)
_MAX_INTERRUPTED_PLAYBACK_SESSIONS = 32
_VOICEPRINT_PROMPT_SESSION_PREFIX = "voiceprint-prompt:"
_VOICEPRINT_PROMPT_DELAY_SECONDS = 3.0
_VOICEPRINT_PROMPT_BEEP_SETTLE_SECONDS = 0.35
_VOICEPRINT_CAPTURE_WINDOW_SECONDS = 7.0
_VOICEPRINT_PROMPT_BEEP_SAMPLE_RATE = 16000
_VOICEPRINT_PROMPT_BEEP_DURATION_SECONDS = 0.18
_VOICEPRINT_PROMPT_BEEP_FREQUENCY_HZ = 880.0
_VOICEPRINT_PROMPT_BEEP_VOLUME = 0.45
_NATIVE_FIRST_AUDIO_BUFFER_SECONDS = 6.0
_TERMINAL_MESSAGE_QUEUE_CLOSE = object()


class TerminalRpcClient:
    def __init__(self, websocket) -> None:
        self._websocket = websocket
        self._pending: dict[str, asyncio.Future[OpenXiaoAIResponse]] = {}

    async def call(self, *, command: str, payload: object | None = None, timeout_seconds: float = 5.0) -> OpenXiaoAIResponse:
        request_id = str(uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[OpenXiaoAIResponse] = loop.create_future()
        self._pending[request_id] = future
        try:
            logger.debug("terminal rpc send command=%s request_id=%s payload=%s", command, request_id, _preview_payload(payload))
            await self._websocket.send(build_rpc_request_message(request_id=request_id, command=command, payload=payload))
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            logger.debug("terminal rpc recv command=%s request_id=%s code=%s", command, request_id, response.code)
            return response
        except asyncio.TimeoutError:
            logger.warning(
                "terminal rpc timeout command=%s request_id=%s timeout_seconds=%s payload=%s",
                command,
                request_id,
                timeout_seconds,
                _preview_payload(payload),
            )
            raise
        finally:
            self._pending.pop(request_id, None)

    async def send_stream(self, *, tag: str, raw_bytes: bytes, data: object | None = None) -> None:
        await self._websocket.send(build_stream_message(stream_id=str(uuid4()), tag=tag, raw_bytes=raw_bytes, data=data))

    async def notify(self, *, command: str, payload: object | None = None) -> None:
        request_id = str(uuid4())
        logger.debug("terminal rpc notify command=%s request_id=%s payload=%s", command, request_id, _preview_payload(payload))
        await self._websocket.send(build_rpc_request_message(request_id=request_id, command=command, payload=payload))

    def resolve(self, response: OpenXiaoAIResponse) -> bool:
        future = self._pending.get(response.id)
        if future is None or future.done():
            return False
        future.set_result(response)
        return True

    def fail_all(self, exc: BaseException) -> None:
        for future in list(self._pending.values()):
            if future.done():
                continue
            future.set_exception(exc)


class GatewayApiError(RuntimeError):
    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(slots=True)
class GatewayDiscoveryStatus:
    claimed: bool
    binding: VoiceTerminalBinding | None


class GatewayApiClient:
    def __init__(self) -> None:
        self._base_url = settings.api_server_http_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "x-voice-gateway-token": settings.voice_gateway_token,
        }

    def report_discovery(self, payload: dict[str, Any]) -> GatewayDiscoveryStatus:
        response = self._request("POST", "/integrations/discoveries/report", payload)
        return _parse_gateway_discovery_status(response)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url=f"{self._base_url}{path}",
            data=data,
            headers=self._headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            detail = body
            try:
                detail = json.loads(body).get("detail", body)
            except json.JSONDecodeError:
                detail = body or exc.reason
            raise GatewayApiError(status_code=exc.code, detail=str(detail)) from exc
        except URLError as exc:
            raise GatewayApiError(status_code=0, detail=str(exc.reason)) from exc


@dataclass
class GatewayRuntimeState:
    context: TerminalBridgeContext
    terminal_rpc: TerminalRpcClient
    remote_addr: str | None
    api_websocket: Any | None = None
    api_reader_task: asyncio.Task[Any] | None = None
    playback_worker_task: asyncio.Task[Any] | None = None
    takeover_keepalive_task: asyncio.Task[Any] | None = None
    takeover_recovery_deadline: float | None = None
    pending_playback_commands: deque[GatewayCommand] = field(default_factory=deque)
    playback_queue_event: asyncio.Event = field(default_factory=asyncio.Event)
    interrupted_playback_session_ids: set[str] = field(default_factory=set)
    native_barge_in_active: bool = False
    suppressed_stop_phrase: str | None = None
    suppressed_stop_phrase_deadline: float | None = None
    voiceprint_round_task: asyncio.Task[Any] | None = None
    voiceprint_capture_session_id: str | None = None
    voiceprint_capture_audio_bytes: int = 0
    last_local_voiceprint_prompt_key: str | None = None
    native_first_audio_chunks: deque[bytes] = field(default_factory=deque)
    native_first_audio_bytes: int = 0
    activation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_active(self) -> bool:
        return self.api_websocket is not None and self.api_reader_task is not None


class OpenXiaoAIGateway:
    def __init__(self) -> None:
        self._server = None

    async def run(self) -> None:
        self._server = await websockets.serve(
            self._handle_terminal_connection,
            settings.listen_host,
            settings.listen_port,
            max_size=None,
        )
        logger.info("open-xiaoai-gateway listening on %s:%s", settings.listen_host, settings.listen_port)
        await self._server.wait_closed()

    async def _handle_terminal_connection(self, websocket) -> None:
        remote_addr = _extract_remote_addr(websocket)
        terminal_rpc = TerminalRpcClient(websocket)
        context = TerminalBridgeContext()
        state = GatewayRuntimeState(
            context=context,
            terminal_rpc=terminal_rpc,
            remote_addr=remote_addr,
        )
        api_client = GatewayApiClient()
        binding_sync_task: asyncio.Task[Any] | None = None
        terminal_message_queue: asyncio.Queue[object] = asyncio.Queue()
        terminal_reader_task = asyncio.create_task(self._forward_terminal_messages(websocket, state, terminal_message_queue))
        terminal_processor_task = asyncio.create_task(self._process_terminal_messages(state, terminal_message_queue))

        try:
            discovery = await self._discover_terminal(terminal_rpc)
            context.apply_discovery(discovery)
            initial_status = await asyncio.to_thread(
                api_client.report_discovery,
                build_discovery_report_payload(context, remote_addr=remote_addr, connection_status="online"),
            )
            if initial_status.claimed and initial_status.binding is not None:
                await self._activate_terminal(state, initial_status.binding)
            binding_sync_task = asyncio.create_task(self._sync_binding_state_loop(state, api_client))

            done, pending = await asyncio.wait(
                {terminal_reader_task, terminal_processor_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )
            for task in done:
                exc = task.exception()
                if exc is None:
                    continue
                for pending_task in pending:
                    pending_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pending_task
                raise exc
            for pending_task in pending:
                await pending_task
        finally:
            await self._cancel_voiceprint_round_task(state, reason="terminal_disconnect")
            await self._stop_takeover_keepalive(
                state,
                reason="terminal_disconnect",
                suppress_errors=True,
            )

            if binding_sync_task is not None:
                binding_sync_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await binding_sync_task

            if not terminal_reader_task.done():
                terminal_reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await terminal_reader_task
            if not terminal_processor_task.done():
                terminal_processor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await terminal_processor_task

            await self._report_offline_discovery(api_client, state)

            if state.api_websocket is not None:
                offline_event = build_terminal_offline_event(context)
                if offline_event is not None:
                    try:
                        await state.api_websocket.send(offline_event.model_dump_json())
                    except ConnectionClosed as exc:
                        logger.info(
                            "skip terminal.offline because api websocket already closed terminal_id=%s code=%s reason=%s",
                            context.terminal_id,
                            getattr(exc.rcvd, "code", None),
                            getattr(exc.rcvd, "reason", ""),
                        )
                    except Exception:
                        logger.exception("failed to report terminal.offline terminal_id=%s", context.terminal_id)
            if state.api_reader_task is not None:
                state.api_reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, ConnectionClosed):
                    await state.api_reader_task
            if state.playback_worker_task is not None:
                state.playback_worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await state.playback_worker_task
            if state.api_websocket is not None:
                await state.api_websocket.close()

    async def _forward_terminal_messages(
        self,
        websocket,
        state: GatewayRuntimeState,
        message_queue: asyncio.Queue[object],
    ) -> None:
        terminal_rpc = state.terminal_rpc
        try:
            async for message in websocket:
                if isinstance(message, str):
                    frame = parse_open_xiaoai_text_message(message)
                    if frame.Response is not None:
                        terminal_rpc.resolve(frame.Response)
                        continue
                await message_queue.put(message)
        except Exception as exc:
            terminal_rpc.fail_all(exc)
            raise
        else:
            terminal_rpc.fail_all(ConnectionError("terminal websocket closed"))
        finally:
            await message_queue.put(_TERMINAL_MESSAGE_QUEUE_CLOSE)

    async def _process_terminal_messages(self, state: GatewayRuntimeState, message_queue: asyncio.Queue[object]) -> None:
        while True:
            message = await message_queue.get()
            if message is _TERMINAL_MESSAGE_QUEUE_CLOSE:
                return
            assert isinstance(message, (str, bytes))
            await self._handle_terminal_message(message=message, state=state)

    async def _handle_terminal_message(self, *, message: str | bytes, state: GatewayRuntimeState) -> None:
        context = state.context
        terminal_rpc = state.terminal_rpc

        if isinstance(message, bytes):
            if not state.is_active():
                return
            stream = parse_open_xiaoai_stream(message)
            raw_bytes = stream.raw_bytes() if stream.tag == "record" else b""
            if raw_bytes and _should_buffer_native_first_audio(state):
                _buffer_native_first_audio_chunk(state, raw_bytes)
            if raw_bytes and _should_hold_native_first_audio_until_takeover(state):
                return
            events = translate_audio_chunk(message, context)
            for event in events:
                self._record_voiceprint_capture_audio(state, event)
                await state.api_websocket.send(event.model_dump_json())
            return

        frame = parse_open_xiaoai_text_message(message)
        if frame.Response is not None:
            terminal_rpc.resolve(frame.Response)
            return
        if frame.Request is not None:
            logger.warning("ignore unexpected client request command=%s", frame.Request.command)
            return
        if not state.is_active():
            return

        if _has_pending_or_active_playback(state) and _is_kws_event_frame(frame):
            if not state.native_barge_in_active:
                interrupted = await self._interrupt_local_playback_if_needed(
                    api_websocket=state.api_websocket,
                    state=state,
                    reason="terminal:kws_during_local_playback",
                    transcript=None,
                    completion_status="interrupted",
                    interrupt_native=True,
                )
                if interrupted:
                    state.native_barge_in_active = True
                    logger.info(
                        "interrupt local playback on kws during local playback fingerprint=%s",
                        context.fingerprint,
                    )
            return

        if _has_pending_or_active_playback(state) and _is_instruction_vad_begin_frame(frame):
            if not state.native_barge_in_active:
                interrupted = await self._interrupt_local_playback_if_needed(
                    api_websocket=state.api_websocket,
                    state=state,
                    reason="terminal:vad_begin_during_local_playback",
                    transcript=None,
                    completion_status="interrupted",
                    interrupt_native=True,
                )
                if interrupted:
                    state.native_barge_in_active = True
                    logger.info(
                        "interrupt local playback on vad_begin during local playback fingerprint=%s",
                        context.fingerprint,
                    )
                return

        stop_transcript = _extract_final_instruction_transcript(message)
        if (
            stop_transcript
            and state.native_barge_in_active
            and not _has_pending_or_active_playback(state)
            and _should_interrupt_local_playback(stop_transcript)
        ):
            state.native_barge_in_active = False
            state.suppressed_stop_phrase = _normalize_stop_phrase(stop_transcript)
            state.suppressed_stop_phrase_deadline = asyncio.get_running_loop().time() + _STOP_PHRASE_SUPPRESSION_SECONDS
            logger.info(
                "suppress final stop phrase after local playback barge-in fingerprint=%s transcript=%s",
                context.fingerprint,
                stop_transcript,
            )
            return
        if stop_transcript and _is_stop_phrase_suppressed(state, stop_transcript):
            logger.info(
                "suppress repeated local playback stop phrase fingerprint=%s transcript=%s",
                context.fingerprint,
                stop_transcript,
            )
            return
        if stop_transcript and _should_interrupt_local_playback(stop_transcript):
            interrupted = await self._interrupt_local_playback_if_needed(
                api_websocket=state.api_websocket,
                state=state,
                reason="terminal:stop_phrase",
                transcript=stop_transcript,
                completion_status="interrupted",
                interrupt_native=True,
            )
            if interrupted:
                state.native_barge_in_active = False
                logger.info(
                    "intercepted local playback stop phrase fingerprint=%s transcript=%s",
                    context.fingerprint,
                    stop_transcript,
                )
                return

        translation = translate_text_message_result(message, context)
        if _is_kws_event_frame(frame) and context.last_invocation_decision == "await_takeover_prefix":
            _clear_native_first_audio_buffer(state)
        if translation.terminal_messages:
            try:
                await self._dispatch_local_terminal_messages(
                    state=state,
                    terminal_rpc=terminal_rpc,
                    outgoing_messages=translation.terminal_messages,
                )
            except Exception:
                logger.warning(
                    "native-first 本地 takeover pause 失败 fingerprint=%s reason=%s",
                    context.fingerprint,
                    context.last_passthrough_reason or context.last_invocation_decision,
                    exc_info=True,
                )
                if context.last_invocation_decision == "familyclaw_takeover":
                    context.last_invocation_decision = "native_passthrough"
                    context.last_passthrough_reason = "takeover_pause_failed"
                    _clear_native_first_audio_buffer(state)
                    logger.info(
                        "skip takeover forwarding because local pause failed fingerprint=%s",
                        context.fingerprint,
                    )
                    return

        events_to_send = translation.events
        if _is_final_instruction_frame(frame):
            if context.last_invocation_decision == "familyclaw_takeover":
                events_to_send = _inject_native_first_buffered_audio_events(state, events_to_send)
            else:
                _clear_native_first_audio_buffer(state)

        for event in events_to_send:
            await state.api_websocket.send(event.model_dump_json())

        if _is_final_instruction_frame(frame):
            state.native_barge_in_active = False

        if _translation_released_active_playback(translation):
            await self._dispatch_next_pending_playback(api_websocket=state.api_websocket, state=state, reason="terminal_playback_released")

    async def _discover_terminal(self, terminal_rpc: TerminalRpcClient) -> TerminalDiscoveryInfo:
        version_response = await terminal_rpc.call(command="get_version")
        model_response = await terminal_rpc.call(command="run_shell", payload="echo $(micocfg_model)")
        sn_response = await terminal_rpc.call(command="run_shell", payload="echo $(micocfg_sn)")
        runtime_version = _parse_version_response(version_response)
        model = _parse_shell_stdout(model_response)
        sn = _parse_shell_stdout(sn_response)
        return build_discovery_info(
            model=model,
            sn=sn,
            runtime_version=runtime_version,
            capabilities=None,
        )

    async def _sync_binding_state_loop(self, state: GatewayRuntimeState, api_client: GatewayApiClient) -> None:
        while True:
            await asyncio.sleep(settings.claim_poll_interval_seconds)
            if not state.context.fingerprint:
                continue
            try:
                status = await asyncio.to_thread(
                    api_client.report_discovery,
                    build_discovery_report_payload(
                        state.context,
                        remote_addr=state.remote_addr,
                        connection_status="online",
                    ),
                )
            except GatewayApiError as exc:
                logger.warning("claim poll failed status=%s detail=%s", exc.status_code, exc.detail)
                continue

            if status.claimed and status.binding is not None:
                if state.is_active():
                    await self._refresh_active_binding(state, status.binding)
                    continue
                await self._activate_terminal(state, status.binding)
                continue

            if state.is_active():
                logger.debug(
                    "skip active binding refresh because binding is unavailable fingerprint=%s claimed=%s",
                    state.context.fingerprint,
                    status.claimed,
                )

    async def _activate_terminal(self, state: GatewayRuntimeState, binding: VoiceTerminalBinding) -> None:
        async with state.activation_lock:
            if state.is_active():
                return
            state.context.apply_binding(binding)
            api_websocket = await self._connect_api(state.context)
            api_reader_task = asyncio.create_task(
                self._forward_api_commands(api_websocket, state),
            )

            try:
                await api_websocket.send(build_terminal_online_event(state.context).model_dump_json())
                if settings.recording_enabled:
                    response = await state.terminal_rpc.call(
                        command="start_recording",
                        payload=build_recording_rpc_payload(),
                    )
                    if not self._is_successful_response(response):
                        raise RuntimeError(self._describe_response(response))
            except Exception:
                api_reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await api_reader_task
                await api_websocket.close()
                logger.exception("failed to activate claimed terminal fingerprint=%s", state.context.fingerprint)
                return

            state.api_websocket = api_websocket
            state.api_reader_task = api_reader_task
            logger.info(
                "claimed terminal activated fingerprint=%s household_id=%s terminal_id=%s invocation_mode=%s takeover_prefixes=%s",
                state.context.fingerprint,
                state.context.household_id,
                state.context.terminal_id,
                state.context.invocation_mode,
                ",".join(state.context.takeover_prefixes),
            )
            await self._maybe_schedule_local_voiceprint_round_prompt(
                api_websocket=api_websocket,
                state=state,
                previous_pending_enrollment=None,
                refresh_reason="terminal_activated",
            )

    async def _refresh_active_binding(self, state: GatewayRuntimeState, binding: VoiceTerminalBinding, *, reason: str | None = None) -> None:
        async with state.activation_lock:
            if not state.is_active():
                return
            if not _can_hot_refresh_binding(state.context, binding):
                logger.warning(
                    "skip binding hot refresh because identity changed fingerprint=%s current_household_id=%s current_terminal_id=%s next_household_id=%s next_terminal_id=%s",
                    state.context.fingerprint,
                    state.context.household_id,
                    state.context.terminal_id,
                    binding.household_id,
                    binding.terminal_id,
                )
                return

            changes = _collect_binding_refresh_changes(state.context, binding)
            if not changes:
                return

            previous_pending_enrollment = state.context.pending_voiceprint_enrollment
            if "pending_voiceprint_enrollment" in changes:
                await self._cancel_voiceprint_round_task(state, reason="binding_refresh")
                await self._cancel_active_voiceprint_session(
                    api_websocket=state.api_websocket,
                    state=state,
                    reason="binding_refresh",
                )
            state.context.apply_binding(binding)
            logger.info(
                "refreshed active terminal binding fingerprint=%s changes=%s invocation_mode=%s takeover_prefixes=%s",
                state.context.fingerprint,
                ",".join(changes),
                state.context.invocation_mode,
                ",".join(state.context.takeover_prefixes),
            )
            await self._maybe_schedule_local_voiceprint_round_prompt(
                api_websocket=state.api_websocket,
                state=state,
                previous_pending_enrollment=previous_pending_enrollment,
                refresh_reason=reason,
            )

    async def _connect_api(self, context: TerminalBridgeContext):
        query = urlencode(
            {
                "household_id": context.household_id,
                "terminal_id": context.terminal_id,
                "fingerprint": context.fingerprint,
            }
        )
        ws_url = f"{settings.api_server_ws_url}?{query}"
        logger.info("connect api-server realtime.voice terminal_id=%s", context.terminal_id)
        return await websockets.connect(
            ws_url,
            additional_headers={"x-voice-gateway-token": settings.voice_gateway_token},
            max_size=None,
        )

    def _log_api_websocket_closed(self, *, state: GatewayRuntimeState, exc: ConnectionClosed, action: str) -> None:
        logger.info(
            "%s terminal_id=%s fingerprint=%s code=%s reason=%s",
            action,
            state.context.terminal_id,
            state.context.fingerprint,
            getattr(exc.rcvd, "code", None),
            getattr(exc.rcvd, "reason", ""),
        )

    async def _send_api_message(self, *, api_websocket, state: GatewayRuntimeState, message: str, event_type: str) -> None:
        # Treat a closed api websocket as a disconnect, not a playback failure.
        try:
            await api_websocket.send(message)
        except ConnectionClosed as exc:
            self._log_api_websocket_closed(
                state=state,
                exc=exc,
                action=f"skip api event because websocket already closed event_type={event_type}",
            )
            raise

    async def _forward_api_commands(self, api_websocket, state: GatewayRuntimeState) -> None:
        try:
            async for raw_message in api_websocket:
                command = GatewayCommand.model_validate_json(raw_message)
                logger.info(
                    "recv api command type=%s terminal_id=%s session_id=%s payload=%s",
                    command.type,
                    command.terminal_id,
                    command.session_id,
                    _preview_payload(command.payload),
                )

                try:
                    if command.type == "binding.refresh":
                        await self._handle_binding_refresh_command(state=state, command=command)
                        continue

                    if command.type == "play.start":
                        await self._handle_play_start_command(
                            api_websocket=api_websocket,
                            state=state,
                            command=command,
                        )
                        continue

                    if command.type in {"play.stop", "play.abort"}:
                        handled = await self._interrupt_local_playback_if_needed(
                            api_websocket=api_websocket,
                            state=state,
                            reason=f"api:{command.type}",
                            transcript=None,
                            completion_status="completed" if command.type == "play.stop" else "interrupted",
                            ts=command.ts,
                            interrupt_native=False,
                        )
                        if handled:
                            continue
                        self._clear_pending_playback_queue(
                            state,
                            reason=f"api:{command.type}",
                        )

                    await self._dispatch_api_command(
                        api_websocket=api_websocket,
                        state=state,
                        command=command,
                    )
                except ConnectionClosed:
                    raise
                except Exception:
                    logger.exception("failed to dispatch command type=%s", command.type)
                    failed_event = build_playback_failed_event(
                        state.context,
                        detail="gateway dispatch failed",
                        error_code="playback_failed",
                    )
                    if failed_event is not None:
                        await self._send_api_message(
                            api_websocket=api_websocket,
                            state=state,
                            message=failed_event.model_dump_json(),
                            event_type="playback.failed",
                        )
                    if command.type == "play.start":
                        await self._dispatch_next_pending_playback(api_websocket=api_websocket, state=state, reason="play_start_dispatch_failed")
        except ConnectionClosed as exc:
            self._log_api_websocket_closed(state=state, exc=exc, action="api websocket closed")

    async def _handle_play_start_command(self, *, api_websocket, state: GatewayRuntimeState, command: GatewayCommand) -> None:
        session_id = str(command.session_id or "").strip()
        if session_id and session_id in state.interrupted_playback_session_ids:
            logger.info(
                "drop api play.start for interrupted session terminal_id=%s session_id=%s playback_id=%s",
                command.terminal_id,
                command.session_id,
                command.payload.get("playback_id"),
            )
            return
        state.pending_playback_commands.append(command)
        state.playback_queue_event.set()
        self._ensure_playback_worker(
            api_websocket=api_websocket,
            state=state,
        )
        logger.info(
            "queue api play.start terminal_id=%s session_id=%s playback_id=%s pending=%s",
            command.terminal_id,
            command.session_id,
            command.payload.get("playback_id"),
            len(state.pending_playback_commands),
        )

    async def _handle_binding_refresh_command(self, *, state: GatewayRuntimeState, command: GatewayCommand) -> None:
        binding = _parse_voice_terminal_binding(command.payload.get("binding"))
        if binding is None:
            logger.warning(
                "skip binding.refresh because payload is invalid terminal_id=%s payload=%s",
                command.terminal_id,
                _preview_payload(command.payload),
            )
            return
        await self._refresh_active_binding(
            state,
            binding,
            reason=_coerce_optional_text(command.payload.get("reason")),
        )

    def _ensure_playback_worker(self, *, api_websocket, state: GatewayRuntimeState) -> None:
        task = state.playback_worker_task
        if task is not None and not task.done():
            return
        state.playback_worker_task = asyncio.create_task(self._run_playback_worker(api_websocket, state))

    async def _run_playback_worker(self, api_websocket, state: GatewayRuntimeState) -> None:
        try:
            while True:
                if state.context.active_playback_id:
                    await asyncio.sleep(0.05)
                    continue

                if not state.pending_playback_commands:
                    state.playback_queue_event.clear()
                    await state.playback_queue_event.wait()
                    continue

                command = state.pending_playback_commands.popleft()
                session_id = str(command.session_id or "").strip()
                if session_id and session_id in state.interrupted_playback_session_ids:
                    logger.info(
                        "skip queued play.start for interrupted session terminal_id=%s session_id=%s playback_id=%s pending=%s",
                        command.terminal_id,
                        command.session_id,
                        command.payload.get("playback_id"),
                        len(state.pending_playback_commands),
                    )
                    continue

                logger.info(
                    "dispatch queued play.start terminal_id=%s session_id=%s playback_id=%s pending=%s",
                    command.terminal_id,
                    command.session_id,
                    command.payload.get("playback_id"),
                    len(state.pending_playback_commands),
                )
                try:
                    await self._dispatch_api_command(
                        api_websocket=api_websocket,
                        state=state,
                        command=command,
                    )
                except ConnectionClosed as exc:
                    self._log_api_websocket_closed(
                        state=state,
                        exc=exc,
                        action="playback worker stop because api websocket closed",
                    )
                    return
                except Exception:
                    logger.exception("failed to dispatch queued play.start playback_id=%s", command.payload.get("playback_id"))
                    failed_event = build_playback_failed_event(
                        state.context,
                        detail="gateway dispatch failed",
                        error_code="playback_failed",
                    )
                    if failed_event is not None:
                        try:
                            await self._send_api_message(
                                api_websocket=api_websocket,
                                state=state,
                                message=failed_event.model_dump_json(),
                                event_type="playback.failed",
                            )
                        except ConnectionClosed as exc:
                            self._log_api_websocket_closed(
                                state=state,
                                exc=exc,
                                action="playback worker stop because api websocket closed",
                            )
                            return
        except asyncio.CancelledError:
            raise
        finally:
            if state.playback_worker_task is asyncio.current_task():
                state.playback_worker_task = None

    async def _dispatch_api_command(self, *, api_websocket, state: GatewayRuntimeState, command: GatewayCommand) -> None:
        if _is_voiceprint_prompt_beep_command(command):
            logger.info(
                "delay voiceprint prompt beep before playback fingerprint=%s session_id=%s delay_seconds=%.1f",
                state.context.fingerprint,
                command.session_id,
                _VOICEPRINT_PROMPT_DELAY_SECONDS,
            )
            await asyncio.sleep(_VOICEPRINT_PROMPT_DELAY_SECONDS)

        outgoing_messages = translate_command_to_terminal(command, state.context)
        if not outgoing_messages:
            return

        if command.type in {"play.start", "play.stop", "play.abort", "speaker.turn_on"}:
            await self._stop_takeover_keepalive(
                state,
                reason=f"api:{command.type}",
                suppress_errors=False,
            )
        if command.type == "play.start":
            await self._wait_takeover_recovery_if_needed(state)

        await self._dispatch_terminal_messages(
            api_websocket=api_websocket,
            state=state,
            command=command,
            outgoing_messages=outgoing_messages,
        )
        if _is_voiceprint_prompt_beep_command(command):
            self._schedule_voiceprint_round_after_prompt(
                api_websocket=api_websocket,
                state=state,
                command=command,
            )

    async def _dispatch_next_pending_playback(self, *, api_websocket, state: GatewayRuntimeState, reason: str) -> None:
        if state.context.active_playback_id:
            return
        if not state.pending_playback_commands:
            return
        logger.info(
            "wake playback worker fingerprint=%s pending=%s reason=%s",
            state.context.fingerprint,
            len(state.pending_playback_commands),
            reason,
        )
        state.playback_queue_event.set()
        self._ensure_playback_worker(
            api_websocket=api_websocket,
            state=state,
        )

    def _clear_pending_playback_queue(self, state: GatewayRuntimeState, *, reason: str) -> None:
        pending_count = len(state.pending_playback_commands)
        state.pending_playback_commands.clear()
        state.playback_queue_event.clear()
        if pending_count <= 0:
            return
        logger.info(
            "cleared pending playback queue fingerprint=%s reason=%s count=%s",
            state.context.fingerprint,
            reason,
            pending_count,
        )

    async def _dispatch_terminal_messages(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        command: GatewayCommand,
        outgoing_messages: list[TerminalRpcRequest | TerminalBinaryStream],
    ) -> None:
        terminal_rpc = state.terminal_rpc
        context = state.context
        last_response: OpenXiaoAIResponse | None = None

        for outgoing in outgoing_messages:
            if isinstance(outgoing, TerminalRpcRequest):
                if _is_blocking_tts_request(outgoing):
                    await self._dispatch_blocking_tts_request(
                        api_websocket=api_websocket,
                        state=state,
                        command=command,
                        outgoing=outgoing,
                    )
                    return
                if _should_fire_and_forget_terminal_request(outgoing):
                    logger.info(
                        "dispatch terminal notify command=%s payload=%s",
                        outgoing.command,
                        _preview_payload(outgoing.payload),
                    )
                    await terminal_rpc.notify(command=outgoing.command, payload=outgoing.payload)
                    if _is_background_tts_request(outgoing):
                        asyncio.create_task(self._probe_background_tts_log(state))
                    continue
                logger.info(
                    "dispatch terminal rpc command=%s payload=%s",
                    outgoing.command,
                    _preview_payload(outgoing.payload),
                )
                response = await terminal_rpc.call(command=outgoing.command, payload=outgoing.payload)
                last_response = response
                if not self._is_successful_response(response):
                    failed_event = build_playback_failed_event(
                        context,
                        detail=self._describe_response(response),
                        error_code="playback_failed",
                    )
                    if failed_event is not None:
                        await self._send_api_message(
                            api_websocket=api_websocket,
                            state=state,
                            message=failed_event.model_dump_json(),
                            event_type="playback.failed",
                        )
                    return
                continue

            await terminal_rpc.send_stream(tag=outgoing.tag, raw_bytes=outgoing.raw_bytes, data=outgoing.data)

        if command.type == "play.start":
            started_event = build_playback_started_event(context)
            if started_event is not None:
                await self._send_api_message(
                    api_websocket=api_websocket,
                    state=state,
                    message=started_event.model_dump_json(),
                    event_type="playback.started",
                )
            return

        if command.type == "play.stop":
            if context.active_playback_id and context.active_playback_session_id and context.terminal_id:
                await self._send_api_message(
                    api_websocket=api_websocket,
                    state=state,
                    message=json.dumps(
                        {
                            "type": "playback.receipt",
                            "terminal_id": context.terminal_id,
                            "session_id": context.active_playback_session_id,
                            "seq": context.next_seq(),
                            "payload": {
                                "playback_id": context.active_playback_id,
                                "status": "completed",
                                "detail": command.payload.get("reason"),
                                "error_code": None,
                            },
                            "ts": command.ts,
                        },
                        ensure_ascii=False,
                    ),
                    event_type="playback.receipt",
                )
                context.clear_playback()
            return

        if command.type == "play.abort":
            interrupted_event = build_terminal_interrupted_json(
                context=context,
                reason=command.payload.get("reason"),
                ts=command.ts,
            )
            if interrupted_event is not None:
                await self._send_api_message(
                    api_websocket=api_websocket,
                    state=state,
                    message=interrupted_event,
                    event_type="playback.interrupted",
                )
            return

        _ = last_response

    async def _dispatch_blocking_tts_request(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        command: GatewayCommand,
        outgoing: TerminalRpcRequest,
    ) -> None:
        context = state.context
        terminal_rpc = state.terminal_rpc
        playback_id_before_dispatch = context.active_playback_id
        playback_session_id_before_dispatch = context.active_playback_session_id
        started_event = build_playback_started_event(context)
        if started_event is not None:
            await self._send_api_message(
                api_websocket=api_websocket,
                state=state,
                message=started_event.model_dump_json(),
                event_type="playback.started",
            )

        timeout_seconds = _estimate_tts_timeout_seconds(command.payload.get("text"))
        logger.info(
            "dispatch blocking terminal rpc command=%s timeout_seconds=%.1f payload=%s",
            outgoing.command,
            timeout_seconds,
            _preview_payload(outgoing.payload),
        )
        response = await terminal_rpc.call(
            command=outgoing.command,
            payload=outgoing.payload,
            timeout_seconds=timeout_seconds,
        )
        if not self._is_successful_response(response):
            if not _is_same_playback(context, playback_id_before_dispatch, playback_session_id_before_dispatch):
                return
            failed_event = build_playback_failed_event(
                context,
                detail=self._describe_response(response),
                error_code="playback_failed",
            )
            if failed_event is not None:
                await self._send_api_message(
                    api_websocket=api_websocket,
                    state=state,
                    message=failed_event.model_dump_json(),
                    event_type="playback.failed",
                )
            return

        await self._wait_terminal_playback_idle(state)
        if not _is_same_playback(context, playback_id_before_dispatch, playback_session_id_before_dispatch):
            return
        completed_event = self._build_playback_completed_json(
            context=context,
            playback_id=context.active_playback_id,
            session_id=context.active_playback_session_id,
            detail="blocking_tts_completed",
            ts=command_ts_now(),
        )
        if completed_event is not None:
            await self._send_api_message(
                api_websocket=api_websocket,
                state=state,
                message=completed_event,
                event_type="playback.completed",
            )

    async def _wait_terminal_playback_idle(self, state: GatewayRuntimeState) -> None:
        for attempt in range(4):
            playing_state = await self._get_terminal_playing_state(state)
            if playing_state in {None, "idle"}:
                state.context.last_playing_state = "idle"
                return
            logger.debug(
                "terminal still playing after blocking tts fingerprint=%s attempt=%s state=%s",
                state.context.fingerprint,
                attempt + 1,
                playing_state,
            )
            await asyncio.sleep(0.05)

    async def _get_terminal_playing_state(self, state: GatewayRuntimeState) -> str | None:
        try:
            response = await state.terminal_rpc.call(
                command="run_shell",
                payload="mphelper mute_stat",
                timeout_seconds=3.0,
            )
        except Exception:
            logger.debug(
                "failed to query terminal playing state fingerprint=%s",
                state.context.fingerprint,
                exc_info=True,
            )
            return None

        stdout = _parse_shell_stdout_safe(response)
        if "1" in stdout:
            return "playing"
        if "2" in stdout:
            return "paused"
        if "0" in stdout:
            return "idle"
        return None

    def _build_playback_completed_json(
        self,
        *,
        context: TerminalBridgeContext,
        playback_id: str | None,
        session_id: str | None,
        detail: str | None,
        ts: str,
    ) -> str | None:
        if not playback_id or not session_id or not context.terminal_id:
            return None
        payload = {
            "type": "playback.receipt",
            "terminal_id": context.terminal_id,
            "session_id": session_id,
            "seq": context.next_seq(),
            "payload": {
                "playback_id": playback_id,
                "status": "completed",
                "detail": detail,
                "error_code": None,
            },
            "ts": ts,
        }
        context.clear_playback()
        return json.dumps(payload, ensure_ascii=False)

    async def _dispatch_local_terminal_messages(
        self,
        *,
        state: GatewayRuntimeState,
        terminal_rpc: TerminalRpcClient,
        outgoing_messages: list[TerminalRpcRequest | TerminalBinaryStream],
    ) -> None:
        for outgoing in outgoing_messages:
            if isinstance(outgoing, TerminalRpcRequest):
                if _is_takeover_abort_request(outgoing):
                    await self._interrupt_native_xiaoai(state)
                    continue
                response = await terminal_rpc.call(command=outgoing.command, payload=outgoing.payload)
                if not self._is_successful_response(response):
                    raise RuntimeError(self._describe_response(response))
                continue
            await terminal_rpc.send_stream(tag=outgoing.tag, raw_bytes=outgoing.raw_bytes, data=outgoing.data)

    async def _interrupt_local_playback_if_needed(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        reason: str,
        transcript: str | None,
        completion_status: str,
        ts: str | None = None,
        interrupt_native: bool = False,
    ) -> bool:
        if not _has_pending_or_active_playback(state):
            return False

        await self._cancel_playback_worker(state, reason=reason)

        session_ids = _collect_playback_session_ids(state)
        if session_ids:
            state.interrupted_playback_session_ids.update(session_ids)
            while len(state.interrupted_playback_session_ids) > _MAX_INTERRUPTED_PLAYBACK_SESSIONS:
                state.interrupted_playback_session_ids.pop()

        logger.info(
            "interrupt local playback fingerprint=%s reason=%s transcript=%s active_playback_id=%s pending=%s interrupted_sessions=%s",
            state.context.fingerprint,
            reason,
            transcript,
            state.context.active_playback_id,
            len(state.pending_playback_commands),
            ",".join(sorted(session_ids)) if session_ids else "<empty>",
        )
        if transcript and _should_interrupt_local_playback(transcript):
            state.suppressed_stop_phrase = _normalize_stop_phrase(transcript)
            state.suppressed_stop_phrase_deadline = asyncio.get_running_loop().time() + _STOP_PHRASE_SUPPRESSION_SECONDS

        self._clear_pending_playback_queue(state, reason=reason)
        state.native_barge_in_active = False

        event_json: str | None = None
        if completion_status == "completed":
            event_json = self._build_playback_completed_json(
                context=state.context,
                playback_id=state.context.active_playback_id,
                session_id=state.context.active_playback_session_id,
                detail=transcript or reason,
                ts=ts or command_ts_now(),
            )
        else:
            event_json = build_terminal_interrupted_json(
                context=state.context,
                reason=transcript or reason,
                ts=ts or command_ts_now(),
            )
        state.context.last_playing_state = "idle"

        native_interrupt_task: asyncio.Task[Any] | None = None
        if interrupt_native:
            native_interrupt_task = asyncio.create_task(
                self._interrupt_native_xiaoai_best_effort(state, reason=reason),
            )

        await self._stop_takeover_keepalive(
            state,
            reason=reason,
            suppress_errors=True,
        )
        try:
            response = await state.terminal_rpc.call(
                command="run_shell",
                payload=_LOCAL_PLAYBACK_STOP_COMMAND,
                timeout_seconds=8.0,
            )
            if not self._is_successful_response(response):
                logger.warning(
                    "local playback stop command returned non-zero fingerprint=%s reason=%s detail=%s",
                    state.context.fingerprint,
                    reason,
                    self._describe_response(response),
                )
            else:
                logger.info(
                    "local playback stop command completed fingerprint=%s reason=%s stdout=%s stderr=%s",
                    state.context.fingerprint,
                    reason,
                    _parse_shell_stdout_safe(response) or "<empty>",
                    _describe_shell_stderr(response) or "<empty>",
                )
        except Exception:
            logger.warning(
                "failed to stop local playback fingerprint=%s reason=%s transcript=%s",
                state.context.fingerprint,
                reason,
                transcript,
                exc_info=True,
            )

        if native_interrupt_task is not None:
            await native_interrupt_task
        if event_json is not None:
            await api_websocket.send(event_json)
        return True

    async def _interrupt_native_xiaoai_best_effort(self, state: GatewayRuntimeState, *, reason: str) -> None:
        try:
            response = await state.terminal_rpc.call(
                command="run_shell",
                payload=_TAKEOVER_ABORT_COMMAND,
                timeout_seconds=5.0,
            )
            if not self._is_successful_response(response):
                logger.warning(
                    "native xiaoai interrupt returned non-zero fingerprint=%s reason=%s detail=%s",
                    state.context.fingerprint,
                    reason,
                    self._describe_response(response),
                )
                return
            state.takeover_recovery_deadline = asyncio.get_running_loop().time() + _TAKEOVER_ABORT_RECOVERY_SECONDS
            logger.info(
                "interrupted native xiaoai for local stop fingerprint=%s reason=%s recovery_seconds=%s",
                state.context.fingerprint,
                reason,
                _TAKEOVER_ABORT_RECOVERY_SECONDS,
            )
        except Exception:
            logger.warning(
                "failed to best-effort interrupt native xiaoai fingerprint=%s reason=%s",
                state.context.fingerprint,
                reason,
                exc_info=True,
            )

    async def _cancel_playback_worker(self, state: GatewayRuntimeState, *, reason: str) -> None:
        task = state.playback_worker_task
        if task is None or task.done() or task is asyncio.current_task():
            return
        logger.info(
            "cancel playback worker fingerprint=%s reason=%s",
            state.context.fingerprint,
            reason,
        )
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        state.playback_worker_task = None

    async def _report_offline_discovery(self, api_client: GatewayApiClient, state: GatewayRuntimeState) -> None:
        if not state.context.fingerprint:
            return
        try:
            await asyncio.to_thread(
                api_client.report_discovery,
                build_discovery_report_payload(
                    state.context,
                    remote_addr=state.remote_addr,
                    connection_status="offline",
                ),
            )
        except Exception:
            logger.debug("skip offline discovery report fingerprint=%s", state.context.fingerprint, exc_info=True)

    def _is_successful_response(self, response: OpenXiaoAIResponse) -> bool:
        if response.code is not None and response.code != 0:
            return False
        if isinstance(response.data, dict) and "exit_code" in response.data:
            try:
                return int(response.data.get("exit_code") or 0) == 0
            except (TypeError, ValueError):
                return False
        return True

    def _describe_response(self, response: OpenXiaoAIResponse) -> str:
        if response.msg:
            return response.msg
        if isinstance(response.data, dict):
            stderr = str(response.data.get("stderr") or "").strip()
            if stderr:
                return stderr
        return "terminal command failed"

    async def _interrupt_native_xiaoai(self, state: GatewayRuntimeState) -> None:
        await self._stop_takeover_keepalive(
            state,
            reason="takeover_abort",
            suppress_errors=True,
        )
        response = await state.terminal_rpc.call(
            command="run_shell",
            payload=_TAKEOVER_ABORT_COMMAND,
            timeout_seconds=10.0,
        )
        if not self._is_successful_response(response):
            raise RuntimeError(self._describe_response(response))

        state.takeover_recovery_deadline = asyncio.get_running_loop().time() + _TAKEOVER_ABORT_RECOVERY_SECONDS
        logger.info(
            "interrupted native xiaoai fingerprint=%s recovery_seconds=%s",
            state.context.fingerprint,
            _TAKEOVER_ABORT_RECOVERY_SECONDS,
        )

    async def _wait_takeover_recovery_if_needed(self, state: GatewayRuntimeState) -> None:
        deadline = state.takeover_recovery_deadline
        if deadline is None:
            return
        state.takeover_recovery_deadline = None
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return
        logger.info(
            "wait native xiaoai recovery before playback fingerprint=%s remaining_seconds=%.3f",
            state.context.fingerprint,
            remaining,
        )
        await asyncio.sleep(remaining)

    async def _probe_background_tts_log(self, state: GatewayRuntimeState) -> None:
        await asyncio.sleep(2.0)
        try:
            response = await state.terminal_rpc.call(
                command="run_shell",
                payload="tail -n 20 /tmp/familyclaw-tts.log",
                timeout_seconds=5.0,
            )
        except Exception:
            logger.debug(
                "failed to probe terminal tts log fingerprint=%s",
                state.context.fingerprint,
                exc_info=True,
            )
            return

        stdout = _parse_shell_stdout_safe(response)
        stderr = ""
        if isinstance(response.data, dict):
            stderr = str(response.data.get("stderr") or "").strip()
        logger.info(
            "terminal tts log fingerprint=%s stdout=%s stderr=%s",
            state.context.fingerprint,
            stdout or "<empty>",
            stderr or "<empty>",
        )

    def _schedule_voiceprint_round_after_prompt(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        command: GatewayCommand,
    ) -> None:
        existing_task = state.voiceprint_round_task
        if existing_task is not None and not existing_task.done():
            existing_task.cancel()
        state.voiceprint_round_task = asyncio.create_task(
            self._run_voiceprint_round_after_prompt(
                api_websocket=api_websocket,
                state=state,
                command=command,
            )
        )

    async def _maybe_schedule_local_voiceprint_round_prompt(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        previous_pending_enrollment: PendingVoiceprintEnrollment | None,
        refresh_reason: str | None,
    ) -> None:
        pending_enrollment = state.context.pending_voiceprint_enrollment
        previous_enrollment_id = previous_pending_enrollment.enrollment_id if previous_pending_enrollment is not None else None
        previous_sample_count = previous_pending_enrollment.sample_count if previous_pending_enrollment is not None else None
        current_enrollment_id = pending_enrollment.enrollment_id if pending_enrollment is not None else None
        current_sample_count = pending_enrollment.sample_count if pending_enrollment is not None else None
        current_sample_goal = pending_enrollment.sample_goal if pending_enrollment is not None else None

        if api_websocket is None:
            logger.info(
                "skip local voiceprint prompt scheduling because api websocket is unavailable fingerprint=%s reason=%s previous_enrollment_id=%s previous_sample_count=%s current_enrollment_id=%s current_sample_count=%s current_sample_goal=%s",
                state.context.fingerprint,
                refresh_reason,
                previous_enrollment_id,
                previous_sample_count,
                current_enrollment_id,
                current_sample_count,
                current_sample_goal,
            )
            return
        if pending_enrollment is None:
            logger.info(
                "skip local voiceprint prompt scheduling because pending enrollment is missing fingerprint=%s reason=%s previous_enrollment_id=%s previous_sample_count=%s",
                state.context.fingerprint,
                refresh_reason,
                previous_enrollment_id,
                previous_sample_count,
            )
            return
        if (
            state.voiceprint_round_task is not None
            and not state.voiceprint_round_task.done()
        ):
            logger.info(
                "skip local voiceprint prompt scheduling because round task is still running fingerprint=%s reason=%s enrollment_id=%s sample_count=%s sample_goal=%s",
                state.context.fingerprint,
                refresh_reason,
                pending_enrollment.enrollment_id,
                pending_enrollment.sample_count,
                pending_enrollment.sample_goal,
            )
            return
        if state.context.active_session_purpose == "voiceprint_enrollment":
            logger.info(
                "skip local voiceprint prompt scheduling because voiceprint session is still active fingerprint=%s reason=%s enrollment_id=%s sample_count=%s active_session_id=%s",
                state.context.fingerprint,
                refresh_reason,
                pending_enrollment.enrollment_id,
                pending_enrollment.sample_count,
                state.context.active_session_id,
            )
            return
        if state.context.active_playback_id or state.pending_playback_commands:
            logger.info(
                "skip local voiceprint prompt scheduling because playback is still busy fingerprint=%s reason=%s enrollment_id=%s sample_count=%s active_playback_id=%s pending_playback_count=%s",
                state.context.fingerprint,
                refresh_reason,
                pending_enrollment.enrollment_id,
                pending_enrollment.sample_count,
                state.context.active_playback_id,
                len(state.pending_playback_commands),
            )
            return
        if pending_enrollment.sample_count >= pending_enrollment.sample_goal:
            logger.info(
                "skip local voiceprint prompt scheduling because enrollment is already complete fingerprint=%s reason=%s enrollment_id=%s sample_count=%s sample_goal=%s",
                state.context.fingerprint,
                refresh_reason,
                pending_enrollment.enrollment_id,
                pending_enrollment.sample_count,
                pending_enrollment.sample_goal,
            )
            return

        if refresh_reason == "voiceprint_enrollment_created":
            logger.info(
                "skip local voiceprint prompt scheduling because initial round should come from api prompt fingerprint=%s enrollment_id=%s sample_count=%s sample_goal=%s",
                state.context.fingerprint,
                pending_enrollment.enrollment_id,
                pending_enrollment.sample_count,
                pending_enrollment.sample_goal,
            )
            return

        sample_count_changed = (
            previous_pending_enrollment is None
            or previous_pending_enrollment.enrollment_id != pending_enrollment.enrollment_id
            or previous_pending_enrollment.sample_count != pending_enrollment.sample_count
        )
        is_retry = (
            not sample_count_changed
            and refresh_reason == "voiceprint_enrollment_progressed"
            and previous_pending_enrollment is not None
            and previous_pending_enrollment.enrollment_id == pending_enrollment.enrollment_id
        )

        if pending_enrollment.sample_count <= 0:
            prompt_key = "created"
        else:
            prompt_key = f"{'rejected' if is_retry else 'recorded'}-{pending_enrollment.sample_count}"
        dedupe_key = f"{pending_enrollment.enrollment_id}:{prompt_key}"
        if state.last_local_voiceprint_prompt_key == dedupe_key:
            logger.info(
                "skip duplicate local voiceprint prompt fingerprint=%s reason=%s enrollment_id=%s prompt_key=%s previous_enrollment_id=%s previous_sample_count=%s current_sample_goal=%s",
                state.context.fingerprint,
                refresh_reason,
                pending_enrollment.enrollment_id,
                prompt_key,
                previous_enrollment_id,
                previous_sample_count,
                pending_enrollment.sample_goal,
            )
            return
        logger.info(
            "schedule local voiceprint prompt fingerprint=%s reason=%s enrollment_id=%s prompt_key=%s retry=%s sample_count_changed=%s previous_enrollment_id=%s previous_sample_count=%s current_sample_count=%s current_sample_goal=%s",
            state.context.fingerprint,
            refresh_reason,
            pending_enrollment.enrollment_id,
            prompt_key,
            is_retry,
            sample_count_changed,
            previous_enrollment_id,
            previous_sample_count,
            pending_enrollment.sample_count,
            pending_enrollment.sample_goal,
        )
        state.last_local_voiceprint_prompt_key = dedupe_key
        await self._enqueue_local_voiceprint_round_prompt(
            api_websocket=api_websocket,
            state=state,
            enrollment=pending_enrollment,
            prompt_key=prompt_key,
            retry=is_retry,
        )

    async def _enqueue_local_voiceprint_round_prompt(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        enrollment: PendingVoiceprintEnrollment,
        prompt_key: str,
        retry: bool,
    ) -> None:
        playback_token = uuid4().hex
        session_id = f"{_VOICEPRINT_PROMPT_SESSION_PREFIX}{enrollment.enrollment_id}:{prompt_key}"
        current_round = _get_voiceprint_current_round(enrollment)
        if retry:
            prompt_text = (
                f"刚才这一轮没有录成成功。请重新准备第 {current_round} 轮。"
                "三秒后在滴的一声后，开始朗读屏幕上的句子。"
            )
        else:
            prompt_text = (
                f"请准备第 {current_round} 轮声纹录入。"
                "三秒后在滴的一声后，开始朗读屏幕上的句子。"
            )
        tts_command = GatewayCommand.model_validate(
            {
                "type": "play.start",
                "terminal_id": state.context.terminal_id or "",
                "session_id": session_id,
                "seq": state.context.next_seq(),
                "payload": {
                    "playback_id": f"{playback_token}-tts",
                    "mode": "tts_text",
                    "text": prompt_text,
                },
                "ts": command_ts_now(),
            }
        )
        beep_command = GatewayCommand.model_validate(
            {
                "type": "play.start",
                "terminal_id": state.context.terminal_id or "",
                "session_id": session_id,
                "seq": state.context.next_seq(),
                "payload": {
                    "playback_id": f"{playback_token}-beep",
                    "mode": "audio_bytes",
                    "audio_base64": _get_voiceprint_prompt_beep_audio_base64(),
                    "content_type": "audio/pcm;rate=16000;channels=1;format=s16le",
                },
                "ts": command_ts_now(),
            }
        )
        logger.info(
            "enqueue local voiceprint prompt fingerprint=%s session_id=%s prompt_key=%s retry=%s current_round=%s",
            state.context.fingerprint,
            session_id,
            prompt_key,
            retry,
            current_round,
        )
        await self._handle_play_start_command(
            api_websocket=api_websocket,
            state=state,
            command=tts_command,
        )
        await self._handle_play_start_command(
            api_websocket=api_websocket,
            state=state,
            command=beep_command,
        )

    async def _run_voiceprint_round_after_prompt(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        command: GatewayCommand,
    ) -> None:
        playback_id = str(command.payload.get("playback_id") or "").strip()
        prompt_session_id = str(command.session_id or "").strip()
        capture_session_id: str | None = None
        try:
            await asyncio.sleep(_VOICEPRINT_PROMPT_BEEP_SETTLE_SECONDS)
            if not state.is_active():
                return
            if _is_same_playback(state.context, playback_id, prompt_session_id):
                completed_event = self._build_playback_completed_json(
                    context=state.context,
                    playback_id=playback_id,
                    session_id=prompt_session_id,
                    detail="voiceprint_prompt_beep_completed",
                    ts=command_ts_now(),
                )
                if completed_event is not None:
                    await api_websocket.send(completed_event)
            capture_session_id = await self._start_voiceprint_enrollment_capture(
                api_websocket=api_websocket,
                state=state,
                prompt_session_id=prompt_session_id,
            )
            if not capture_session_id:
                return
            await asyncio.sleep(_VOICEPRINT_CAPTURE_WINDOW_SECONDS)
            await self._finish_voiceprint_enrollment_capture(
                api_websocket=api_websocket,
                state=state,
                capture_session_id=capture_session_id,
            )
        except asyncio.CancelledError:
            raise
        finally:
            if state.voiceprint_round_task is asyncio.current_task():
                state.voiceprint_round_task = None
            if capture_session_id and state.voiceprint_capture_session_id == capture_session_id:
                state.voiceprint_capture_session_id = None
                state.voiceprint_capture_audio_bytes = 0

    async def _start_voiceprint_enrollment_capture(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        prompt_session_id: str,
    ) -> str | None:
        enrollment = state.context.pending_voiceprint_enrollment
        if enrollment is None:
            logger.warning(
                "skip voiceprint enrollment capture because pending enrollment is missing fingerprint=%s prompt_session_id=%s",
                state.context.fingerprint,
                prompt_session_id,
            )
            return None

        await self._cancel_active_voiceprint_session(
            api_websocket=api_websocket,
            state=state,
            reason="voiceprint_round_restart",
        )

        capture_session_id = state.context.start_session(
            purpose="voiceprint_enrollment",
            enrollment_id=enrollment.enrollment_id,
        )
        state.voiceprint_capture_session_id = capture_session_id
        state.voiceprint_capture_audio_bytes = 0
        await api_websocket.send(
            self._build_voiceprint_session_start_event(
                state=state,
                session_id=capture_session_id,
                enrollment_id=enrollment.enrollment_id,
            ).model_dump_json()
        )
        logger.info(
            "started voiceprint enrollment capture fingerprint=%s prompt_session_id=%s session_id=%s enrollment_id=%s",
            state.context.fingerprint,
            prompt_session_id,
            capture_session_id,
            enrollment.enrollment_id,
        )

        if settings.recording_enabled:
            try:
                response = await state.terminal_rpc.call(
                    command="start_recording",
                    payload=build_recording_rpc_payload(),
                )
                if not self._is_successful_response(response):
                    logger.warning(
                        "voiceprint enrollment start_recording returned non-zero fingerprint=%s session_id=%s detail=%s",
                        state.context.fingerprint,
                        capture_session_id,
                        self._describe_response(response),
                    )
            except Exception:
                logger.warning(
                    "failed to refresh terminal recording for voiceprint enrollment fingerprint=%s session_id=%s",
                    state.context.fingerprint,
                    capture_session_id,
                    exc_info=True,
                )

        return capture_session_id

    async def _finish_voiceprint_enrollment_capture(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        capture_session_id: str,
    ) -> None:
        if state.voiceprint_capture_session_id != capture_session_id:
            return
        if state.context.active_session_id != capture_session_id:
            return
        if state.context.active_session_purpose != "voiceprint_enrollment":
            return

        enrollment = state.context.pending_voiceprint_enrollment
        enrollment_id = state.context.active_enrollment_id
        if enrollment is None or not enrollment_id:
            logger.warning(
                "skip finishing voiceprint enrollment capture because binding changed fingerprint=%s session_id=%s",
                state.context.fingerprint,
                capture_session_id,
            )
            state.context.clear_session()
            return

        audio_bytes = max(int(state.voiceprint_capture_audio_bytes or 0), 0)
        if audio_bytes <= 0:
            logger.warning(
                "cancel voiceprint enrollment capture because no audio was captured fingerprint=%s session_id=%s enrollment_id=%s",
                state.context.fingerprint,
                capture_session_id,
                enrollment_id,
            )
            await api_websocket.send(
                GatewayEvent(
                    type="session.cancel",
                    terminal_id=state.context.terminal_id or "",
                    session_id=capture_session_id,
                    seq=state.context.next_seq(),
                    payload={"reason": "voiceprint_enrollment_no_audio"},
                    ts=command_ts_now(),
                ).model_dump_json()
            )
            state.context.clear_session()
            return

        await api_websocket.send(
            GatewayEvent(
                type="audio.commit",
                terminal_id=state.context.terminal_id or "",
                session_id=capture_session_id,
                seq=state.context.next_seq(),
                payload={
                    "duration_ms": None,
                    "reason": "voiceprint_enrollment_window_elapsed",
                    "debug_transcript": enrollment.expected_phrase,
                    "session_purpose": "voiceprint_enrollment",
                    "enrollment_id": enrollment_id,
                },
                ts=command_ts_now(),
            ).model_dump_json()
        )
        logger.info(
            "auto committed voiceprint enrollment capture fingerprint=%s session_id=%s enrollment_id=%s audio_bytes=%s",
            state.context.fingerprint,
            capture_session_id,
            enrollment_id,
            audio_bytes,
        )
        state.context.clear_session()

    async def _cancel_voiceprint_round_task(self, state: GatewayRuntimeState, *, reason: str) -> None:
        task = state.voiceprint_round_task
        if task is None or task.done() or task is asyncio.current_task():
            return
        logger.info(
            "cancel voiceprint round task fingerprint=%s reason=%s",
            state.context.fingerprint,
            reason,
        )
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        state.voiceprint_round_task = None
        state.voiceprint_capture_session_id = None
        state.voiceprint_capture_audio_bytes = 0

    async def _cancel_active_voiceprint_session(
        self,
        *,
        api_websocket,
        state: GatewayRuntimeState,
        reason: str,
    ) -> None:
        session_id = str(state.context.active_session_id or "").strip()
        if not session_id or state.context.active_session_purpose != "voiceprint_enrollment":
            return
        logger.info(
            "cancel stale voiceprint enrollment session fingerprint=%s session_id=%s reason=%s",
            state.context.fingerprint,
            session_id,
            reason,
        )
        await api_websocket.send(
            GatewayEvent(
                type="session.cancel",
                terminal_id=state.context.terminal_id or "",
                session_id=session_id,
                seq=state.context.next_seq(),
                payload={"reason": reason},
                ts=command_ts_now(),
            ).model_dump_json()
        )
        state.context.clear_session()
        if state.voiceprint_capture_session_id == session_id:
            state.voiceprint_capture_session_id = None
            state.voiceprint_capture_audio_bytes = 0

    def _build_voiceprint_session_start_event(
        self,
        *,
        state: GatewayRuntimeState,
        session_id: str,
        enrollment_id: str,
    ) -> GatewayEvent:
        return GatewayEvent(
            type="session.start",
            terminal_id=state.context.terminal_id or "",
            session_id=session_id,
            seq=state.context.next_seq(),
            payload={
                "household_id": state.context.household_id,
                "room_id": state.context.room_id,
                "terminal_code": state.context.terminal_code,
                "sample_rate": settings.recording_sample_rate,
                "codec": "pcm_s16le",
                "channels": settings.recording_channels,
                "trace_id": None,
                "session_purpose": "voiceprint_enrollment",
                "enrollment_id": enrollment_id,
            },
            ts=command_ts_now(),
        )

    def _record_voiceprint_capture_audio(self, state: GatewayRuntimeState, event: GatewayEvent) -> None:
        if event.type != "audio.append":
            return
        if state.voiceprint_capture_session_id != event.session_id:
            return
        chunk_bytes = max(int(event.payload.get("chunk_bytes") or 0), 0)
        if chunk_bytes <= 0:
            return
        had_audio = state.voiceprint_capture_audio_bytes > 0
        state.voiceprint_capture_audio_bytes += chunk_bytes
        if not had_audio:
            logger.info(
                "received first voiceprint enrollment audio chunk fingerprint=%s session_id=%s chunk_bytes=%s",
                state.context.fingerprint,
                event.session_id,
                chunk_bytes,
            )

    async def _start_takeover_keepalive(self, state: GatewayRuntimeState) -> None:
        existing_task = state.takeover_keepalive_task
        if existing_task is not None and not existing_task.done():
            logger.debug("takeover keepalive already active fingerprint=%s", state.context.fingerprint)
            return

        response = await state.terminal_rpc.call(
            command="start_play",
            payload=_build_takeover_playback_payload(),
        )
        if not self._is_successful_response(response):
            raise RuntimeError(self._describe_response(response))

        await state.terminal_rpc.send_stream(tag="play", raw_bytes=_build_takeover_silence_chunk())
        state.takeover_keepalive_task = asyncio.create_task(self._run_takeover_keepalive(state))
        logger.info("started takeover keepalive fingerprint=%s", state.context.fingerprint)

    async def _run_takeover_keepalive(self, state: GatewayRuntimeState) -> None:
        silence_chunk = _build_takeover_silence_chunk()
        try:
            while True:
                await asyncio.sleep(_TAKEOVER_KEEPALIVE_INTERVAL_SECONDS)
                await state.terminal_rpc.send_stream(tag="play", raw_bytes=silence_chunk)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "takeover keepalive stream failed fingerprint=%s",
                state.context.fingerprint,
                exc_info=True,
            )
            raise
        finally:
            if state.takeover_keepalive_task is asyncio.current_task():
                state.takeover_keepalive_task = None

    async def _stop_takeover_keepalive(
        self,
        state: GatewayRuntimeState,
        *,
        reason: str,
        suppress_errors: bool,
    ) -> None:
        task = state.takeover_keepalive_task
        if task is None:
            return

        state.takeover_keepalive_task = None
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        try:
            await state.terminal_rpc.notify(command="stop_play")
        except Exception:
            if suppress_errors:
                logger.debug(
                    "skip stop_play for takeover keepalive fingerprint=%s reason=%s",
                    state.context.fingerprint,
                    reason,
                    exc_info=True,
                )
                return
            raise

        logger.info(
            "stopped takeover keepalive fingerprint=%s reason=%s",
            state.context.fingerprint,
            reason,
        )


def build_terminal_interrupted_json(*, context: TerminalBridgeContext, reason: object | None, ts: str) -> str | None:
    if not context.active_playback_id or not context.active_playback_session_id or not context.terminal_id:
        return None
    payload = {
        "type": "playback.interrupted",
        "terminal_id": context.terminal_id,
        "session_id": context.active_playback_session_id,
        "seq": context.next_seq(),
        "payload": {
            "playback_id": context.active_playback_id,
            "reason": None if reason is None else str(reason),
        },
        "ts": ts,
    }
    context.clear_playback()
    return json.dumps(payload, ensure_ascii=False)


def _parse_gateway_discovery_status(payload: dict[str, Any]) -> GatewayDiscoveryStatus:
    return GatewayDiscoveryStatus(
        claimed=bool(payload.get("claimed")),
        binding=_parse_voice_terminal_binding(payload.get("binding")),
    )


def _parse_voice_terminal_binding(payload: object) -> VoiceTerminalBinding | None:
    if not isinstance(payload, dict):
        return None

    household_id = str(payload.get("household_id") or "").strip()
    terminal_id = str(payload.get("terminal_id") or "").strip()
    terminal_name = str(payload.get("terminal_name") or "").strip()
    if not household_id or not terminal_id or not terminal_name:
        return None

    return VoiceTerminalBinding(
        household_id=household_id,
        terminal_id=terminal_id,
        room_id=_coerce_optional_text(payload.get("room_id")),
        terminal_name=terminal_name,
        voice_auto_takeover_enabled=bool(payload.get("voice_auto_takeover_enabled")),
        voice_takeover_prefixes=tuple(_coerce_text_list(payload.get("voice_takeover_prefixes")) or ["\u8bf7"]),
        pending_voiceprint_enrollment=_parse_pending_voiceprint_enrollment(payload.get("pending_voiceprint_enrollment")),
    )


def _parse_version_response(response: OpenXiaoAIResponse) -> str:
    data = response.data
    if isinstance(data, str) and data.strip():
        return data.strip()
    raise RuntimeError("open-xiaoai runtime version is missing")


def _parse_shell_stdout(response: OpenXiaoAIResponse) -> str:
    data = response.data
    if isinstance(data, dict):
        stdout = str(data.get("stdout") or "").strip()
        if stdout:
            return stdout
    raise RuntimeError("terminal shell output is missing")


def _parse_shell_stdout_safe(response: OpenXiaoAIResponse) -> str:
    data = response.data
    if isinstance(data, dict):
        return str(data.get("stdout") or "").strip()
    if isinstance(data, str):
        return data.strip()
    return ""


def _describe_shell_stderr(response: OpenXiaoAIResponse) -> str:
    data = response.data
    if isinstance(data, dict):
        return str(data.get("stderr") or "").strip()
    return ""


def _coerce_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_pending_voiceprint_enrollment(payload: object) -> PendingVoiceprintEnrollment | None:
    if not isinstance(payload, dict):
        return None
    enrollment_id = str(payload.get("enrollment_id") or "").strip()
    target_member_id = str(payload.get("target_member_id") or "").strip()
    if not enrollment_id or not target_member_id:
        return None
    return PendingVoiceprintEnrollment(
        enrollment_id=enrollment_id,
        target_member_id=target_member_id,
        expected_phrase=_coerce_optional_text(payload.get("expected_phrase")),
        sample_goal=max(1, int(payload.get("sample_goal") or 1)),
        sample_count=max(0, int(payload.get("sample_count") or 0)),
        expires_at=_coerce_optional_text(payload.get("expires_at")),
    )


def _coerce_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace("，", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text or text in normalized:
            continue
        normalized.append(text)
    return normalized


def _extract_remote_addr(websocket: Any) -> str | None:
    remote_address = getattr(websocket, "remote_address", None)
    if isinstance(remote_address, tuple) and remote_address:
        host = remote_address[0]
        return str(host).strip() or None
    if remote_address is not None:
        host = getattr(remote_address, "host", None)
        if host is not None:
            return str(host).strip() or None

    client = getattr(websocket, "client", None)
    if client is None:
        return None
    host = getattr(client, "host", None)
    if host is None:
        return None
    return str(host).strip() or None


def _can_hot_refresh_binding(context: TerminalBridgeContext, binding: VoiceTerminalBinding) -> bool:
    if context.household_id and context.household_id != binding.household_id:
        return False
    if context.terminal_id and context.terminal_id != binding.terminal_id:
        return False
    return True


def _collect_binding_refresh_changes(context: TerminalBridgeContext, binding: VoiceTerminalBinding) -> list[str]:
    changes: list[str] = []
    if context.room_id != binding.room_id:
        changes.append("room_id")
    if context.name != binding.terminal_name:
        changes.append("terminal_name")

    next_invocation_mode = "always_familyclaw" if binding.voice_auto_takeover_enabled else "native_first"
    if context.invocation_mode != next_invocation_mode:
        changes.append("invocation_mode")
    if tuple(context.takeover_prefixes) != tuple(binding.voice_takeover_prefixes or ("\u8bf7",)):
        changes.append("takeover_prefixes")
    if not _same_pending_voiceprint_enrollment(
        context.pending_voiceprint_enrollment,
        binding.pending_voiceprint_enrollment,
    ):
        changes.append("pending_voiceprint_enrollment")
    return changes


def _same_pending_voiceprint_enrollment(
    current: PendingVoiceprintEnrollment | None,
    next_value: PendingVoiceprintEnrollment | None,
) -> bool:
    if current is None or next_value is None:
        return current is None and next_value is None
    return (
        current.enrollment_id == next_value.enrollment_id
        and current.target_member_id == next_value.target_member_id
        and current.expected_phrase == next_value.expected_phrase
        and current.sample_goal == next_value.sample_goal
        and current.sample_count == next_value.sample_count
        and current.expires_at == next_value.expires_at
    )


def _is_takeover_abort_request(outgoing: TerminalRpcRequest) -> bool:
    return outgoing.command == "run_shell" and str(outgoing.payload or "").strip() == _TAKEOVER_ABORT_COMMAND


def _translation_released_active_playback(translation) -> bool:
    for event in translation.events:
        if event.type == "playback.interrupted":
            return True
        if event.type != "playback.receipt":
            continue
        status = str(event.payload.get("status") or "").strip().lower()
        if status in {"completed", "failed", "interrupted"}:
            return True
    return False


def _is_blocking_tts_request(outgoing: TerminalRpcRequest) -> bool:
    if outgoing.command != "run_shell":
        return False
    payload = str(outgoing.payload or "").strip()
    return "tts_play.sh" in payload and not payload.endswith("&")


def _should_fire_and_forget_terminal_request(outgoing: TerminalRpcRequest) -> bool:
    if outgoing.command != "run_shell":
        return False
    payload = str(outgoing.payload or "").strip()
    if payload.endswith("&") and "ubus call mibrain text_to_speech" in payload:
        return True
    return "nohup" in payload and "tts_play.sh" in payload and payload.endswith("&")


def _extract_final_instruction_transcript(raw_message: str) -> str | None:
    frame = parse_open_xiaoai_text_message(raw_message)
    if frame.Event is None or frame.Event.event != "instruction":
        return None
    data = frame.Event.data
    if not isinstance(data, dict):
        return None
    line = data.get("NewLine")
    if not isinstance(line, str) or not line.strip():
        return None
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(message, dict):
        return None
    header = message.get("header")
    payload = message.get("payload")
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return None
    if header.get("namespace") != "SpeechRecognizer" or header.get("name") != "RecognizeResult":
        return None
    if not bool(payload.get("is_final")):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    text = str(first.get("text") or "").strip()
    return text or None


def _is_kws_event_frame(frame) -> bool:
    return frame.Event is not None and frame.Event.event == "kws"


def _is_instruction_vad_begin_frame(frame) -> bool:
    payload = _extract_instruction_event_payload(frame)
    return bool(payload and payload.get("is_vad_begin"))


def _is_final_instruction_frame(frame) -> bool:
    payload = _extract_instruction_event_payload(frame)
    return bool(payload and payload.get("is_final"))


def _extract_instruction_event_payload(frame) -> dict[str, Any] | None:
    if frame.Event is None or frame.Event.event != "instruction":
        return None
    data = frame.Event.data
    if not isinstance(data, dict):
        return None
    line = data.get("NewLine")
    if not isinstance(line, str) or not line.strip():
        return None
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(message, dict):
        return None
    header = message.get("header")
    payload = message.get("payload")
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return None
    if header.get("namespace") != "SpeechRecognizer" or header.get("name") != "RecognizeResult":
        return None
    return payload


def _should_buffer_native_first_audio(state: GatewayRuntimeState) -> bool:
    return (
        state.context.invocation_mode == "native_first"
        and state.context.pending_voiceprint_enrollment is None
        and state.context.active_session_id is None
        and state.context.terminal_id is not None
    )


def _should_hold_native_first_audio_until_takeover(state: GatewayRuntimeState) -> bool:
    return _should_buffer_native_first_audio(state) and state.context.last_invocation_decision == "await_takeover_prefix"


def _buffer_native_first_audio_chunk(state: GatewayRuntimeState, raw_bytes: bytes) -> None:
    if not raw_bytes:
        return
    max_bytes = _get_native_first_audio_buffer_limit_bytes()
    if max_bytes <= 0:
        return
    state.native_first_audio_chunks.append(raw_bytes)
    state.native_first_audio_bytes += len(raw_bytes)
    while state.native_first_audio_chunks and state.native_first_audio_bytes > max_bytes:
        removed = state.native_first_audio_chunks.popleft()
        state.native_first_audio_bytes -= len(removed)
    if state.native_first_audio_bytes < 0:
        state.native_first_audio_bytes = 0


def _clear_native_first_audio_buffer(state: GatewayRuntimeState) -> None:
    state.native_first_audio_chunks.clear()
    state.native_first_audio_bytes = 0


def _inject_native_first_buffered_audio_events(
    state: GatewayRuntimeState,
    events: list[GatewayEvent],
) -> list[GatewayEvent]:
    if not events or not state.native_first_audio_chunks:
        return events

    commit_index = next((index for index, item in enumerate(events) if item.type == "audio.commit"), None)
    if commit_index is None:
        return events

    session_id = str(events[commit_index].session_id or "").strip()
    terminal_id = str(state.context.terminal_id or "").strip()
    if not session_id or not terminal_id:
        _clear_native_first_audio_buffer(state)
        return events

    buffered_events: list[GatewayEvent] = []
    for raw_bytes in state.native_first_audio_chunks:
        if not raw_bytes:
            continue
        buffered_events.append(
            GatewayEvent(
                type="audio.append",
                terminal_id=terminal_id,
                session_id=session_id,
                seq=state.context.next_seq(),
                payload={
                    "chunk_base64": base64.b64encode(raw_bytes).decode("ascii"),
                    "chunk_bytes": len(raw_bytes),
                    "codec": "pcm_s16le",
                    "sample_rate": settings.recording_sample_rate,
                },
                ts=command_ts_now(),
            )
        )

    _clear_native_first_audio_buffer(state)
    if not buffered_events:
        return events

    return events[:commit_index] + buffered_events + events[commit_index:]


def _get_native_first_audio_buffer_limit_bytes() -> int:
    bytes_per_sample = max(1, settings.recording_bits_per_sample // 8)
    bytes_per_second = settings.recording_sample_rate * settings.recording_channels * bytes_per_sample
    return max(0, int(bytes_per_second * _NATIVE_FIRST_AUDIO_BUFFER_SECONDS))


def _should_interrupt_local_playback(transcript: str) -> bool:
    normalized = _normalize_stop_phrase(transcript)
    return normalized in _LOCAL_PLAYBACK_STOP_PHRASES


def _has_pending_or_active_playback(state: GatewayRuntimeState) -> bool:
    return bool(state.context.active_playback_id or state.pending_playback_commands)


def _is_voiceprint_prompt_beep_command(command: GatewayCommand) -> bool:
    if command.type != "play.start":
        return False
    session_id = str(command.session_id or "").strip()
    if not session_id.startswith(_VOICEPRINT_PROMPT_SESSION_PREFIX):
        return False
    return str(command.payload.get("mode") or "").strip() == "audio_bytes"


def _is_stop_phrase_suppressed(state: GatewayRuntimeState, transcript: str) -> bool:
    deadline = state.suppressed_stop_phrase_deadline
    normalized = _normalize_stop_phrase(transcript)
    if not deadline or not normalized:
        return False
    if normalized != state.suppressed_stop_phrase:
        return False
    if asyncio.get_running_loop().time() >= deadline:
        state.suppressed_stop_phrase = None
        state.suppressed_stop_phrase_deadline = None
        return False
    return True


def _collect_playback_session_ids(state: GatewayRuntimeState) -> set[str]:
    session_ids: set[str] = set()
    active_session_id = str(state.context.active_playback_session_id or "").strip()
    if active_session_id:
        session_ids.add(active_session_id)
    for command in state.pending_playback_commands:
        queued_session_id = str(command.session_id or "").strip()
        if queued_session_id:
            session_ids.add(queued_session_id)
    return session_ids


def _is_same_playback(context: TerminalBridgeContext, playback_id: str | None, session_id: str | None) -> bool:
    return context.active_playback_id == playback_id and context.active_playback_session_id == session_id


def _get_voiceprint_current_round(enrollment: PendingVoiceprintEnrollment) -> int:
    sample_goal = max(int(enrollment.sample_goal or 1), 1)
    sample_count = max(int(enrollment.sample_count or 0), 0)
    return min(sample_goal, sample_count + 1)


def _get_voiceprint_prompt_beep_audio_base64() -> str:
    total_frames = int(_VOICEPRINT_PROMPT_BEEP_SAMPLE_RATE * _VOICEPRINT_PROMPT_BEEP_DURATION_SECONDS)
    frames = bytearray()
    for frame_index in range(total_frames):
        progress = frame_index / total_frames
        envelope = min(progress / 0.15, 1.0) * min((1.0 - progress) / 0.2, 1.0)
        sample_value = int(
            32767
            * _VOICEPRINT_PROMPT_BEEP_VOLUME
            * max(envelope, 0.0)
            * math.sin(2.0 * math.pi * _VOICEPRINT_PROMPT_BEEP_FREQUENCY_HZ * (frame_index / _VOICEPRINT_PROMPT_BEEP_SAMPLE_RATE))
        )
        frames.extend(struct.pack("<h", sample_value))
    return base64.b64encode(bytes(frames)).decode("ascii")


def _normalize_stop_phrase(transcript: str) -> str:
    return "".join(str(transcript).split())


def _build_takeover_playback_payload() -> dict[str, object]:
    return {
        "pcm": "noop",
        "channels": settings.playback_channels,
        "bits_per_sample": settings.playback_bits_per_sample,
        "sample_rate": settings.playback_sample_rate,
        "period_size": settings.playback_period_size,
        "buffer_size": settings.playback_buffer_size,
    }


def _build_takeover_silence_chunk() -> bytes:
    bytes_per_sample = max(1, settings.playback_bits_per_sample // 8)
    chunk_frames = max(1, int(settings.playback_sample_rate * _TAKEOVER_KEEPALIVE_CHUNK_MS / 1000))
    chunk_bytes = chunk_frames * settings.playback_channels * bytes_per_sample
    return b"\x00" * chunk_bytes


def _preview_payload(payload: object | None, *, max_length: int = 120) -> str:
    if payload is None:
        return "None"
    text = str(payload).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _estimate_tts_timeout_seconds(text: object | None) -> float:
    normalized = str(text or "").strip()
    if not normalized:
        return 20.0
    visible_length = len(normalized.replace(" ", ""))
    punctuation_count = sum(1 for char in normalized if char in "，。！？；,.!?;:")
    estimated_seconds = 8.0 + visible_length * 0.28 + punctuation_count * 0.5
    return min(180.0, max(20.0, estimated_seconds))


def command_ts_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()
