from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class MemberRelationship(Base):
    __tablename__ = "member_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_member_id",
            "target_member_id",
            "relation_type",
            name="uq_member_relationships_source_target_type",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    visibility_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    delegation_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)

