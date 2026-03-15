from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
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
            await self._websocket.send(build_rpc_request_message(request_id=request_id, command=command, payload=payload))
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        finally:
            self._pending.pop(request_id, None)

    async def send_stream(self, *, tag: str, raw_bytes: bytes, data: object | None = None) -> None:
        await self._websocket.send(build_stream_message(stream_id=str(uuid4()), tag=tag, raw_bytes=raw_bytes, data=data))

    def resolve(self, response: OpenXiaoAIResponse) -> bool:
        future = self._pending.get(response.id)
        if future is None or future.done():
            return False
        future.set_result(response)
        return True


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
        remote_addr = websocket.client.host if websocket.client else None
        terminal_rpc = TerminalRpcClient(websocket)
        context = TerminalBridgeContext()
        state = GatewayRuntimeState(
            context=context,
            terminal_rpc=terminal_rpc,
            remote_addr=remote_addr,
        )
        api_client = GatewayApiClient()
        claim_poll_task: asyncio.Task[Any] | None = None

        try:
            discovery = await self._discover_terminal(terminal_rpc)
            context.apply_discovery(discovery)
            initial_status = await asyncio.to_thread(
                api_client.report_discovery,
                build_discovery_report_payload(context, remote_addr=remote_addr, connection_status="online"),
            )
            if initial_status.claimed and initial_status.binding is not None:
                await self._activate_terminal(state, initial_status.binding)
            if not state.is_active():
                claim_poll_task = asyncio.create_task(self._poll_until_claimed(state, api_client))

            async for message in websocket:
                if isinstance(message, bytes):
                    if not state.is_active():
                        continue
                    events = translate_audio_chunk(message, context)
                    for event in events:
                        await state.api_websocket.send(event.model_dump_json())
                    continue

                frame = parse_open_xiaoai_text_message(message)
                if frame.Response is not None:
                    terminal_rpc.resolve(frame.Response)
                    continue
                if frame.Request is not None:
                    logger.warning("ignore unexpected client request command=%s", frame.Request.command)
                    continue
                if not state.is_active():
                    continue

                translation = translate_text_message_result(message, context)
                if translation.terminal_messages:
                    try:
                        await self._dispatch_local_terminal_messages(
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

                for event in translation.events:
                    await state.api_websocket.send(event.model_dump_json())
        finally:
            if claim_poll_task is not None:
                claim_poll_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await claim_poll_task

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
            if state.api_websocket is not None:
                await state.api_websocket.close()

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

    async def _poll_until_claimed(self, state: GatewayRuntimeState, api_client: GatewayApiClient) -> None:
        refresh_tick = 0
        while not state.is_active():
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
                await self._activate_terminal(state, status.binding)

    async def _activate_terminal(self, state: GatewayRuntimeState, binding: VoiceTerminalBinding) -> None:
        async with state.activation_lock:
            if state.is_active():
                return
            state.context.apply_binding(binding)
            api_websocket = await self._connect_api(state.context)
            api_reader_task = asyncio.create_task(
                self._forward_api_commands(api_websocket, state.terminal_rpc, state.context),
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
                "claimed terminal activated fingerprint=%s household_id=%s terminal_id=%s",
                state.context.fingerprint,
                state.context.household_id,
                state.context.terminal_id,
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

    async def _forward_api_commands(self, api_websocket, terminal_rpc: TerminalRpcClient, context: TerminalBridgeContext) -> None:
        async for raw_message in api_websocket:
            command = GatewayCommand.model_validate_json(raw_message)
            outgoing_messages = translate_command_to_terminal(command, context)
            if not outgoing_messages:
                continue

            try:
                await self._dispatch_terminal_messages(
                    api_websocket=api_websocket,
                    terminal_rpc=terminal_rpc,
                    context=context,
                    command=command,
                    outgoing_messages=outgoing_messages,
                )
            except Exception:
                logger.exception("failed to dispatch command type=%s", command.type)
                failed_event = build_playback_failed_event(
                    context,
                    detail="gateway dispatch failed",
                    error_code="playback_failed",
                )
                if failed_event is not None:
                    await api_websocket.send(failed_event.model_dump_json())

    async def _dispatch_terminal_messages(
        self,
        *,
        api_websocket,
        terminal_rpc: TerminalRpcClient,
        context: TerminalBridgeContext,
        command: GatewayCommand,
        outgoing_messages: list[TerminalRpcRequest | TerminalBinaryStream],
    ) -> None:
        last_response: OpenXiaoAIResponse | None = None

        for outgoing in outgoing_messages:
            if isinstance(outgoing, TerminalRpcRequest):
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

    async def _dispatch_local_terminal_messages(
        self,
        *,
        terminal_rpc: TerminalRpcClient,
        outgoing_messages: list[TerminalRpcRequest | TerminalBinaryStream],
    ) -> None:
        for outgoing in outgoing_messages:
            if isinstance(outgoing, TerminalRpcRequest):
                response = await terminal_rpc.call(command=outgoing.command, payload=outgoing.payload)
                if not self._is_successful_response(response):
                    raise RuntimeError(self._describe_response(response))
                continue
            await terminal_rpc.send_stream(tag=outgoing.tag, raw_bytes=outgoing.raw_bytes, data=outgoing.data)

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


def _coerce_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
