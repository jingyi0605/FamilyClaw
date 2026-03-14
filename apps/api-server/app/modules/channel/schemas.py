from typing import Any, Literal

from pydantic import BaseModel, Field


ChannelAccountStatus = Literal["draft", "active", "degraded", "disabled"]
ChannelConnectionMode = Literal["webhook", "polling", "websocket"]
ChannelBindingStatus = Literal["active", "disabled"]
ChannelInboundEventStatus = Literal["received", "matched", "dispatched", "ignored", "failed"]
ChannelDeliveryStatus = Literal["pending", "sent", "failed", "skipped"]
ChannelDeliveryType = Literal["reply", "notice", "error"]
ChannelInboundChatType = Literal["direct", "group"]
ChannelBindingResolveStrategy = Literal["bound", "direct_unbound_prompt", "group_unbound_ignore"]
ChannelBridgeDisposition = Literal["dispatched", "ignored"]


class ChannelAccountCreate(BaseModel):
    plugin_id: str = Field(min_length=1, max_length=64)
    account_code: str = Field(min_length=1, max_length=64)
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


class ChannelAccountStatusRead(BaseModel):
    account: ChannelAccountRead
    recent_failure_summary: ChannelDeliveryFailureSummaryRead
    latest_delivery: ChannelDeliveryRead | None = None
    latest_inbound_event: ChannelInboundEventRead | None = None
    latest_failed_inbound_event: ChannelInboundEventRead | None = None
    recent_delivery_count: int = Field(default=0, ge=0)
    recent_inbound_count: int = Field(default=0, ge=0)


class ChannelInboundProcessingRead(BaseModel):
    processing_status: str
    member_id: str | None = None
    conversation_session_id: str | None = None
    assistant_message_id: str | None = None
    reply_text: str | None = None
    delivery_id: str | None = None
    delivery_status: str | None = None
    provider_message_ref: str | None = None
