from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class RegionNode(Base):
    __tablename__ = "region_nodes"
    __table_args__ = (
        UniqueConstraint("provider_code", "region_code", name="uq_region_nodes_provider_region_code"),
        Index("idx_region_nodes_provider_parent", "provider_code", "parent_region_code"),
        Index("idx_region_nodes_provider_level", "provider_code", "admin_level"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    country_code: Mapped[str] = mapped_column(String(16), nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_region_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    admin_level: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    path_codes: Mapped[str] = mapped_column(Text, nullable=False)
    path_names: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_precision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coordinate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coordinate_updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)


class HouseholdRegionBinding(Base):
    __tablename__ = "household_regions"
    __table_args__ = (
        Index("idx_household_regions_provider_region", "provider_code", "region_code"),
    )

    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    country_code: Mapped[str] = mapped_column(String(16), nullable=False)
    region_code: Mapped[str] = mapped_column(String(32), nullable=False)
    admin_level: Mapped[str] = mapped_column(String(16), nullable=False)
    province_code: Mapped[str] = mapped_column(String(32), nullable=False)
    province_name: Mapped[str] = mapped_column(String(100), nullable=False)
    city_code: Mapped[str] = mapped_column(String(32), nullable=False)
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_code: Mapped[str] = mapped_column(String(32), nullable=False)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)
