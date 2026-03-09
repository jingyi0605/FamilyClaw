from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "data" / "familyclaw.db"


class Settings(BaseSettings):
    app_name: str = "FamilyClaw API Server"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DB_PATH.as_posix()}",
    )
    home_assistant_base_url: str | None = None
    home_assistant_token: str | None = None
    home_assistant_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
