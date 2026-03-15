from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    listen_host: str = "0.0.0.0"
    listen_port: int = Field(default=9040, ge=1, le=65535)
    api_key: str | None = None
    log_level: str = "INFO"
    default_commit_transcript: str = "打开客厅灯"

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_VOICE_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
