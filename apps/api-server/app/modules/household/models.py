from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class Household(Base):
    __tablename__ = "households"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coordinate_precision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coordinate_updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    setup_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=utc_now_iso,
        onupdate=utc_now_iso,
    )

