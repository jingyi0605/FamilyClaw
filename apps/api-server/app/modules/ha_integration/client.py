from __future__ import annotations

import json
import subprocess
from urllib import error, parse, request

import httpx
import websockets

from app.core.config import settings


class HomeAssistantClientError(Exception):
    pass


class HomeAssistantClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.home_assistant_base_url or "").rstrip("/")
        self.token = token or settings.home_assistant_token
        self.timeout_seconds = timeout_seconds or settings.home_assistant_timeout_seconds

        if not self.base_url:
            raise HomeAssistantClientError("home assistant base url is not configured")
        if not self.token:
            raise HomeAssistantClientError("home assistant token is not configured")

    def get_base_url(self) -> str:
        return self.base_url

    def get_states(self) -> list[dict]:
        payload = self._request_json("/api/states", method="GET")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant states api")
        return payload

    def get_device_registry(self) -> list[dict]:
        payload = self._request_ws_command("config/device_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant device registry api")
        return payload

    def get_entity_registry(self) -> list[dict]:
        payload = self._request_ws_command("config/entity_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant entity registry api")
        return payload

    def get_area_registry(self) -> list[dict]:
        payload = self._request_ws_command("config/area_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant area registry api")
        return payload

    def call_service(
        self,
        *,
        domain: str,
        service: str,
        data: dict | None = None,
    ) -> dict | list:
        if not domain.strip():
            raise HomeAssistantClientError("home assistant service domain is required")
        if not service.strip():
            raise HomeAssistantClientError("home assistant service name is required")
        return self._request_json(
            f"/api/services/{domain}/{service}",
            method="POST",
            body=data or {},
        )

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        body: dict | None = None,
    ) -> dict | list:
        url = parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            data=payload,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            if isinstance(exc, error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8")
                except Exception:
                    detail = exc.reason
                raise HomeAssistantClientError(
                    f"home assistant request failed with status {exc.code}: {detail}"
                ) from exc

            if isinstance(exc, error.URLError):
                try:
                    return self._request_json_with_curl(url, method=method, body=body)
                except HomeAssistantClientError:
                    raise HomeAssistantClientError(
                        f"home assistant connection failed: {exc.reason}"
                    ) from exc

            raise

    def _request_json_with_curl(
        self,
        url: str,
        *,
        method: str,
        body: dict | None = None,
    ) -> dict | list:
        command = [
            "curl",
            "--noproxy",
            "*",
            "--silent",
            "--show-error",
            "--fail",
            "--max-time",
            str(int(self.timeout_seconds)),
            "-H",
            f"Authorization: Bearer {self.token}",
            "-H",
            "Content-Type: application/json",
            "-X",
            method,
            url,
        ]
        if body is not None:
            command.extend(["--data", json.dumps(body, ensure_ascii=False)])
        try:
            output = subprocess.check_output(command, text=True)
        except subprocess.CalledProcessError as exc:
            raise HomeAssistantClientError(
                f"home assistant curl request failed with exit code {exc.returncode}: {exc.output}"
            ) from exc

        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise HomeAssistantClientError(
                "home assistant returned invalid json"
            ) from exc

    def _request_ws_command(self, command_type: str) -> dict | list:
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise HomeAssistantClientError(
                "websockets package is required for home assistant registry sync"
            ) from exc

        ws_url = self._build_websocket_url()
        try:
            with connect(ws_url, open_timeout=self.timeout_seconds, close_timeout=self.timeout_seconds) as websocket:
                auth_required = self._recv_ws_json(websocket)
                if auth_required.get("type") != "auth_required":
                    raise HomeAssistantClientError("unexpected websocket auth handshake from home assistant")

                websocket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "access_token": self.token,
                        }
                    )
                )
                auth_result = self._recv_ws_json(websocket)
                if auth_result.get("type") != "auth_ok":
                    raise HomeAssistantClientError("home assistant websocket authentication failed")

                websocket.send(json.dumps({"id": 1, "type": command_type}))
                response = self._recv_ws_json(websocket)
        except Exception as exc:
            raise HomeAssistantClientError(
                f"home assistant websocket request failed: {exc}"
            ) from exc

        if response.get("type") != "result":
            raise HomeAssistantClientError("unexpected websocket response from home assistant")
        if not response.get("success"):
            raise HomeAssistantClientError(
                f"home assistant websocket command failed: {response.get('error')}"
            )
        return response.get("result")

    def _build_websocket_url(self) -> str:
        parsed = parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise HomeAssistantClientError("home assistant base url must start with http or https")
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        websocket_path = parsed.path.rstrip("/") + "/api/websocket"
        return parse.urlunparse(
            (
                ws_scheme,
                parsed.netloc,
                websocket_path,
                "",
                "",
                "",
            )
        )

    def _recv_ws_json(self, websocket) -> dict:
        payload = json.loads(websocket.recv())
        if not isinstance(payload, dict):
            raise HomeAssistantClientError("unexpected websocket payload from home assistant")
        return payload


class AsyncHomeAssistantClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.home_assistant_base_url or "").rstrip("/")
        self.token = token or settings.home_assistant_token
        self.timeout_seconds = timeout_seconds or settings.home_assistant_timeout_seconds

        if not self.base_url:
            raise HomeAssistantClientError("home assistant base url is not configured")
        if not self.token:
            raise HomeAssistantClientError("home assistant token is not configured")

    def get_base_url(self) -> str:
        return self.base_url

    async def get_states(self) -> list[dict]:
        payload = await self._request_json("/api/states", method="GET")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant states api")
        return payload

    async def get_device_registry(self) -> list[dict]:
        payload = await self._request_ws_command("config/device_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant device registry api")
        return payload

    async def get_entity_registry(self) -> list[dict]:
        payload = await self._request_ws_command("config/entity_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant entity registry api")
        return payload

    async def get_area_registry(self) -> list[dict]:
        payload = await self._request_ws_command("config/area_registry/list")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant area registry api")
        return payload

    async def call_service(
        self,
        *,
        domain: str,
        service: str,
        data: dict | None = None,
    ) -> dict | list:
        if not domain.strip():
            raise HomeAssistantClientError("home assistant service domain is required")
        if not service.strip():
            raise HomeAssistantClientError("home assistant service name is required")
        return await self._request_json(
            f"/api/services/{domain}/{service}",
            method="POST",
            body=data or {},
        )

    async def _request_json(
        self,
        path: str,
        *,
        method: str,
        body: dict | None = None,
    ) -> dict | list:
        url = parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HomeAssistantClientError(
                f"home assistant request failed with status {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise HomeAssistantClientError(f"home assistant connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise HomeAssistantClientError("home assistant returned invalid json") from exc

    async def _request_ws_command(self, command_type: str) -> dict | list:
        ws_url = self._build_websocket_url()
        try:
            async with websockets.connect(ws_url, open_timeout=self.timeout_seconds, close_timeout=self.timeout_seconds) as websocket:
                auth_required = await self._recv_ws_json(websocket)
                if auth_required.get("type") != "auth_required":
                    raise HomeAssistantClientError("unexpected websocket auth handshake from home assistant")

                await websocket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "access_token": self.token,
                        }
                    )
                )
                auth_result = await self._recv_ws_json(websocket)
                if auth_result.get("type") != "auth_ok":
                    raise HomeAssistantClientError("home assistant websocket authentication failed")

                await websocket.send(json.dumps({"id": 1, "type": command_type}))
                response = await self._recv_ws_json(websocket)
        except Exception as exc:
            raise HomeAssistantClientError(f"home assistant websocket request failed: {exc}") from exc

        if response.get("type") != "result":
            raise HomeAssistantClientError("unexpected websocket response from home assistant")
        if not response.get("success"):
            raise HomeAssistantClientError(
                f"home assistant websocket command failed: {response.get('error')}"
            )
        return response.get("result")

    def _build_websocket_url(self) -> str:
        parsed = parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise HomeAssistantClientError("home assistant base url must start with http or https")
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        websocket_path = parsed.path.rstrip("/") + "/api/websocket"
        return parse.urlunparse((ws_scheme, parsed.netloc, websocket_path, "", "", ""))

    async def _recv_ws_json(self, websocket) -> dict:
        payload = json.loads(await websocket.recv())
        if not isinstance(payload, dict):
            raise HomeAssistantClientError("unexpected websocket payload from home assistant")
        return payload
