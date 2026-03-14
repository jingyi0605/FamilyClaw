from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    listen_host: str = "0.0.0.0"
    listen_port: int = Field(default=4399, ge=1, le=65535)
    api_server_ws_url: str = "ws://127.0.0.1:8000/api/v1/realtime/voice"
    voice_gateway_token: str = "dev-voice-gateway-token"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_OPEN_XIAOAI_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
