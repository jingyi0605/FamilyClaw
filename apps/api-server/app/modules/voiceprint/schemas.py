from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VoiceprintEnrollmentStatus = Literal["pending", "recording", "processing", "completed", "failed", "cancelled"]
VoiceprintProfileStatus = Literal["active", "superseded", "deleted", "failed"]
VoiceprintSampleStatus = Literal["accepted", "rejected", "deleted"]
VoiceprintConversationMode = Literal["public", "voiceprint_member"]
MemberVoiceprintSummaryStatus = Literal["not_enrolled", "pending", "active", "failed", "disabled"]


class VoiceprintEnrollmentCreate(BaseModel):
    household_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    terminal_id: str = Field(min_length=1)
    expected_phrase: str | None = Field(default=None, max_length=200)
    sample_goal: int = Field(default=6, ge=1, le=10)


class VoiceprintEnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    member_id: str
    terminal_id: str
    status: VoiceprintEnrollmentStatus
    expected_phrase: str | None = None
    sample_goal: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    expires_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class VoiceprintEnrollmentListResponse(BaseModel):
    items: list[VoiceprintEnrollmentRead]
    page: int
    page_size: int
    total: int


class PendingVoiceprintEnrollmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enrollment_id: str
    target_member_id: str
    expected_phrase: str | None = None
    sample_goal: int = Field(ge=1)
    sample_count: int = Field(ge=0)
    expires_at: str | None = None


class MemberVoiceprintProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    household_id: str
    member_id: str
    provider: str
    provider_profile_ref: str | None = None
    profile_payload_json: str | None = None
    status: VoiceprintProfileStatus
    sample_count: int = Field(ge=0)
    version: int = Field(ge=1)
    created_at: str
    updated_at: str


class MemberVoiceprintSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str | None = None
    enrollment_id: str | None = None
    household_id: str
    member_id: str
    terminal_id: str
    artifact_id: str
    artifact_path: str
    artifact_sha256: str
    sample_rate: int = Field(ge=1)
    channels: int = Field(ge=1)
    sample_width: int = Field(ge=1)
    duration_ms: int = Field(ge=1)
    transcript_text: str | None = None
    sample_payload_json: str | None = None
    status: VoiceprintSampleStatus
    created_at: str


class MemberVoiceprintDetailRead(BaseModel):
    member_id: str
    household_id: str
    active_profile: MemberVoiceprintProfileRead | None = None
    samples: list[MemberVoiceprintSampleRead] = Field(default_factory=list)
    pending_enrollments: list[VoiceprintEnrollmentRead] = Field(default_factory=list)
    recent_identification_status: str | None = None


class MemberVoiceprintDeleteResponse(BaseModel):
    member_id: str
    household_id: str
    deleted_profile_count: int = Field(ge=0)
    cancelled_enrollment_count: int = Field(ge=0)


class HouseholdVoiceprintMemberSummaryRead(BaseModel):
    member_id: str
    member_name: str
    member_role: str
    status: MemberVoiceprintSummaryStatus
    sample_count: int = Field(ge=0)
    updated_at: str | None = None
    pending_enrollment_id: str | None = None
    active_profile_id: str | None = None
    error_message: str | None = None


class HouseholdVoiceprintSummaryRead(BaseModel):
    household_id: str
    terminal_id: str
    voiceprint_identity_enabled: bool
    conversation_mode: VoiceprintConversationMode
    pending_enrollment: PendingVoiceprintEnrollmentRead | None = None
    members: list[HouseholdVoiceprintMemberSummaryRead] = Field(default_factory=list)
