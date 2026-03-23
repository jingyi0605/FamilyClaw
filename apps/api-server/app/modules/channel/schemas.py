from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ChannelAccountStatus = Literal["draft", "active", "degraded", "disabled"]
ChannelConnectionMode = Literal["webhook", "polling", "websocket"]
ChannelBindingStatus = Literal["active", "disabled"]
ChannelInboundEventStatus = Literal["received", "matched", "dispatched", "ignored", "failed"]
ChannelDeliveryStatus = Literal["pending", "sent", "failed", "skipped"]
ChannelDeliveryType = Literal["reply", "notice", "error"]
ChannelDeliveryAttachmentKind = Literal["image", "video", "audio", "file"]
ChannelInboundChatType = Literal["direct", "group"]
ChannelBindingResolveStrategy = Literal["bound", "direct_unbound_prompt", "group_unbound_ignore"]
ChannelBridgeDisposition = Literal["dispatched", "ignored"]
ChannelAccountPluginActionVariant = Literal["default", "primary", "danger"]
ChannelAccountPluginStatusTone = Literal["neutral", "info", "success", "warning", "danger"]
ChannelAccountPluginArtifactKind = Literal["image_url", "external_url", "text"]


class ChannelAccountCreate(BaseModel):
    plugin_id: str = Field(min_length=1, max_length=64)
    account_code: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    connection_mode: ChannelConnectionMode
    config: dict[str, Any] = Field(default_factory=dict)
    status: ChannelAccountStatus = "draft"


class ChannelAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    connection_mode: ChannelConnectionMode | None = None
    config: dict[str, Any] | None = None
    status: ChannelAccountStatus | None = None
    last_probe_status: str | None = Field(default=None, max_length=20)
    last_error_code: str | None = Field(default=None, max_length=100)
    last_error_message: str | None = None
    last_inbound_at: str | None = None
    last_outbound_at: str | None = None


class ChannelAccountRead(BaseModel):
    id: str
    household_id: str
    plugin_id: str
    platform_code: str
    account_code: str
    display_name: str
    connection_mode: ChannelConnectionMode
    config: dict[str, Any] = Field(default_factory=dict)
    status: ChannelAccountStatus
    last_probe_status: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_inbound_at: str | None = None
    last_outbound_at: str | None = None
    created_at: str
    updated_at: str


class MemberChannelBindingCreate(BaseModel):
    channel_account_id: str = Field(min_length=1)
    member_id: str = Field(min_length=1)
    external_user_id: str = Field(min_length=1, max_length=255)
    external_chat_id: str | None = Field(default=None, max_length=255)
    display_hint: str | None = Field(default=None, max_length=255)
    binding_status: ChannelBindingStatus = "active"


class MemberChannelBindingUpdate(BaseModel):
    external_user_id: str | None = Field(default=None, min_length=1, max_length=255)
    external_chat_id: str | None = Field(default=None, max_length=255)
    display_hint: str | None = Field(default=None, max_length=255)
    binding_status: ChannelBindingStatus | None = None


class MemberChannelBindingRead(BaseModel):
    id: str
    household_id: str
    member_id: str
    channel_account_id: str
    platform_code: str
    external_user_id: str
    external_chat_id: str | None = None
    display_hint: str | None = None
    binding_status: ChannelBindingStatus
    created_at: str
    updated_at: str


class ChannelBindingCandidateRead(BaseModel):
    external_user_id: str
    external_chat_id: str | None = None
    sender_display_name: str | None = None
    username: str | None = None
    chat_type: ChannelInboundChatType
    last_message_text: str | None = None
    last_seen_at: str
    inbound_event_id: str
    platform_code: str
    channel_account_id: str


class ChannelInboundEventCreate(BaseModel):
    household_id: str = Field(min_length=1)
    channel_account_id: str = Field(min_length=1)
    external_event_id: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=50)
    external_user_id: str | None = Field(default=None, max_length=255)
    external_conversation_key: str | None = Field(default=None, max_length=255)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    status: ChannelInboundEventStatus = "received"
    conversation_session_id: str | None = None
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = None
    received_at: str | None = None
    processed_at: str | None = None


class ChannelInboundEventRead(BaseModel):
    id: str
    household_id: str
    channel_account_id: str
    platform_code: str
    external_event_id: str
    event_type: str
    external_user_id: str | None = None
    external_conversation_key: str | None = None
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    status: ChannelInboundEventStatus
    conversation_session_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    received_at: str
    processed_at: str | None = None


class ChannelDeliveryCreate(BaseModel):
    household_id: str = Field(min_length=1)
    channel_account_id: str = Field(min_length=1)
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    external_conversation_key: str = Field(min_length=1, max_length=255)
    delivery_type: ChannelDeliveryType
    request_payload: dict[str, Any] = Field(default_factory=dict)
    provider_message_ref: str | None = Field(default=None, max_length=255)
    status: ChannelDeliveryStatus = "pending"
    attempt_count: int = Field(default=0, ge=0)
    last_error_code: str | None = Field(default=None, max_length=100)
    last_error_message: str | None = None


class ChannelDeliveryAttachment(BaseModel):
    kind: ChannelDeliveryAttachmentKind
    file_name: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    source_path: str | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    size_bytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelDeliveryRead(BaseModel):
    id: str
    household_id: str
    channel_account_id: str
    platform_code: str
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    external_conversation_key: str
    delivery_type: ChannelDeliveryType
    request_payload: dict[str, Any] = Field(default_factory=dict)
    provider_message_ref: str | None = None
    status: ChannelDeliveryStatus
    attempt_count: int = Field(ge=0)
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: str
    updated_at: str


