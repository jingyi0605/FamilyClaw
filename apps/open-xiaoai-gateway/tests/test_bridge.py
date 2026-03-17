import asyncio
import contextlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from open_xiaoai_gateway.bridge import (
    GatewayDiscoveryStatus,
    GatewayRuntimeState,
    OpenXiaoAIGateway,
    _parse_gateway_discovery_status,
    _extract_remote_addr,
)
from open_xiaoai_gateway.protocol import GatewayCommand
from open_xiaoai_gateway.translator import (
    PendingVoiceprintEnrollment,
    TerminalBridgeContext,
    TerminalRpcRequest,
    VoiceTerminalBinding,
    build_discovery_info,
)


class GatewayBridgeTests(unittest.TestCase):
    def test_extract_remote_addr_from_tuple_remote_address(self) -> None:
        websocket = SimpleNamespace(remote_address=("192.168.1.22", 4399))

        self.assertEqual("192.168.1.22", _extract_remote_addr(websocket))

    def test_extract_remote_addr_from_host_object(self) -> None:
        websocket = SimpleNamespace(remote_address=SimpleNamespace(host="speaker.local"))

        self.assertEqual("speaker.local", _extract_remote_addr(websocket))

    def test_extract_remote_addr_falls_back_to_legacy_client(self) -> None:
        websocket = SimpleNamespace(client=SimpleNamespace(host="192.168.1.30"))

        self.assertEqual("192.168.1.30", _extract_remote_addr(websocket))

    def test_extract_remote_addr_returns_none_when_missing(self) -> None:
        websocket = SimpleNamespace()

        self.assertIsNone(_extract_remote_addr(websocket))

    def test_parse_gateway_discovery_status_reads_pending_voiceprint_enrollment(self) -> None:
        status = _parse_gateway_discovery_status(
            {
                "claimed": True,
                "binding": {
                    "household_id": "household-1",
                    "terminal_id": "terminal-1",
                    "room_id": "room-1",
                    "terminal_name": "客厅小爱",
                    "voice_auto_takeover_enabled": False,
                    "voice_takeover_prefixes": ["请"],
                    "pending_voiceprint_enrollment": {
                        "enrollment_id": "enrollment-1",
                        "target_member_id": "member-1",
                        "expected_phrase": "我是妈妈",
                        "sample_goal": 3,
                        "sample_count": 1,
                        "expires_at": "2026-03-16T12:00:00+08:00",
                    },
                },
            }
        )

        self.assertTrue(status.claimed)
        self.assertIsNotNone(status.binding)
        assert status.binding is not None
        self.assertIsNotNone(status.binding.pending_voiceprint_enrollment)
        assert status.binding.pending_voiceprint_enrollment is not None
        self.assertEqual("enrollment-1", status.binding.pending_voiceprint_enrollment.enrollment_id)


class _FakeTerminalWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str | bytes] = []
        self._queue: asyncio.Queue[str | bytes | None] = asyncio.Queue()

    async def send(self, message: str | bytes) -> None:
        self.sent_messages.append(message)
        assert isinstance(message, str)
        request = json.loads(message)["Request"]
        command = request["command"]
        request_id = request["id"]

        if command == "get_version":
            response_data: object = "1.0.0"
        elif request["payload"] == "echo $(micocfg_model)":
            response_data = {"stdout": "LX06\n", "stderr": "", "exit_code": 0}
        else:
            response_data = {"stdout": "SN001\n", "stderr": "", "exit_code": 0}

        await self._queue.put(
            json.dumps(
                {
                    "Response": {
                        "id": request_id,
                        "code": 0,
                        "msg": "ok",
                        "data": response_data,
                    }
                },
                ensure_ascii=False,
            )
        )
        if len(self.sent_messages) >= 3:
            await self._queue.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str | bytes:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


class GatewayBridgeAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_terminal_connection_discovers_terminal_while_reader_is_running(self) -> None:
        gateway = OpenXiaoAIGateway()
        websocket = _FakeTerminalWebSocket()

        with patch(
            "open_xiaoai_gateway.bridge.GatewayApiClient.report_discovery",
            return_value=GatewayDiscoveryStatus(claimed=False, binding=None),
        ), patch.object(
            OpenXiaoAIGateway,
            "_report_offline_discovery",
            new=AsyncMock(),
        ):
            await gateway._handle_terminal_connection(websocket)

        self.assertEqual(3, len(websocket.sent_messages))
        first_request = json.loads(websocket.sent_messages[0])["Request"]
        self.assertEqual("get_version", first_request["command"])

    async def test_refresh_active_binding_updates_takeover_strategy(self) -> None:
        gateway = OpenXiaoAIGateway()
        context = TerminalBridgeContext()
        context.apply_discovery(build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0"))
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
                voice_auto_takeover_enabled=False,
                voice_takeover_prefixes=("请",),
            )
        )
        api_reader_task = asyncio.create_task(asyncio.sleep(60))
        state = GatewayRuntimeState(
            context=context,
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
            api_websocket=SimpleNamespace(),
            api_reader_task=api_reader_task,
        )

        try:
            await gateway._refresh_active_binding(
                state,
                VoiceTerminalBinding(
                    household_id="household-1",
                    terminal_id="terminal-1",
                    room_id="room-1",
                    terminal_name="客厅小爱",
                    voice_auto_takeover_enabled=True,
                    voice_takeover_prefixes=("帮我",),
                ),
            )
        finally:
            api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await api_reader_task

        self.assertEqual("always_familyclaw", context.invocation_mode)
        self.assertEqual(("帮我",), context.takeover_prefixes)

    async def test_refresh_active_binding_ignores_identity_change(self) -> None:
        gateway = OpenXiaoAIGateway()
        context = TerminalBridgeContext()
        context.apply_discovery(build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0"))
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
                voice_auto_takeover_enabled=False,
                voice_takeover_prefixes=("请",),
            )
        )
        api_reader_task = asyncio.create_task(asyncio.sleep(60))
        state = GatewayRuntimeState(
            context=context,
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
            api_websocket=SimpleNamespace(),
            api_reader_task=api_reader_task,
        )

        try:
            await gateway._refresh_active_binding(
                state,
                VoiceTerminalBinding(
                    household_id="household-2",
                    terminal_id="terminal-2",
                    room_id="room-9",
                    terminal_name="书房小爱",
                    voice_auto_takeover_enabled=True,
                    voice_takeover_prefixes=("帮我",),
                ),
            )
        finally:
            api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await api_reader_task

        self.assertEqual("household-1", context.household_id)
        self.assertEqual("terminal-1", context.terminal_id)
        self.assertEqual("native_first", context.invocation_mode)
        self.assertEqual(("请",), context.takeover_prefixes)

    async def test_refresh_active_binding_updates_pending_voiceprint_enrollment(self) -> None:
        gateway = OpenXiaoAIGateway()
        context = TerminalBridgeContext()
        context.apply_discovery(build_discovery_info(model="LX06", sn="SN001", runtime_version="1.0.0"))
        context.apply_binding(
            VoiceTerminalBinding(
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                terminal_name="客厅小爱",
                voice_auto_takeover_enabled=False,
                voice_takeover_prefixes=("请",),
            )
        )
        api_reader_task = asyncio.create_task(asyncio.sleep(60))
        state = GatewayRuntimeState(
            context=context,
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
            api_websocket=SimpleNamespace(),
            api_reader_task=api_reader_task,
        )

        try:
            await gateway._refresh_active_binding(
                state,
                VoiceTerminalBinding(
                    household_id="household-1",
                    terminal_id="terminal-1",
                    room_id="room-1",
                    terminal_name="客厅小爱",
                    voice_auto_takeover_enabled=False,
                    voice_takeover_prefixes=("请",),
                    pending_voiceprint_enrollment=PendingVoiceprintEnrollment(
                        enrollment_id="enrollment-1",
                        target_member_id="member-1",
                        expected_phrase="我是妈妈",
                        sample_goal=3,
                        sample_count=1,
                        expires_at="2026-03-16T12:00:00+08:00",
                    ),
                ),
            )
        finally:
            api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await api_reader_task

        self.assertIsNotNone(context.pending_voiceprint_enrollment)
        assert context.pending_voiceprint_enrollment is not None
        self.assertEqual("enrollment-1", context.pending_voiceprint_enrollment.enrollment_id)

    async def test_dispatch_local_terminal_messages_interrupts_native_xiaoai_for_takeover(self) -> None:
        gateway = OpenXiaoAIGateway()
        terminal_rpc = SimpleNamespace(
            notify=AsyncMock(),
            call=AsyncMock(),
            send_stream=AsyncMock(),
        )
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
            ),
            terminal_rpc=terminal_rpc,
            remote_addr="192.168.1.22",
        )

        with patch.object(OpenXiaoAIGateway, "_interrupt_native_xiaoai", new=AsyncMock()) as interrupt_native:
            await gateway._dispatch_local_terminal_messages(
                state=state,
                terminal_rpc=terminal_rpc,
                outgoing_messages=[
                    TerminalRpcRequest(
                        command="run_shell",
                        payload="/etc/init.d/mico_aivs_lab restart >/dev/null 2>&1",
                    )
                ],
            )

        interrupt_native.assert_awaited_once_with(state)
        terminal_rpc.call.assert_not_called()
        terminal_rpc.notify.assert_not_called()

    async def test_dispatch_terminal_messages_calls_shell_for_xiaoai_tts(self) -> None:
        gateway = OpenXiaoAIGateway()
        terminal_rpc = SimpleNamespace(
            notify=AsyncMock(),
            call=AsyncMock(return_value=SimpleNamespace(code=0, msg="ok", data={"stdout": "", "stderr": "", "exit_code": 0})),
            send_stream=AsyncMock(),
        )
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
            ),
            terminal_rpc=terminal_rpc,
            remote_addr="192.168.1.22",
        )
        command = SimpleNamespace(
            type="play.start",
            payload={"playback_id": "playback-1", "reason": None, "text": "你好"},
            ts="2026-03-15T00:00:00+08:00",
        )
        state.context.track_playback(playback_id="playback-1", session_id="session-1")

        with patch.object(OpenXiaoAIGateway, "_wait_terminal_playback_idle", new=AsyncMock()):
            await gateway._dispatch_terminal_messages(
                api_websocket=api_websocket,
                state=state,
                command=command,
                outgoing_messages=[
                    TerminalRpcRequest(
                        command="run_shell",
                        payload="/usr/sbin/tts_play.sh '你好' >/tmp/familyclaw-tts.log 2>&1",
                    )
                ],
            )

        terminal_rpc.notify.assert_not_called()
        self.assertGreaterEqual(terminal_rpc.call.await_count, 1)
        self.assertGreaterEqual(api_websocket.send.await_count, 2)
        self.assertIsNone(state.context.active_playback_id)

    async def test_handle_terminal_message_skips_forwarding_when_local_takeover_fails(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
            ),
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
            api_websocket=api_websocket,
            api_reader_task=asyncio.create_task(asyncio.sleep(60)),
        )

        translation = SimpleNamespace(
            terminal_messages=[
                SimpleNamespace(
                    command="run_shell",
                    payload="/etc/init.d/mico_aivs_lab restart >/dev/null 2>&1",
                )
            ],
            events=[SimpleNamespace(model_dump_json=lambda: '{"type":"audio.commit"}')],
        )
        raw_message = json.dumps(
            {
                "Event": {
                    "id": "event-1",
                    "event": "instruction",
                    "data": {"NewLine": "{}"},
                }
            },
            ensure_ascii=False,
        )

        try:
            state.context.last_invocation_decision = "familyclaw_takeover"
            with patch("open_xiaoai_gateway.bridge.translate_text_message_result", return_value=translation), patch.object(
                OpenXiaoAIGateway,
                "_dispatch_local_terminal_messages",
                new=AsyncMock(side_effect=TimeoutError()),
            ):
                await gateway._handle_terminal_message(message=raw_message, state=state)
        finally:
            state.api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.api_reader_task

        api_websocket.send.assert_not_called()
        self.assertEqual("native_passthrough", state.context.last_invocation_decision)
        self.assertEqual("takeover_pause_failed", state.context.last_passthrough_reason)

    async def test_handle_play_start_command_queues_when_playback_is_active(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
                active_playback_id="playback-active",
                active_playback_session_id="session-1",
            ),
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
        )
        command = GatewayCommand.model_validate(
            {
                "type": "play.start",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 4,
                "payload": {
                    "playback_id": "playback-queued",
                    "mode": "tts_text",
                    "text": "第二句",
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch.object(OpenXiaoAIGateway, "_ensure_playback_worker") as ensure_worker_mock:
            await gateway._handle_play_start_command(
                api_websocket=api_websocket,
                state=state,
                command=command,
            )

        ensure_worker_mock.assert_called_once()
        self.assertEqual(1, len(state.pending_playback_commands))
        self.assertEqual("playback-queued", state.pending_playback_commands[0].payload["playback_id"])

    async def test_dispatch_next_pending_playback_wakes_worker_after_current_finishes(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
            ),
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
        )
        state.pending_playback_commands.append(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 5,
                    "payload": {
                        "playback_id": "playback-next",
                        "mode": "tts_text",
                        "text": "下一段",
                    },
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )
        )

        with patch.object(OpenXiaoAIGateway, "_ensure_playback_worker") as ensure_worker_mock:
            await gateway._dispatch_next_pending_playback(
                api_websocket=api_websocket,
                state=state,
                reason="terminal_playback_released",
            )

        ensure_worker_mock.assert_called_once()
        self.assertTrue(state.playback_queue_event.is_set())

    async def test_dispatch_blocking_tts_request_releases_queue(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="客厅小爱",
            ),
            terminal_rpc=SimpleNamespace(
                call=AsyncMock(return_value=SimpleNamespace(code=0, msg="ok", data={"stdout": "", "stderr": "", "exit_code": 0})),
            ),
            remote_addr="192.168.1.22",
        )
        state.context.track_playback(playback_id="playback-1", session_id="session-1")
        state.pending_playback_commands.append(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 6,
                    "payload": {
                        "playback_id": "playback-2",
                        "mode": "tts_text",
                        "text": "下一句",
                    },
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )
        )

        with patch.object(OpenXiaoAIGateway, "_wait_terminal_playback_idle", new=AsyncMock()):
            await gateway._dispatch_blocking_tts_request(
                api_websocket=api_websocket,
                state=state,
                command=GatewayCommand.model_validate(
                    {
                        "type": "play.start",
                        "terminal_id": "terminal-1",
                        "session_id": "session-1",
                        "seq": 5,
                        "payload": {
                            "playback_id": "playback-1",
                            "mode": "tts_text",
                            "text": "第一句",
                        },
                        "ts": "2026-03-15T00:00:00+08:00",
                    }
                ),
                outgoing=TerminalRpcRequest(
                    command="run_shell",
                    payload="/usr/sbin/tts_play.sh '第一句' >/tmp/familyclaw-tts.log 2>&1",
                ),
            )

        self.assertGreaterEqual(api_websocket.send.await_count, 2)
        self.assertIsNone(state.context.active_playback_id)

    async def test_handle_terminal_message_interrupts_local_playback_on_stop_phrase(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        terminal_rpc = SimpleNamespace(
            call=AsyncMock(return_value=SimpleNamespace(code=0, msg="ok", data={"stdout": "", "stderr": "", "exit_code": 0})),
        )
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="瀹㈠巺灏忕埍",
                active_playback_id="playback-1",
                active_playback_session_id="session-1",
            ),
            terminal_rpc=terminal_rpc,
            remote_addr="192.168.1.22",
            api_websocket=api_websocket,
            api_reader_task=asyncio.create_task(asyncio.sleep(60)),
        )
        state.pending_playback_commands.append(
            GatewayCommand.model_validate(
                {
                    "type": "play.start",
                    "terminal_id": "terminal-1",
                    "session_id": "session-1",
                    "seq": 5,
                    "payload": {
                        "playback_id": "playback-queued",
                        "mode": "tts_text",
                        "text": "涓嬩竴鍙?",
                    },
                    "ts": "2026-03-15T00:00:00+08:00",
                }
            )
        )

        try:
            await gateway._handle_terminal_message(
                message=json.dumps(
                    {
                        "Event": {
                            "id": "event-stop-1",
                            "event": "instruction",
                            "data": {
                                "NewLine": json.dumps(
                                    {
                                        "header": {
                                            "namespace": "SpeechRecognizer",
                                            "name": "RecognizeResult",
                                        },
                                        "payload": {
                                            "is_final": True,
                                            "is_vad_begin": False,
                                            "results": [{"text": "停止"}],
                                        },
                                    },
                                    ensure_ascii=False,
                                )
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                state=state,
            )
        finally:
            state.api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.api_reader_task

        self.assertEqual(2, terminal_rpc.call.await_count)
        first_call = terminal_rpc.call.await_args_list[0].kwargs
        second_call = terminal_rpc.call.await_args_list[1].kwargs
        self.assertEqual("run_shell", first_call["command"])
        self.assertEqual("run_shell", second_call["command"])
        self.assertEqual(0, len(state.pending_playback_commands))
        self.assertIn("session-1", state.interrupted_playback_session_ids)
        self.assertIsNone(state.context.active_playback_id)
        sent_payload = json.loads(api_websocket.send.await_args.args[0])
        self.assertEqual("playback.interrupted", sent_payload["type"])
        self.assertEqual("停止", sent_payload["payload"]["reason"])

    async def test_handle_terminal_message_preempts_native_on_vad_begin_during_local_playback(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        terminal_rpc = SimpleNamespace(
            call=AsyncMock(return_value=SimpleNamespace(code=0, msg="ok", data={"stdout": "", "stderr": "", "exit_code": 0})),
        )
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="瀹㈠巺灏忕埍",
                active_playback_id="playback-1",
                active_playback_session_id="session-1",
            ),
            terminal_rpc=terminal_rpc,
            remote_addr="192.168.1.22",
            api_websocket=api_websocket,
            api_reader_task=asyncio.create_task(asyncio.sleep(60)),
        )

        try:
            await gateway._handle_terminal_message(
                message=json.dumps(
                    {
                        "Event": {
                            "id": "event-vad-1",
                            "event": "instruction",
                            "data": {
                                "NewLine": json.dumps(
                                    {
                                        "header": {
                                            "namespace": "SpeechRecognizer",
                                            "name": "RecognizeResult",
                                        },
                                        "payload": {
                                            "is_final": False,
                                            "is_vad_begin": True,
                                            "results": [{"text": ""}],
                                        },
                                    },
                                    ensure_ascii=False,
                                )
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                state=state,
            )
        finally:
            state.api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.api_reader_task

        self.assertEqual(2, terminal_rpc.call.await_count)
        self.assertTrue(state.native_barge_in_active)
        self.assertIsNone(state.context.active_playback_id)
        sent_payload = json.loads(api_websocket.send.await_args.args[0])
        self.assertEqual("playback.interrupted", sent_payload["type"])

    async def test_handle_terminal_message_suppresses_final_stop_phrase_after_barge_in(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        terminal_rpc = SimpleNamespace(call=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="瀹㈠巺灏忕埍",
            ),
            terminal_rpc=terminal_rpc,
            remote_addr="192.168.1.22",
            api_websocket=api_websocket,
            api_reader_task=asyncio.create_task(asyncio.sleep(60)),
            native_barge_in_active=True,
        )

        try:
            await gateway._handle_terminal_message(
                message=json.dumps(
                    {
                        "Event": {
                            "id": "event-stop-final-1",
                            "event": "instruction",
                            "data": {
                                "NewLine": json.dumps(
                                    {
                                        "header": {
                                            "namespace": "SpeechRecognizer",
                                            "name": "RecognizeResult",
                                        },
                                        "payload": {
                                            "is_final": True,
                                            "is_vad_begin": False,
                                            "results": [{"text": "停止"}],
                                        },
                                    },
                                    ensure_ascii=False,
                                )
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                state=state,
            )
        finally:
            state.api_reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.api_reader_task

        terminal_rpc.call.assert_not_called()
        api_websocket.send.assert_not_called()
        self.assertFalse(state.native_barge_in_active)

    async def test_handle_play_start_command_drops_interrupted_session(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="瀹㈠巺灏忕埍",
            ),
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
        )
        state.interrupted_playback_session_ids.add("session-1")
        command = GatewayCommand.model_validate(
            {
                "type": "play.start",
                "terminal_id": "terminal-1",
                "session_id": "session-1",
                "seq": 4,
                "payload": {
                    "playback_id": "playback-dropped",
                    "mode": "tts_text",
                    "text": "涓嶅簲鎾斁",
                },
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )

        with patch.object(OpenXiaoAIGateway, "_ensure_playback_worker") as ensure_worker_mock:
            await gateway._handle_play_start_command(
                api_websocket=api_websocket,
                state=state,
                command=command,
            )

        ensure_worker_mock.assert_not_called()
        self.assertEqual(0, len(state.pending_playback_commands))

    async def test_dispatch_api_command_stops_takeover_keepalive_before_speaker_turn_on(self) -> None:
        gateway = OpenXiaoAIGateway()
        api_websocket = SimpleNamespace(send=AsyncMock())
        state = GatewayRuntimeState(
            context=TerminalBridgeContext(
                fingerprint="open_xiaoai:LX06:SN001",
                household_id="household-1",
                terminal_id="terminal-1",
                room_id="room-1",
                name="鐎广垹宸虹亸蹇曞煃",
            ),
            terminal_rpc=SimpleNamespace(),
            remote_addr="192.168.1.22",
        )
        command = GatewayCommand.model_validate(
            {
                "type": "speaker.turn_on",
                "terminal_id": "terminal-1",
                "session_id": "device-control-terminal-1",
                "seq": 6,
                "payload": {"reason": "device_control"},
                "ts": "2026-03-15T00:00:00+08:00",
            }
        )
        outgoing_messages = [TerminalRpcRequest(command="run_shell", payload="mphelper play")]

        with patch(
            "open_xiaoai_gateway.bridge.translate_command_to_terminal",
            return_value=outgoing_messages,
        ), patch.object(
            OpenXiaoAIGateway,
            "_stop_takeover_keepalive",
            new=AsyncMock(),
        ) as stop_keepalive, patch.object(
            OpenXiaoAIGateway,
            "_dispatch_terminal_messages",
            new=AsyncMock(),
        ) as dispatch_terminal_messages:
            await gateway._dispatch_api_command(
                api_websocket=api_websocket,
                state=state,
                command=command,
            )

        stop_keepalive.assert_awaited_once()
        dispatch_terminal_messages.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
