from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "data" / "familyclaw.db"


class AiProviderRuntimeConfig(BaseModel):
    enabled: bool = True
    transport_type: str | None = None
    base_url: str | None = None
    api_version: str | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=120000)
    max_retry_count: int | None = Field(default=None, ge=0, le=5)
    allow_remote: bool | None = None
    secret_env_var: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AiRuntimeConfig(BaseModel):
    default_provider_code: str | None = None
    default_fallback_provider_codes: list[str] = Field(default_factory=list)
    default_timeout_ms: int = Field(default=15000, ge=100, le=120000)
    default_max_retry_count: int = Field(default=1, ge=0, le=5)
    default_routing_mode: str = "primary_then_fallback"
    default_allow_remote: bool = True
    local_preferred: bool = False
    secret_ref_prefix: str = "env://"
    provider_configs: dict[str, AiProviderRuntimeConfig] = Field(default_factory=dict)


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
    context_cache_enabled: bool = True
    auth_session_cookie_name: str = "familyclaw_session"
    auth_session_ttl_hours: int = 24 * 7
    auth_legacy_header_enabled: bool = True
    conversation_debug_log_enabled: bool = False
    conversation_lane_shadow_enabled: bool = False
    conversation_lane_takeover_enabled: bool = True
    conversation_proposal_shadow_enabled: bool = False
    conversation_proposal_write_enabled: bool = True
    plugin_job_worker_enabled: bool = True
    plugin_job_worker_poll_interval_seconds: float = 1.0
    plugin_job_default_max_attempts: int = 2
    plugin_job_default_retry_delay_seconds: int = 5
    plugin_job_default_timeout_seconds: int = 60
    plugin_job_running_stale_after_seconds: int = 120
    scheduler_worker_enabled: bool = True
    scheduler_worker_poll_interval_seconds: float = 1.0
    scheduler_worker_batch_size: int = 100
    scheduler_definition_failure_threshold: int = 3
    voice_gateway_token: str = "dev-voice-gateway-token"
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_household_username: str = "user"
    bootstrap_household_password: str = "user"
    ai_gateway_enabled: bool = True
    ai_default_provider_code: str | None = None
    ai_default_fallback_provider_codes: list[str] = Field(default_factory=list)
    ai_default_timeout_ms: int = 15000
    ai_default_max_retry_count: int = 1
    ai_default_routing_mode: str = "primary_then_fallback"
    ai_default_allow_remote: bool = True
    ai_local_preferred: bool = False
    ai_secret_ref_prefix: str = "env://"
    ai_provider_configs: dict[str, AiProviderRuntimeConfig] = Field(default_factory=dict)
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:4174",
            "http://127.0.0.1:4174",
        ]
    )
    cors_allow_origin_regex: str | None = Field(
        default=r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+):(?:4174|5174)",
    )

    model_config = SettingsConfigDict(
        env_prefix="FAMILYCLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def ai_runtime(self) -> AiRuntimeConfig:
        return AiRuntimeConfig(
            default_provider_code=self.ai_default_provider_code,
            default_fallback_provider_codes=self.ai_default_fallback_provider_codes,
            default_timeout_ms=self.ai_default_timeout_ms,
            default_max_retry_count=self.ai_default_max_retry_count,
            default_routing_mode=self.ai_default_routing_mode,
            default_allow_remote=self.ai_default_allow_remote,
            local_preferred=self.ai_local_preferred,
            secret_ref_prefix=self.ai_secret_ref_prefix,
            provider_configs=self.ai_provider_configs,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
