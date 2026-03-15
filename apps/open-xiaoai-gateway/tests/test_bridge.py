import asyncio
import json
import unittest

from open_xiaoai_gateway.bridge import OpenXiaoAIGateway, TerminalRpcClient, extract_remote_addr


class ExtractRemoteAddrTests(unittest.TestCase):
    def test_extract_remote_addr_from_legacy_client(self) -> None:
        websocket = type(
            "LegacyWebSocket",
            (),
            {"client": type("Client", (), {"host": "192.168.1.10"})()},
        )()

        self.assertEqual("192.168.1.10", extract_remote_addr(websocket))

    def test_extract_remote_addr_from_remote_address_tuple(self) -> None:
        websocket = type(
            "NewWebSocket",
            (),
            {"remote_address": ("192.168.1.11", 54321)},
        )()

        self.assertEqual("192.168.1.11", extract_remote_addr(websocket))

    def test_extract_remote_addr_returns_none_when_missing(self) -> None:
        websocket = object()

        self.assertIsNone(extract_remote_addr(websocket))


class TerminalPumpTests(unittest.IsolatedAsyncioTestCase):
    async def test_pump_resolves_response_and_queues_event(self) -> None:
        websocket = _FakePumpWebSocket(
            [
                json.dumps(
                    {
                        "Response": {
                            "id": "req-1",
                            "code": 0,
                            "msg": "success",
                            "data": "1.0.0",
                        }
                    }
                ),
                json.dumps(
                    {
                        "Event": {
                            "id": "evt-1",
                            "event": "kws",
                            "data": {"Keyword": "小爱同学"},
                        }
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        rpc_client = TerminalRpcClient(websocket)
        queue: asyncio.Queue[str | bytes | None] = asyncio.Queue()
        gateway = OpenXiaoAIGateway()

        future = asyncio.get_running_loop().create_future()
        rpc_client._pending["req-1"] = future

        await gateway._pump_terminal_messages(websocket, rpc_client, queue)

        response = await future
        self.assertEqual("1.0.0", response.data)
        queued_message = await queue.get()
        self.assertIn('"event": "kws"', queued_message)
        self.assertIsNone(await queue.get())


class _FakePumpWebSocket:
    def __init__(self, messages: list[str | bytes]) -> None:
        self._messages = list(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


if __name__ == "__main__":
    unittest.main()
