import { ApiError, createCoreApiClient, createRequestClient } from '@familyclaw/user-core';
import type {
  AgentDetail,
  AgentListResponse,
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiProviderAdapter,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  ContextOverviewRead,
  Device,
  HomeAssistantConfig,
  HomeAssistantDeviceCandidatesResponse,
  HomeAssistantRoomCandidatesResponse,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  HouseholdVoiceprintSummaryRead,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginJobListRead,
  PluginRegistryItem,
  PluginRegistrySnapshot,
  PluginStateUpdateRequest,
  VoiceprintEnrollmentRead,
  VoiceDiscoveryBinding,
  VoiceDiscoveryListResponse,
} from './settingsTypes';

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

const coreApi = createCoreApiClient(request);

export { ApiError };

export const settingsApi = {
  ...coreApi,
  listAiProviderAdapters() {
    return request<AiProviderAdapter[]>('/ai-config/provider-adapters');
  },
  listHouseholdAiProviders(householdId: string) {
    return request<AiProviderProfile[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles`);
  },
  createHouseholdAiProvider(householdId: string, payload: AiProviderProfileCreatePayload) {
    return request<AiProviderProfile>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateHouseholdAiProvider(householdId: string, profileId: string, payload: AiProviderProfileUpdatePayload) {
    return request<AiProviderProfile>(
      `/ai-config/${encodeURIComponent(householdId)}/provider-profiles/${encodeURIComponent(profileId)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  deleteHouseholdAiProvider(householdId: string, profileId: string) {
    return request<void>(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles/${encodeURIComponent(profileId)}`, {
      method: 'DELETE',
    });
  },
  listHouseholdAiRoutes(householdId: string) {
    return request<AiCapabilityRoute[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-routes`);
  },
  upsertHouseholdAiRoute(householdId: string, capability: string, payload: AiCapabilityRouteUpsertPayload) {
    return request<AiCapabilityRoute>(
      `/ai-config/${encodeURIComponent(householdId)}/provider-routes/${encodeURIComponent(capability)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  listAgents(householdId: string) {
    return request<AgentListResponse>(`/ai-config/${encodeURIComponent(householdId)}`);
  },
  createAgent(
    householdId: string,
    payload: {
      display_name: string;
      agent_type?: 'butler' | 'nutritionist' | 'fitness_coach' | 'study_coach' | 'custom';
      self_identity: string;
      role_summary: string;
      intro_message?: string | null;
      speaking_style?: string | null;
      personality_traits: string[];
      service_focus: string[];
      service_boundaries?: Record<string, unknown> | null;
      conversation_enabled?: boolean;
      default_entry?: boolean;
      created_by?: string;
    },
  ) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getAgentDetail(householdId: string, agentId: string) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`);
  },
  updateAgent(
    householdId: string,
    agentId: string,
    payload: {
      display_name?: string;
      status?: AgentDetail['status'];
      sort_order?: number;
    },
  ) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  upsertAgentSoul(
    householdId: string,
    agentId: string,
    payload: {
      self_identity: string;
      role_summary: string;
      intro_message?: string | null;
      speaking_style?: string | null;
      personality_traits: string[];
      service_focus: string[];
      service_boundaries?: Record<string, unknown> | null;
      created_by?: string;
    },
  ) {
    return request<AgentDetail['soul']>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/soul`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  upsertAgentRuntimePolicy(
    householdId: string,
    agentId: string,
    payload: {
      conversation_enabled: boolean;
      default_entry: boolean;
      routing_tags: string[];
      memory_scope: Record<string, unknown> | null;
      autonomous_action_policy: {
        memory: 'ask' | 'notify' | 'auto';
        config: 'ask' | 'notify' | 'auto';
        action: 'ask' | 'notify' | 'auto';
      };
    },
  ) {
    return request<AgentDetail['runtime_policy']>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/runtime-policy`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  upsertAgentMemberCognitions(
    householdId: string,
    agentId: string,
    payload: {
      items: Array<{
        member_id: string;
        display_address?: string | null;
        closeness_level: number;
        service_priority: number;
        communication_style?: string | null;
        care_notes?: Record<string, unknown> | null;
        prompt_notes?: string | null;
      }>;
    },
  ) {
    return request<AgentDetail['member_cognitions']>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/member-cognitions`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  listVoiceTerminalDiscoveries(householdId: string) {
    return request<VoiceDiscoveryListResponse>(`/devices/voice-terminals/discoveries?household_id=${encodeURIComponent(householdId)}`);
  },
  claimVoiceTerminalDiscovery(
    fingerprint: string,
    payload: { household_id: string; room_id: string; terminal_name: string },
  ) {
    return request<VoiceDiscoveryBinding>(
      `/devices/voice-terminals/discoveries/${encodeURIComponent(fingerprint)}/claim`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },
  updateDevice(
    deviceId: string,
    payload: Partial<{
      name: string;
      status: 'active' | 'offline' | 'inactive';
      room_id: string | null;
      controllable: boolean;
      voice_auto_takeover_enabled: boolean;
      voiceprint_identity_enabled: boolean;
      voice_takeover_prefixes: string[];
    }>,
  ) {
    return request<Device>(`/devices/${encodeURIComponent(deviceId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  getHouseholdVoiceprintSummary(householdId: string, terminalId: string) {
    return request<HouseholdVoiceprintSummaryRead>(
      `/voiceprints/households/${encodeURIComponent(householdId)}/summary?terminal_id=${encodeURIComponent(terminalId)}`,
    );
  },
  createVoiceprintEnrollment(payload: {
    household_id: string;
    member_id: string;
    terminal_id: string;
    expected_phrase?: string | null;
    sample_goal?: number;
  }) {
    return request<VoiceprintEnrollmentRead>('/voiceprints/enrollments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getVoiceprintEnrollment(enrollmentId: string) {
    return request<VoiceprintEnrollmentRead>(`/voiceprints/enrollments/${encodeURIComponent(enrollmentId)}`);
  },
  cancelVoiceprintEnrollment(enrollmentId: string) {
    return request<VoiceprintEnrollmentRead>(`/voiceprints/enrollments/${encodeURIComponent(enrollmentId)}/cancel`, {
      method: 'POST',
    });
  },
  getHomeAssistantConfig(householdId: string) {
    return request<HomeAssistantConfig>(`/devices/ha-config/${encodeURIComponent(householdId)}`);
  },
  updateHomeAssistantConfig(
    householdId: string,
    payload: {
      base_url: string | null;
      access_token?: string | null;
      clear_access_token?: boolean;
      sync_rooms_enabled: boolean;
    },
  ) {
    return request<HomeAssistantConfig>(`/devices/ha-config/${encodeURIComponent(householdId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  listHomeAssistantDeviceCandidates(householdId: string) {
    return request<HomeAssistantDeviceCandidatesResponse>(`/devices/ha-candidates/${encodeURIComponent(householdId)}`);
  },
  syncSelectedHomeAssistantDevices(householdId: string, externalDeviceIds: string[]) {
    return request<HomeAssistantSyncResponse>('/devices/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId, external_device_ids: externalDeviceIds }),
    });
  },
  listHomeAssistantRoomCandidates(householdId: string) {
    return request<HomeAssistantRoomCandidatesResponse>(`/devices/rooms/ha-candidates/${encodeURIComponent(householdId)}`);
  },
  syncSelectedHomeAssistantRooms(householdId: string, roomNames: string[]) {
    return request<HomeAssistantRoomSyncResponse>('/devices/rooms/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId, room_names: roomNames }),
    });
  },
  getContextOverview(householdId: string) {
    return request<ContextOverviewRead>(`/context/overview?household_id=${encodeURIComponent(householdId)}`);
  },
  listChannelAccounts(householdId: string) {
    return request<ChannelAccountRead[]>(`/ai-config/${encodeURIComponent(householdId)}/channel-accounts`);
  },
  createChannelAccount(householdId: string, payload: ChannelAccountCreate) {
    return request<ChannelAccountRead>(`/ai-config/${encodeURIComponent(householdId)}/channel-accounts`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateChannelAccount(householdId: string, accountId: string, payload: ChannelAccountUpdate) {
    return request<ChannelAccountRead>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  probeChannelAccount(householdId: string, accountId: string) {
    return request<ChannelAccountStatusRead>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/probe`,
      { method: 'POST' },
    );
  },
  getChannelAccountStatus(householdId: string, accountId: string) {
    return request<ChannelAccountStatusRead>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/status`,
    );
  },
  listChannelDeliveries(
    householdId: string,
    params?: { channel_account_id?: string; platform_code?: string; status?: string },
  ) {
    const query = new URLSearchParams();
    if (params?.channel_account_id) query.set('channel_account_id', params.channel_account_id);
    if (params?.platform_code) query.set('platform_code', params.platform_code);
    if (params?.status) query.set('status', params.status);
    const queryString = query.toString();
    return request<ChannelDeliveryRead[]>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-deliveries${queryString ? `?${queryString}` : ''}`,
    );
  },
  listChannelInboundEvents(
    householdId: string,
    params?: { channel_account_id?: string; platform_code?: string; status?: string },
  ) {
    const query = new URLSearchParams();
    if (params?.channel_account_id) query.set('channel_account_id', params.channel_account_id);
    if (params?.platform_code) query.set('platform_code', params.platform_code);
    if (params?.status) query.set('status', params.status);
    const queryString = query.toString();
    return request<ChannelInboundEventRead[]>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-inbound-events${queryString ? `?${queryString}` : ''}`,
    );
  },
  listChannelAccountBindings(householdId: string, accountId: string) {
    return request<MemberChannelBindingRead[]>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings`,
    );
  },
  createChannelAccountBinding(householdId: string, accountId: string, payload: MemberChannelBindingCreate) {
    return request<MemberChannelBindingRead>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },
  updateChannelAccountBinding(
    householdId: string,
    accountId: string,
    bindingId: string,
    payload: MemberChannelBindingUpdate,
  ) {
    return request<MemberChannelBindingRead>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings/${encodeURIComponent(bindingId)}`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  listRegisteredPlugins(householdId: string) {
    return request<PluginRegistrySnapshot>(`/ai-config/${encodeURIComponent(householdId)}/plugins`);
  },
  updatePluginState(householdId: string, pluginId: string, payload: PluginStateUpdateRequest) {
    return request<PluginRegistryItem>(
      `/ai-config/${encodeURIComponent(householdId)}/plugins/${encodeURIComponent(pluginId)}/state`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  listPluginJobs(
    householdId: string,
    params?: {
      status?: string;
      plugin_id?: string;
      created_from?: string;
      created_to?: string;
      page?: number;
      page_size?: number;
    },
  ) {
    const query = new URLSearchParams({ household_id: householdId });
    if (params?.status) query.set('status', params.status);
    if (params?.plugin_id) query.set('plugin_id', params.plugin_id);
    if (params?.created_from) query.set('created_from', params.created_from);
    if (params?.created_to) query.set('created_to', params.created_to);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    return request<PluginJobListRead>(`/plugin-jobs?${query.toString()}`);
  },
};
