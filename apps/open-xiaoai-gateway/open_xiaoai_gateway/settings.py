from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_OPEN_XIAOAI_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