class ChannelGatewayInboundEvent(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=50)
    external_user_id: str | None = Field(default=None, max_length=255)
    external_conversation_key: str | None = Field(default=None, max_length=255)
    normalized_payload: dict[str, Any] = Field(default_factory=dict)
    status: ChannelInboundEventStatus = "received"
    conversation_session_id: str | None = None
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = None
    received_at: str | None = None
    processed_at: str | None = None


class ChannelGatewayWebhookAck(BaseModel):
    accepted: bool = True
    account_id: str
    plugin_id: str
    event_recorded: bool = False
    duplicate: bool = False
    inbound_event_id: str | None = None
    external_event_id: str | None = None
    status: str = "accepted"
    message: str | None = None
    processing_status: str | None = None
    member_id: str | None = None
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    reply_text: str | None = None
    delivery_id: str | None = None
    delivery_status: str | None = None
    provider_message_ref: str | None = None


class ChannelGatewayHttpResponse(BaseModel):
    status_code: int = Field(default=200, ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    body_json: dict[str, Any] | list[Any] | None = None
    body_text: str | None = None
    media_type: str | None = Field(default=None, max_length=100)
    defer_processing: bool = False


class ChannelGatewayHandleResult(BaseModel):
    ack: ChannelGatewayWebhookAck
    http_response: ChannelGatewayHttpResponse | None = None


class ChannelPollingExecutionRead(BaseModel):
    events: list[ChannelGatewayInboundEvent] = Field(default_factory=list)
    next_cursor: str | None = Field(default=None, max_length=255)
    message: str | None = None


class ChannelPollingBatchRead(BaseModel):
    account_id: str
    plugin_id: str
    fetched_event_count: int = Field(default=0, ge=0)
    recorded_event_count: int = Field(default=0, ge=0)
    duplicate_event_count: int = Field(default=0, ge=0)
    processed_event_count: int = Field(default=0, ge=0)
    next_cursor: str | None = None
    message: str | None = None


class ChannelInboundMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    chat_type: ChannelInboundChatType
    external_message_id: str | None = Field(default=None, max_length=255)
    thread_key: str | None = Field(default=None, max_length=255)
    sender_display_name: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelBindingResolveRead(BaseModel):
    matched: bool
    strategy: ChannelBindingResolveStrategy
    member_id: str | None = None
    binding_id: str | None = None
    reply_text: str | None = None


class ChannelConversationBridgeRead(BaseModel):
    inbound_event_id: str
    disposition: ChannelBridgeDisposition
    member_id: str | None = None
    binding_strategy: ChannelBindingResolveStrategy
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    request_id: str | None = None
    reply_text: str | None = None
    created_session: bool = False
    created_conversation_binding: bool = False


class ChannelDeliveryDispatchRead(BaseModel):
    delivery: ChannelDeliveryRead
    sent: bool
    provider_message_ref: str | None = None


class ChannelDeliveryFailureSummaryRead(BaseModel):
    channel_account_id: str
    platform_code: str
    recent_failure_count: int = Field(ge=0)
    last_delivery_id: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    last_failed_at: str | None = None


class ChannelAccountPluginActionRead(BaseModel):
    key: str
    action_name: str
    label: str
    description: str | None = None
    variant: ChannelAccountPluginActionVariant = "default"
    requires_confirmation: bool = False
    confirmation_text: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None


class ChannelAccountPluginStatusSummaryRead(BaseModel):
    status: str
    title: str | None = None
    message: str | None = None
    tone: ChannelAccountPluginStatusTone = "neutral"
    last_error_code: str | None = None
    last_error_message: str | None = None
    updated_at: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ChannelAccountPluginArtifactRead(BaseModel):
    kind: ChannelAccountPluginArtifactKind
    label: str | None = None
    url: str | None = None
    text: str | None = None

    @field_validator("label", "text")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("artifact text cannot be empty")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("artifact url cannot be empty")
        if normalized.startswith("data:"):
            if not normalized.startswith("data:image/"):
                raise ValueError("artifact data URL must be an image")
            if len(normalized) > 200_000:
                raise ValueError("artifact data URL is too long")
            return normalized
        if len(normalized) > 4096:
            raise ValueError("artifact url is too long")
        return normalized

    @model_validator(mode="after")
    def validate_payload(self) -> "ChannelAccountPluginArtifactRead":
        if self.kind in {"image_url", "external_url"} and self.url is None:
            raise ValueError("artifact url is required")
        if self.kind == "external_url" and self.url is not None and self.url.startswith("data:"):
            raise ValueError("external_url artifact does not allow data URLs")
        if self.kind == "text" and self.text is None:
            raise ValueError("artifact text is required")
        return self


class ChannelAccountPluginActionExecuteRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ChannelAccountPluginActionExecuteRead(BaseModel):
    action: ChannelAccountPluginActionRead
    message: str | None = None
    status_summary: ChannelAccountPluginStatusSummaryRead | None = None
    artifacts: list[ChannelAccountPluginArtifactRead] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)


class ChannelAccountStatusRead(BaseModel):
    account: ChannelAccountRead
    recent_failure_summary: ChannelDeliveryFailureSummaryRead
    latest_delivery: ChannelDeliveryRead | None = None
    latest_inbound_event: ChannelInboundEventRead | None = None
    latest_failed_inbound_event: ChannelInboundEventRead | None = None
    recent_delivery_count: int = Field(default=0, ge=0)
    recent_inbound_count: int = Field(default=0, ge=0)
    plugin_status_summary: ChannelAccountPluginStatusSummaryRead | None = None
    plugin_actions: list[ChannelAccountPluginActionRead] = Field(default_factory=list)


class ChannelInboundProcessingRead(BaseModel):
    processing_status: str
    member_id: str | None = None
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    reply_text: str | None = None
    delivery_id: str | None = None
    delivery_status: str | None = None
    provider_message_ref: str | None = None
