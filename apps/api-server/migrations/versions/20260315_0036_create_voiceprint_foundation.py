"""create voiceprint foundation tables

Revision ID: 20260315_0036
Revises: 20260315_0035
Create Date: 2026-03-15 23:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260315_0036"
down_revision = "20260315_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voiceprint_enrollments",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("terminal_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expected_phrase", sa.Text(), nullable=True),
        sa.Column("sample_goal", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint("sample_goal > 0", name="ck_voiceprint_enrollments_sample_goal_positive"),
        sa.CheckConstraint("sample_count >= 0", name="ck_voiceprint_enrollments_sample_count_non_negative"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terminal_id"], ["devices.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_voiceprint_enrollments_household_id", "voiceprint_enrollments", ["household_id"], unique=False)
    op.create_index("idx_voiceprint_enrollments_member_id", "voiceprint_enrollments", ["member_id"], unique=False)
    op.create_index("idx_voiceprint_enrollments_terminal_id", "voiceprint_enrollments", ["terminal_id"], unique=False)
    op.create_index("idx_voiceprint_enrollments_status", "voiceprint_enrollments", ["status"], unique=False)
    op.create_index("idx_voiceprint_enrollments_expires_at", "voiceprint_enrollments", ["expires_at"], unique=False)

    op.create_table(
        "member_voiceprint_profiles",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="sherpa_onnx_wespeaker_resnet34"),
        sa.Column("provider_profile_ref", sa.String(length=255), nullable=True),
        sa.Column("profile_payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint("sample_count >= 0", name="ck_member_voiceprint_profiles_sample_count_non_negative"),
        sa.CheckConstraint("version > 0", name="ck_member_voiceprint_profiles_version_positive"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "household_id",
            "member_id",
            "version",
            name="uq_member_voiceprint_profiles_household_member_version",
        ),
    )
    op.create_index("idx_member_voiceprint_profiles_household_id", "member_voiceprint_profiles", ["household_id"], unique=False)
    op.create_index("idx_member_voiceprint_profiles_member_id", "member_voiceprint_profiles", ["member_id"], unique=False)
    op.create_index("idx_member_voiceprint_profiles_status", "member_voiceprint_profiles", ["status"], unique=False)

    op.create_table(
        "member_voiceprint_samples",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("profile_id", sa.Text(), nullable=True),
        sa.Column("enrollment_id", sa.Text(), nullable=True),
        sa.Column("household_id", sa.Text(), nullable=False),
        sa.Column("member_id", sa.Text(), nullable=False),
        sa.Column("terminal_id", sa.Text(), nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("sample_width", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("sample_payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="accepted"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("sample_rate > 0", name="ck_member_voiceprint_samples_sample_rate_positive"),
        sa.CheckConstraint("channels > 0", name="ck_member_voiceprint_samples_channels_positive"),
        sa.CheckConstraint("sample_width > 0", name="ck_member_voiceprint_samples_sample_width_positive"),
        sa.CheckConstraint("duration_ms > 0", name="ck_member_voiceprint_samples_duration_positive"),
        sa.ForeignKeyConstraint(["profile_id"], ["member_voiceprint_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["voiceprint_enrollments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terminal_id"], ["devices.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_member_voiceprint_samples_profile_id", "member_voiceprint_samples", ["profile_id"], unique=False)
    op.create_index("idx_member_voiceprint_samples_enrollment_id", "member_voiceprint_samples", ["enrollment_id"], unique=False)
    op.create_index("idx_member_voiceprint_samples_household_id", "member_voiceprint_samples", ["household_id"], unique=False)
    op.create_index("idx_member_voiceprint_samples_member_id", "member_voiceprint_samples", ["member_id"], unique=False)
    op.create_index("idx_member_voiceprint_samples_terminal_id", "member_voiceprint_samples", ["terminal_id"], unique=False)
    op.create_index("idx_member_voiceprint_samples_status", "member_voiceprint_samples", ["status"], unique=False)
    op.create_index("idx_member_voiceprint_samples_created_at", "member_voiceprint_samples", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_member_voiceprint_samples_created_at", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_status", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_terminal_id", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_member_id", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_household_id", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_enrollment_id", table_name="member_voiceprint_samples")
    op.drop_index("idx_member_voiceprint_samples_profile_id", table_name="member_voiceprint_samples")
    op.drop_table("member_voiceprint_samples")

    op.drop_index("idx_member_voiceprint_profiles_status", table_name="member_voiceprint_profiles")
    op.drop_index("idx_member_voiceprint_profiles_member_id", table_name="member_voiceprint_profiles")
    op.drop_index("idx_member_voiceprint_profiles_household_id", table_name="member_voiceprint_profiles")
    op.drop_table("member_voiceprint_profiles")

    op.drop_index("idx_voiceprint_enrollments_expires_at", table_name="voiceprint_enrollments")
    op.drop_index("idx_voiceprint_enrollments_status", table_name="voiceprint_enrollments")
    op.drop_index("idx_voiceprint_enrollments_terminal_id", table_name="voiceprint_enrollments")
    op.drop_index("idx_voiceprint_enrollments_member_id", table_name="voiceprint_enrollments")
    op.drop_index("idx_voiceprint_enrollments_household_id", table_name="voiceprint_enrollments")
    op.drop_table("voiceprint_enrollments")
