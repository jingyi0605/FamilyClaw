from __future__ import annotations

import asyncio
import contextlib
import logging
from urllib.parse import urlencode

import websockets

from open_xiaoai_gateway.protocol import GatewayCommand, GatewayEvent
from open_xiaoai_gateway.settings import settings
from open_xiaoai_gateway.translator import (
    TerminalBridgeContext,
    build_terminal_offline_event,
    translate_audio_chunk,
    translate_command_to_terminal,
    translate_text_message,
)

logger = logging.getLogger(__name__)


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
        api_websocket = None
        api_reader_task: asyncio.Task[None] | None = None

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    events = translate_audio_chunk(message, context)
                else:
                    events = translate_text_message(message, context)

                if not events:
                    continue

                if api_websocket is None:
                    api_websocket = await self._connect_api(context)
                    api_reader_task = asyncio.create_task(self._forward_api_commands(api_websocket, websocket))

                for event in events:
                    await api_websocket.send(event.model_dump_json())
        finally:
            offline_event = build_terminal_offline_event(context)
            if offline_event is not None and api_websocket is not None:
                try:
                    await api_websocket.send(offline_event.model_dump_json())
                except Exception:
                    logger.exception("上报 terminal.offline 失败 terminal_id=%s", context.terminal_id)
            if api_reader_task is not None:
                api_reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await api_reader_task
            if api_websocket is not None:
                await api_websocket.close()

    async def _connect_api(self, context: TerminalBridgeContext):
        if not context.household_id or not context.terminal_id:
            raise RuntimeError("终端尚未完成识别，无法连接 api-server")

        query = urlencode({"household_id": context.household_id, "terminal_id": context.terminal_id})
        ws_url = f"{settings.api_server_ws_url}?{query}"
        logger.info("连接 api-server realtime.voice terminal_id=%s", context.terminal_id)
        return await websockets.connect(
            ws_url,
            additional_headers={"x-voice-gateway-token": settings.voice_gateway_token},
            max_size=None,
        )

    async def _forward_api_commands(self, api_websocket, terminal_websocket) -> None:
        async for raw_message in api_websocket:
            command = GatewayCommand.model_validate_json(raw_message)
            terminal_message = translate_command_to_terminal(command)
            await terminal_websocket.send(terminal_message)
