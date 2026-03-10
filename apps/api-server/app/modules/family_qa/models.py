from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class QaQueryLog(Base):
    __tablename__ = "qa_query_logs"
    __table_args__ = (
        Index("idx_qa_query_logs_household_created_at", "household_id", "created_at"),
        Index("idx_qa_query_logs_requester_member_id", "requester_member_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    requester_member_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    answer_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    facts_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
