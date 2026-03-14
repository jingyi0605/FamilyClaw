import asyncio
import json
import time
import unittest

from app.db.utils import new_uuid, utc_now_iso
from app.modules.ai_gateway.models import AiProviderProfile
from app.modules.ai_gateway.provider_runtime import ProviderAdapter, stream_provider_invoke


class ProviderRuntimeAsyncStreamTests(unittest.TestCase):
    @staticmethod
    def _build_provider_profile(port: int) -> AiProviderProfile:
        return AiProviderProfile(
            id=new_uuid(),
            provider_code="test-provider",
            display_name="Test Provider",
            transport_type="openai_compatible",
            api_family="openai_chat_completions",
            base_url=f"http://127.0.0.1:{port}",
            api_version="test-model",
            secret_ref=None,
            enabled=True,
            supported_capabilities_json="[]",
            privacy_level="local_only",
            latency_budget_ms=5000,
            cost_policy_json=None,
            extra_config_json=json.dumps({"allow_anonymous": True}),
            updated_at=utc_now_iso(),
        )

    def test_stream_provider_invoke_does_not_block_event_loop(self) -> None:
        async def _run_case() -> tuple[list[str], float, float]:
            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    await reader.readuntil(b"\r\n\r\n")
                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/event-stream\r\n"
                        b"Cache-Control: no-cache\r\n"
                        b"Connection: close\r\n\r\n"
                    )
                    await writer.drain()
                    await asyncio.sleep(0.08)
                    writer.write(("data: " + json.dumps({"choices": [{"delta": {"content": "你好"}}]}, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    await writer.drain()
                    await asyncio.sleep(0.08)
                    writer.write(b"data: [DONE]\n\n")
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            provider_profile = self._build_provider_profile(port)

            heartbeat_at = 0.0
            stream_done_at = 0.0
            chunks: list[str] = []

            async def _consume_stream() -> None:
                nonlocal stream_done_at
                async for chunk in stream_provider_invoke(
                    provider_profile=provider_profile,
                    payload={"messages": [{"role": "user", "content": "你好"}]},
                    timeout_ms=3000,
                ):
                    chunks.append(chunk)
                stream_done_at = time.perf_counter()

            async def _heartbeat() -> None:
                nonlocal heartbeat_at
                await asyncio.sleep(0.02)
                heartbeat_at = time.perf_counter()

            try:
                await asyncio.gather(_consume_stream(), _heartbeat())
            finally:
                server.close()
                await server.wait_closed()

            return chunks, heartbeat_at, stream_done_at

        chunks, heartbeat_at, stream_done_at = asyncio.run(_run_case())
        self.assertEqual(["你好"], chunks)
        self.assertGreater(heartbeat_at, 0)
        self.assertGreater(stream_done_at, 0)
        self.assertLess(heartbeat_at, stream_done_at)

    def test_async_invoke_does_not_block_event_loop(self) -> None:
        async def _run_case() -> tuple[str, float, float]:
            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    await reader.readuntil(b"\r\n\r\n")
                    body = json.dumps(
                        {
                            "model": "test-model",
                            "choices": [{"message": {"content": "普通异步回复"}, "finish_reason": "stop"}],
                        },
                        ensure_ascii=False,
                    ).encode("utf-8")
                    await asyncio.sleep(0.1)
                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/json\r\n"
                        + f"Content-Length: {len(body)}\r\n".encode("ascii")
                        + b"Connection: close\r\n\r\n"
                        + body
                    )
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            provider_profile = self._build_provider_profile(port)
            adapter = ProviderAdapter(transport_type="openai_compatible")
            heartbeat_at = 0.0
            invoke_done_at = 0.0
            text = ""

            async def _invoke() -> None:
                nonlocal text, invoke_done_at
                result = await adapter.ainvoke(
                    capability="qa_generation",
                    provider_profile=provider_profile,
                    payload={"question": "你好"},
                    timeout_ms=3000,
                )
                text = str(result.normalized_output.get("text") or "")
                invoke_done_at = time.perf_counter()

            async def _heartbeat() -> None:
                nonlocal heartbeat_at
                await asyncio.sleep(0.02)
                heartbeat_at = time.perf_counter()

            try:
                await asyncio.gather(_invoke(), _heartbeat())
            finally:
                server.close()
                await server.wait_closed()

            return text, heartbeat_at, invoke_done_at

        text, heartbeat_at, invoke_done_at = asyncio.run(_run_case())
        self.assertEqual("普通异步回复", text)
        self.assertGreater(heartbeat_at, 0)
        self.assertGreater(invoke_done_at, 0)
        self.assertLess(heartbeat_at, invoke_done_at)


if __name__ == "__main__":
    unittest.main()
