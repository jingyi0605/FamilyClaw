from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

GatewayInvocationMode = Literal["always_familyclaw", "native_first"]


class Settings(BaseSettings):
    listen_host: str = "0.0.0.0"
    listen_port: int = Field(default=4399, ge=1, le=65535)
    api_server_http_url: str = "http://127.0.0.1:8000/api/v1"
    api_server_ws_url: str = "ws://127.0.0.1:8000/api/v1/realtime/voice"
    voice_gateway_token: str = "dev-voice-gateway-token"
    claim_poll_interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    recording_enabled: bool = True
    recording_pcm: str = "noop"
    recording_channels: int = Field(default=1, ge=1, le=2)
    recording_bits_per_sample: int = Field(default=16, ge=8, le=32)
    recording_sample_rate: int = Field(default=16000, ge=8000, le=96000)
    recording_period_size: int = Field(default=360, ge=1)
    recording_buffer_size: int = Field(default=1440, ge=1)
    playback_sample_rate: int = Field(default=24000, ge=8000, le=96000)
    playback_channels: int = Field(default=1, ge=1, le=2)
    playback_bits_per_sample: int = Field(default=16, ge=8, le=32)
    playback_period_size: int = Field(default=360, ge=1)
    playback_buffer_size: int = Field(default=1440, ge=1)
    invocation_mode: GatewayInvocationMode = "always_familyclaw"
    takeover_prefixes: list[str] = Field(default_factory=list)
    strip_takeover_prefix: bool = True
    pause_on_takeover: bool = True
    log_level: str = "INFO"

    @field_validator("takeover_prefixes", mode="before")
    @classmethod
    def normalize_takeover_prefixes(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw_items = value.split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raise ValueError("takeover_prefixes 必须是字符串或字符串数组")

        normalized: list[str] = []
        for item in raw_items:
            text = str(item).strip()
            if not text or text in normalized:
                continue
            normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def validate_invocation_config(self) -> "Settings":
        if self.invocation_mode == "native_first" and not self.takeover_prefixes:
            raise ValueError("native_first 模式必须至少配置一个 takeover_prefixes")
        return self

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_OPEN_XIAOAI_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
