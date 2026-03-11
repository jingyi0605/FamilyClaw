from __future__ import annotations

import json
import subprocess
from urllib import error, parse, request

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
