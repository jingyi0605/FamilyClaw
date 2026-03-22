from app.modules.account.models import Account, AccountMemberBinding, AccountSession
from app.modules.agent.models import (
    FamilyAgent,
    FamilyAgentBootstrapMessage,
    FamilyAgentBootstrapRequest,
    FamilyAgentBootstrapSession,
    FamilyAgentMemberCognition,
    FamilyAgentRuntimePolicy,
    FamilyAgentSoulProfile,
)
from app.modules.ai_gateway.models import AiCapabilityRoute, AiModelCallLog, AiProviderProfile
from app.modules.audit.models import AuditLog
from app.modules.channel.models import (
    ChannelConversationBinding,
    ChannelDelivery,
    ChannelInboundEvent,
    ChannelPluginAccount,
    MemberChannelBinding,
)
from app.modules.context.models import ContextConfig
from app.modules.conversation.models import (
    ConversationActionRecord,
    ConversationDeviceControlShortcut,
    ConversationDebugLog,
    ConversationMemoryRead,
    ConversationMemoryCandidate,
    ConversationMessage,
    ConversationProposalBatch,
    ConversationProposalItem,
    ConversationSession,
    ConversationSessionSummary,
    ConversationTurnSource,
)
from app.modules.device.models import Device, DeviceBinding, DeviceEntity, DeviceEntityFavorite
from app.modules.family_qa.models import QaQueryLog
from app.modules.household import lifecycle as household_lifecycle  # noqa: F401
from app.modules.household.models import Household
from app.modules.integration.models import IntegrationDiscovery, IntegrationInstance
from app.modules.member.models import Member, MemberPreference
from app.modules.memory.models import (
    EpisodicMemoryEntryRevision,
    EpisodicMemoryEntry,
    EventRecord,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    MemoryCard,
    MemoryCardMember,
    MemoryCardRevision,
    MemoryRecallDocument,
)
from app.modules.permission.models import MemberPermission
from app.modules.plugin.models import (
    MemberDashboardLayout,
    PluginConfigInstance,
    PluginDashboardCardSnapshot,
    PluginJob,
    PluginJobAttempt,
    PluginJobNotification,
    PluginJobResponse,
    PluginMount,
    PluginRawRecord,
    PluginRun,
)
from app.modules.plugin_marketplace.models import (
    PluginMarketplaceEntrySnapshot,
    PluginMarketplaceInstallTask,
    PluginMarketplaceInstance,
    PluginMarketplaceSource,
)
from app.modules.presence.models import MemberPresenceState, PresenceEvent
from app.modules.reminder.models import ReminderAckEvent, ReminderDeliveryAttempt, ReminderRun, ReminderTask
from app.modules.region.models import HouseholdRegionBinding, RegionNode
from app.modules.relationship.models import MemberRelationship
from app.modules.scene.models import SceneExecution, SceneExecutionStep, SceneTemplate
from app.modules.room.models import Room
from app.modules.scheduler.models import ScheduledTaskDefinition, ScheduledTaskDelivery, ScheduledTaskRun
from app.modules.voiceprint.models import MemberVoiceprintProfile, MemberVoiceprintSample, VoiceprintEnrollment
from app.modules.voice.models import SpeakerRuntimeState, VoiceTerminalConversationBinding

__all__ = [
    "Account",
    "AccountMemberBinding",
    "AccountSession",
    "FamilyAgent",
    "FamilyAgentBootstrapMessage",
    "FamilyAgentBootstrapRequest",
    "FamilyAgentBootstrapSession",
    "FamilyAgentMemberCognition",
    "FamilyAgentRuntimePolicy",
    "FamilyAgentSoulProfile",
    "AiCapabilityRoute",
    "AiModelCallLog",
    "AiProviderProfile",
    "AuditLog",
    "ChannelConversationBinding",
    "ChannelDelivery",
    "ChannelInboundEvent",
    "ChannelPluginAccount",
    "ContextConfig",
    "ConversationSession",
    "ConversationSessionSummary",
    "ConversationMessage",
    "ConversationMemoryCandidate",
    "ConversationProposalBatch",
    "ConversationProposalItem",
    "ConversationActionRecord",
    "ConversationDeviceControlShortcut",
    "ConversationDebugLog",
    "ConversationMemoryRead",
    "ConversationTurnSource",
    "Device",
    "DeviceBinding",
    "DeviceEntity",
    "DeviceEntityFavorite",
    "Household",
    "Member",
    "MemberChannelBinding",
    "MemberPermission",
    "MemberDashboardLayout",
    "PluginRawRecord",
    "PluginConfigInstance",
    "PluginDashboardCardSnapshot",
    "PluginJob",
    "PluginJobAttempt",
    "PluginJobNotification",
    "PluginJobResponse",
    "PluginMarketplaceEntrySnapshot",
    "PluginMarketplaceInstallTask",
    "PluginMarketplaceInstance",
    "PluginMarketplaceSource",
    "PluginMount",
    "PluginRun",
    "MemberPreference",
    "MemoryCard",
    "MemoryCardMember",
    "MemoryCardRevision",
    "EpisodicMemoryEntry",
    "EpisodicMemoryEntryRevision",
    "KnowledgeDocument",
    "KnowledgeDocumentRevision",
    "MemoryRecallDocument",
    "MemberPresenceState",
    "MemberRelationship",
    "EventRecord",
    "PresenceEvent",
    "QaQueryLog",
    "IntegrationInstance",
    "IntegrationDiscovery",
    "ReminderAckEvent",
    "ReminderDeliveryAttempt",
    "ReminderRun",
    "ReminderTask",
    "RegionNode",
    "HouseholdRegionBinding",
    "Room",
    "ScheduledTaskDefinition",
    "ScheduledTaskRun",
    "ScheduledTaskDelivery",
    "SceneExecution",
    "SceneExecutionStep",
    "SceneTemplate",
    "VoiceprintEnrollment",
    "MemberVoiceprintProfile",
    "MemberVoiceprintSample",
    "SpeakerRuntimeState",
    "VoiceTerminalConversationBinding",
]
