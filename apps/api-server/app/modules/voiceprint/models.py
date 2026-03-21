from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.utils import utc_now_iso


class VoiceprintEnrollment(Base):
    __tablename__ = "voiceprint_enrollments"
    __table_args__ = (
        CheckConstraint("sample_goal > 0", name="ck_voiceprint_enrollments_sample_goal_positive"),
        CheckConstraint("sample_count >= 0", name="ck_voiceprint_enrollments_sample_count_non_negative"),
        Index("idx_voiceprint_enrollments_household_id", "household_id"),
        Index("idx_voiceprint_enrollments_member_id", "member_id"),
        Index("idx_voiceprint_enrollments_terminal_id", "terminal_id"),
        Index("idx_voiceprint_enrollments_status", "status"),
        Index("idx_voiceprint_enrollments_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    terminal_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    base_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class MemberVoiceprintProfile(Base):
    __tablename__ = "member_voiceprint_profiles"
    __table_args__ = (
        CheckConstraint("sample_count >= 0", name="ck_member_voiceprint_profiles_sample_count_non_negative"),
        CheckConstraint("version > 0", name="ck_member_voiceprint_profiles_version_positive"),
        UniqueConstraint(
            "household_id",
            "member_id",
            "version",
            name="uq_member_voiceprint_profiles_household_member_version",
        ),
        Index("idx_member_voiceprint_profiles_household_id", "household_id"),
        Index("idx_member_voiceprint_profiles_member_id", "member_id"),
        Index("idx_member_voiceprint_profiles_status", "status"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="sherpa_onnx_wespeaker_resnet34")
    provider_profile_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso, onupdate=utc_now_iso)


class MemberVoiceprintSample(Base):
    __tablename__ = "member_voiceprint_samples"
    __table_args__ = (
        CheckConstraint("sample_rate > 0", name="ck_member_voiceprint_samples_sample_rate_positive"),
        CheckConstraint("channels > 0", name="ck_member_voiceprint_samples_channels_positive"),
        CheckConstraint("sample_width > 0", name="ck_member_voiceprint_samples_sample_width_positive"),
        CheckConstraint("duration_ms > 0", name="ck_member_voiceprint_samples_duration_positive"),
        Index("idx_member_voiceprint_samples_profile_id", "profile_id"),
        Index("idx_member_voiceprint_samples_enrollment_id", "enrollment_id"),
        Index("idx_member_voiceprint_samples_household_id", "household_id"),
        Index("idx_member_voiceprint_samples_member_id", "member_id"),
        Index("idx_member_voiceprint_samples_terminal_id", "terminal_id"),
        Index("idx_member_voiceprint_samples_status", "status"),
        Index("idx_member_voiceprint_samples_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    profile_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("member_voiceprint_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("voiceprint_enrollments.id", ondelete="SET NULL"),
        nullable=True,
    )
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
    )
    terminal_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_width: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="accepted")
    created_at: Mapped[str] = mapped_column(Text, nullable=False, default=utc_now_iso)
