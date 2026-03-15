from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    listen_host: str = "0.0.0.0"
    listen_port: int = Field(default=9040, ge=1, le=65535)
    api_key: str | None = None
    log_level: str = "INFO"
    default_commit_transcript: str = "\u6253\u5f00\u5ba2\u5385\u706f"
    artifacts_root: Path = BASE_DIR / "data" / "artifacts"

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_VOICE_RUNTIME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

