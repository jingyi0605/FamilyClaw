from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class AiProviderProfile(Base):
    __tablename__ = "ai_provider_profiles"
    __table_args__ = (
        Index("uq_ai_provider_profiles_provider_code", "provider_code", unique=True),
        Index("idx_ai_provider_profiles_enabled", "enabled"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(30), nullable=False)
    api_family: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supported_capabilities_json: Mapped[str] = mapped_column(Text, nullable=False)
    privacy_level: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_budget_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class AiCapabilityRoute(Base):
    __tablename__ = "ai_capability_routes"
    __table_args__ = (
        Index("idx_ai_capability_routes_capability", "capability"),
        Index("idx_ai_capability_routes_household_id", "household_id"),
        Index(
            "uq_ai_capability_routes_global_capability",
            "capability",
            unique=True,
            sqlite_where=text("household_id IS NULL"),
        ),
        Index(
            "uq_ai_capability_routes_household_capability",
            "household_id",
            "capability",
            unique=True,
            sqlite_where=text("household_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    household_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=True,
    )
    primary_provider_profile_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("ai_provider_profiles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fallback_provider_profile_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    routing_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allow_remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prompt_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class AiModelCallLog(Base):
    __tablename__ = "ai_model_call_logs"
    __table_args__ = (
        Index("idx_ai_model_call_logs_trace_id", "trace_id"),
        Index("idx_ai_model_call_logs_household_created_at", "household_id", "created_at"),
        Index("idx_ai_model_call_logs_capability_created_at", "capability", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    household_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="SET NULL"),
        nullable=True,
    )
    requester_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    input_policy: Mapped[str] = mapped_column(String(50), nullable=False)
    masked_fields_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
