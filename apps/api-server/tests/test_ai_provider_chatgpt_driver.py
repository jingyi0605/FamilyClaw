import asyncio
import json
import unittest

from app.db.utils import new_uuid, utc_now_iso
from app.modules.ai_gateway.models import AiProviderProfile
from app.plugins.builtin.ai_provider_chatgpt.driver import _prepare_request, build_driver


async def _read_http_request(reader: asyncio.StreamReader) -> tuple[str, bytes]:
    head = await reader.readuntil(b"\r\n\r\n")
    lines = head.decode("utf-8", errors="ignore").split("\r\n")
    request_line = lines[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.lower()] = value.strip()
    content_length = int(headers.get("content-length", "0") or "0")
    body = await reader.readexactly(content_length) if content_length else b""
    path = request_line.split(" ")[1]
    return path, body


async def _write_json_response(
    writer: asyncio.StreamWriter,
    *,
    status_line: bytes,
    payload: dict[str, object],
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    writer.write(
        status_line
        + b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: close\r\n\r\n"
        + body
    )
    await writer.drain()


class ChatGptDriverTests(unittest.TestCase):
    @staticmethod
    def _build_profile(
        *,
        base_url: str,
        model_name: str = "gpt-5.4",
        extra_config: dict[str, object] | None = None,
    ) -> AiProviderProfile:
        values = {"adapter_code": "chatgpt", "model_name": model_name, "allow_anonymous": True}
        if extra_config:
            values.update(extra_config)
        return AiProviderProfile(
            id=new_uuid(),
            provider_code="family-chatgpt-main",
            display_name="ChatGPT Main",
            transport_type="openai_compatible",
            api_family="openai_chat_completions",
            base_url=base_url,
            api_version=model_name,
            secret_ref=None,
            enabled=True,
            supported_capabilities_json='["text"]',
            privacy_level="public_cloud",
            latency_budget_ms=15000,
            cost_policy_json="{}",
            extra_config_json=json.dumps(values, ensure_ascii=False),
            updated_at=utc_now_iso(),
        )

    def test_prepare_request_auto_completes_v1_and_both_endpoints(self) -> None:
        profile = self._build_profile(base_url="https://gmncodex.com")

        prepared = _prepare_request(profile, "text", {"question": "hello"})
        prepared_extra_config = json.loads(prepared.provider_profile.extra_config_json or "{}")

        self.assertEqual("https://gmncodex.com/v1", prepared.provider_profile.base_url)
        self.assertEqual("https://gmncodex.com/v1/chat/completions", prepared_extra_config["chat_completions_url"])
        self.assertEqual("https://gmncodex.com/v1/responses", prepared_extra_config["responses_url"])
        self.assertEqual("auto", prepared.protocol_mode)

    def test_driver_auto_uses_responses_with_root_base_url(self) -> None:
        async def _run_case() -> tuple[list[str], str]:
            requested_paths: list[str] = []

            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    path, body = await _read_http_request(reader)
                    requested_paths.append(path)
                    request_payload = json.loads(body.decode("utf-8"))
                    self.assertEqual("/v1/responses", path)
                    self.assertEqual("gpt-5.4", request_payload["model"])
                    await _write_json_response(
                        writer,
                        status_line=b"HTTP/1.1 200 OK\r\n",
                        payload={
                            "model": "gpt-5.4",
                            "status": "completed",
                            "output": [
                                {
                                    "content": [
                                        {"type": "output_text", "text": "responses reply"},
                                    ]
                                }
                            ],
                        },
                    )
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            driver = build_driver()
            profile = self._build_profile(base_url=f"http://127.0.0.1:{port}")

            try:
                result = await driver.ainvoke(
                    capability="text",
                    provider_profile=profile,
                    payload={"question": "hello"},
                    timeout_ms=3000,
                )
            finally:
                server.close()
                await server.wait_closed()
            return requested_paths, str(result.normalized_output.get("text") or "")

        requested_paths, text = asyncio.run(_run_case())
        self.assertEqual(["/v1/responses"], requested_paths)
        self.assertEqual("responses reply", text)

    def test_driver_auto_falls_back_to_chat_completions_when_responses_is_missing(self) -> None:
        async def _run_case() -> tuple[list[str], str]:
            requested_paths: list[str] = []

            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    path, _body = await _read_http_request(reader)
                    requested_paths.append(path)
                    if path == "/v1/responses":
                        await _write_json_response(
                            writer,
                            status_line=b"HTTP/1.1 404 Not Found\r\n",
                            payload={"error": "responses route not found"},
                        )
                        return
                    await _write_json_response(
                        writer,
                        status_line=b"HTTP/1.1 200 OK\r\n",
                        payload={
                            "model": "gpt-4o-mini",
                            "choices": [
                                {
                                    "message": {"content": "legacy reply"},
                                    "finish_reason": "stop",
                                }
                            ],
                        },
                    )
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            driver = build_driver()
            profile = self._build_profile(base_url=f"http://127.0.0.1:{port}", model_name="gpt-4o-mini")

            try:
                result = await driver.ainvoke(
                    capability="text",
                    provider_profile=profile,
                    payload={"question": "hello"},
                    timeout_ms=3000,
                )
            finally:
                server.close()
                await server.wait_closed()
            return requested_paths, str(result.normalized_output.get("text") or "")

        requested_paths, text = asyncio.run(_run_case())
        self.assertEqual(["/v1/responses", "/v1/chat/completions"], requested_paths)
        self.assertEqual("legacy reply", text)

    def test_driver_stream_reads_responses_sse(self) -> None:
        async def _run_case() -> list[str]:
            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    path, _body = await _read_http_request(reader)
                    self.assertEqual("/v1/responses", path)
                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/event-stream\r\n"
                        b"Cache-Control: no-cache\r\n"
                        b"Connection: close\r\n\r\n"
                    )
                    await writer.drain()
                    writer.write(
                        (
                            "event: response.output_text.delta\n"
                            + f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': 'hello '})}\n\n"
                            + "event: response.output_text.delta\n"
                            + f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': 'world'})}\n\n"
                        ).encode("utf-8")
                    )
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            driver = build_driver()
            profile = self._build_profile(base_url=f"http://127.0.0.1:{port}")

            chunks: list[str] = []
            try:
                async for chunk in driver.stream(
                    provider_profile=profile,
                    payload={"question": "hello"},
                    timeout_ms=3000,
                ):
                    chunks.append(chunk)
            finally:
                server.close()
                await server.wait_closed()
            return chunks

        self.assertEqual(["hello ", "world"], asyncio.run(_run_case()))

    def test_driver_stream_falls_back_to_chat_completions_when_responses_is_missing(self) -> None:
        async def _run_case() -> tuple[list[str], list[str]]:
            requested_paths: list[str] = []

            async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                try:
                    path, _body = await _read_http_request(reader)
                    requested_paths.append(path)
                    if path == "/v1/responses":
                        await _write_json_response(
                            writer,
                            status_line=b"HTTP/1.1 404 Not Found\r\n",
                            payload={"error": "responses route not found"},
                        )
                        return

                    writer.write(
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: text/event-stream\r\n"
                        b"Cache-Control: no-cache\r\n"
                        b"Connection: close\r\n\r\n"
                    )
                    await writer.drain()
                    writer.write(
                        (
                            "data: "
                            + json.dumps({"choices": [{"delta": {"content": "legacy "}}]})
                            + "\n\n"
                            + "data: "
                            + json.dumps({"choices": [{"delta": {"content": "stream"}}]})
                            + "\n\n"
                            + "data: [DONE]\n\n"
                        ).encode("utf-8")
                    )
                    await writer.drain()
                finally:
                    writer.close()
                    await writer.wait_closed()

            server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            driver = build_driver()
            profile = self._build_profile(base_url=f"http://127.0.0.1:{port}", model_name="gpt-4o-mini")

            chunks: list[str] = []
            try:
                async for chunk in driver.stream(
                    provider_profile=profile,
                    payload={"question": "hello"},
                    timeout_ms=3000,
                ):
                    chunks.append(chunk)
            finally:
                server.close()
                await server.wait_closed()
            return requested_paths, chunks

        requested_paths, chunks = asyncio.run(_run_case())
        self.assertEqual(["/v1/responses", "/v1/chat/completions"], requested_paths)
        self.assertEqual(["legacy ", "stream"], chunks)


if __name__ == "__main__":
    unittest.main()
