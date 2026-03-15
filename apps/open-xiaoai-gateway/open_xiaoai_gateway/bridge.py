from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from uuid import uuid4
from urllib.parse import urlencode

import websockets

from open_xiaoai_gateway.protocol import GatewayCommand, OpenXiaoAIResponse
from open_xiaoai_gateway.settings import settings
from open_xiaoai_gateway.translator import (
    TerminalBinaryStream,
    TerminalBridgeContext,
    TerminalRpcRequest,
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
    translate_text_message,
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
        context = TerminalBridgeContext()
        terminal_rpc = TerminalRpcClient(websocket)
        api_websocket = await self._connect_api(context)
        api_reader_task = asyncio.create_task(self._forward_api_commands(api_websocket, terminal_rpc, context))

        try:
            await api_websocket.send(build_terminal_online_event(context).model_dump_json())
            if settings.recording_enabled:
                response = await terminal_rpc.call(command="start_recording", payload=build_recording_rpc_payload())
                if not self._is_successful_response(response):
                    logger.warning("start_recording failed: %s", self._describe_response(response))

            async for message in websocket:
                if isinstance(message, bytes):
                    events = translate_audio_chunk(message, context)
                    for event in events:
                        await api_websocket.send(event.model_dump_json())
                    continue

                frame = parse_open_xiaoai_text_message(message)
                if frame.Response is not None:
                    terminal_rpc.resolve(frame.Response)
                    continue
                if frame.Request is not None:
                    logger.warning("ignore unexpected client request command=%s", frame.Request.command)
                    continue

                events = translate_text_message(message, context)
                for event in events:
                    await api_websocket.send(event.model_dump_json())
        finally:
            offline_event = build_terminal_offline_event(context)
            if offline_event is not None:
                try:
                    await api_websocket.send(offline_event.model_dump_json())
                except Exception:
                    logger.exception("failed to report terminal.offline terminal_id=%s", context.terminal_id)
            api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await api_reader_task
            await api_websocket.close()

    async def _connect_api(self, context: TerminalBridgeContext):
        query = urlencode({"household_id": context.household_id, "terminal_id": context.terminal_id})
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
            if context.active_playback_id and context.active_playback_session_id:
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
            interrupted_event = build_terminal_interrupted_json(context=context, reason=command.payload.get("reason"), ts=command.ts)
            if interrupted_event is not None:
                await api_websocket.send(interrupted_event)
            return

        _ = last_response

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
    if not context.active_playback_id or not context.active_playback_session_id:
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
