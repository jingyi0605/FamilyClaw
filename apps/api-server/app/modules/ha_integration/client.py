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

    def get_states(self) -> list[dict]:
        payload = self._request_json("/api/states")
        if not isinstance(payload, list):
            raise HomeAssistantClientError("unexpected response from home assistant states api")
        return payload

    def _request_json(self, path: str) -> dict | list:
        url = parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except OSError:
            return self._request_json_with_curl(url)
        except error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = exc.reason
            raise HomeAssistantClientError(
                f"home assistant request failed with status {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:
            try:
                return self._request_json_with_curl(url)
            except HomeAssistantClientError:
                raise HomeAssistantClientError(
                    f"home assistant connection failed: {exc.reason}"
                ) from exc

    def _request_json_with_curl(self, url: str) -> dict | list:
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
            url,
        ]
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
