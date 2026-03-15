from __future__ import annotations

import asyncio
from collections import deque
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import websockets

from open_xiaoai_gateway.protocol import GatewayCommand, OpenXiaoAIResponse
from open_xiaoai_gateway.settings import settings
from open_xiaoai_gateway.translator import (
    TerminalBinaryStream,
    TerminalBridgeContext,
    TerminalDiscoveryInfo,
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
        response = self._request("POST", "/devices/voice-terminals/discoveries/report", payload)
        return _parse_gateway_discovery_status(response)

    def get_binding(self, fingerprint: str) -> GatewayDiscoveryStatus:
        response = self._request(
            "GET",
            f"/devices/voice-terminals/discoveries/{quote(fingerprint, safe='')}/binding",
            None,
        )
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
                    except Exception:
                        logger.exception("failed to report terminal.offline terminal_id=%s", context.terminal_id)
            if state.api_reader_task is not None:
                state.api_reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
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
            events = translate_audio_chunk(message, context)
            for event in events:
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
                    logger.info(
                        "skip takeover forwarding because local pause failed fingerprint=%s",
                        context.fingerprint,
                    )
                    return

        for event in translation.events:
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
        refresh_tick = 0
        while True:
            await asyncio.sleep(settings.claim_poll_interval_seconds)
            if not state.context.fingerprint:
                continue
            refresh_tick += 1
            try:
                if refresh_tick % 3 == 0:
                    status = await asyncio.to_thread(
                        api_client.report_discovery,
                        build_discovery_report_payload(
                            state.context,
                            remote_addr=state.remote_addr,
                            connection_status="online",
                        ),
                    )
                else:
                    status = await asyncio.to_thread(api_client.get_binding, state.context.fingerprint)
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

    async def _refresh_active_binding(self, state: GatewayRuntimeState, binding: VoiceTerminalBinding) -> None:
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

            state.context.apply_binding(binding)
            logger.info(
                "refreshed active terminal binding fingerprint=%s changes=%s invocation_mode=%s takeover_prefixes=%s",
                state.context.fingerprint,
                ",".join(changes),
                state.context.invocation_mode,
                ",".join(state.context.takeover_prefixes),
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

    async def _forward_api_commands(self, api_websocket, state: GatewayRuntimeState) -> None:
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
            except Exception:
                logger.exception("failed to dispatch command type=%s", command.type)
                failed_event = build_playback_failed_event(
                    state.context,
                    detail="gateway dispatch failed",
                    error_code="playback_failed",
                )
                if failed_event is not None:
                    await api_websocket.send(failed_event.model_dump_json())
                if command.type == "play.start":
                    await self._dispatch_next_pending_playback(api_websocket=api_websocket, state=state, reason="play_start_dispatch_failed")

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
                except Exception:
                    logger.exception("failed to dispatch queued play.start playback_id=%s", command.payload.get("playback_id"))
                    failed_event = build_playback_failed_event(
                        state.context,
                        detail="gateway dispatch failed",
                        error_code="playback_failed",
                    )
                    if failed_event is not None:
                        await api_websocket.send(failed_event.model_dump_json())
        except asyncio.CancelledError:
            raise
        finally:
            if state.playback_worker_task is asyncio.current_task():
                state.playback_worker_task = None

    async def _dispatch_api_command(self, *, api_websocket, state: GatewayRuntimeState, command: GatewayCommand) -> None:
        outgoing_messages = translate_command_to_terminal(command, state.context)
        if not outgoing_messages:
            return

        if command.type in {"play.start", "play.stop", "play.abort"}:
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
                        await api_websocket.send(failed_event.model_dump_json())
                    return
                continue

            await terminal_rpc.send_stream(tag=outgoing.tag, raw_bytes=outgoing.raw_bytes, data=outgoing.data)

        if command.type == "play.start":
            started_event = build_playback_started_event(context)
            if started_event is not None:
                await api_websocket.send(started_event.model_dump_json())
            return

        if command.type == "play.stop":
            if context.active_playback_id and context.active_playback_session_id and context.terminal_id:
                await api_websocket.send(
                    json.dumps(
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
                    )
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
                await api_websocket.send(interrupted_event)
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
            await api_websocket.send(started_event.model_dump_json())

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
                await api_websocket.send(failed_event.model_dump_json())
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
            await api_websocket.send(completed_event)

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
    binding_payload = payload.get("binding")
    binding = None
    if isinstance(binding_payload, dict):
        binding = VoiceTerminalBinding(
            household_id=str(binding_payload.get("household_id") or "").strip(),
            terminal_id=str(binding_payload.get("terminal_id") or "").strip(),
            room_id=_coerce_optional_text(binding_payload.get("room_id")),
            terminal_name=str(binding_payload.get("terminal_name") or "").strip(),
            voice_auto_takeover_enabled=bool(binding_payload.get("voice_auto_takeover_enabled")),
            voice_takeover_prefixes=tuple(_coerce_text_list(binding_payload.get("voice_takeover_prefixes")) or ["请"]),
        )
    return GatewayDiscoveryStatus(
        claimed=bool(payload.get("claimed")),
        binding=binding,
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
    if tuple(context.takeover_prefixes) != tuple(binding.voice_takeover_prefixes or ("请",)):
        changes.append("takeover_prefixes")
    return changes


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


def _should_interrupt_local_playback(transcript: str) -> bool:
    normalized = _normalize_stop_phrase(transcript)
    return normalized in _LOCAL_PLAYBACK_STOP_PHRASES


def _has_pending_or_active_playback(state: GatewayRuntimeState) -> bool:
    return bool(state.context.active_playback_id or state.pending_playback_commands)


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
