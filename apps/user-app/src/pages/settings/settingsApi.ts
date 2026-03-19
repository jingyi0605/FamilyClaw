import { ApiError, createCoreApiClient, createRequestClient } from '@familyclaw/user-core';
import type {
  AgentDetail,
  AgentModelBinding,
  AgentListResponse,
  AgentSkillModelBinding,
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiCapability,
  AiProviderAdapter,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
  ChannelAccountCreate,
  ChannelAccountRead,
  ChannelAccountStatusRead,
  ChannelAccountUpdate,
  ChannelBindingCandidateRead,
  ChannelDeliveryRead,
  ChannelInboundEventRead,
  ContextOverviewRead,
  Device,
  DeviceActionExecuteRequest,
  DeviceActionExecuteResponse,
  DeviceActionLogListRead,
  DeviceDetailViewRead,
  DeviceEntityListRead,
  IntegrationActionResult,
  IntegrationCatalogListRead,
  IntegrationInstance,
  IntegrationInstanceActionRequest,
  IntegrationInstanceCreateRequest,
  IntegrationInstanceListRead,
  IntegrationInstanceUpdateRequest,
  IntegrationPageViewModel,
  IntegrationResourceListRead,
  MarketplaceCatalogListRead,
  MarketplaceEntryDetailRead,
  MarketplaceInstallTaskCreateRequest,
  MarketplaceInstallTaskRead,
  MarketplaceInstanceRead,
  MarketplaceSourceCreateRequest,
  MarketplaceSourceRead,
  MarketplaceSourceSyncResultRead,
  HouseholdVoiceprintSummaryRead,
  PluginConfigFormRead,
  PluginConfigResolveRequest,
  MemberChannelBindingCreate,
  MemberChannelBindingRead,
  MemberChannelBindingUpdate,
  PluginJobListRead,
  PluginPackageInstallRead,
  PluginRegistryItem,
  PluginRegistrySnapshot,
  PluginStateUpdateRequest,
  PluginVersionGovernanceRead,
  PluginVersionOperationRequest,
  PluginVersionOperationResultRead,
  VoiceprintEnrollmentRead,
  SystemVersionRead,
} from './settingsTypes';

const request = createRequestClient({
  baseUrl: '/api/v1',
  credentials: 'include',
});

const coreApi = createCoreApiClient(request);

function resolveApiErrorMessage(payload: unknown, fallbackMessage: string): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      const nestedDetail = (detail as { detail?: unknown }).detail;
      if (typeof nestedDetail === 'string' && nestedDetail.trim()) {
        return nestedDetail;
      }
    }
  }
  return fallbackMessage;
}

async function readApiPayload(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }
  const contentType = response.headers.get('content-type') ?? '';
  const text = await response.text().catch(() => '');
  if (!text.trim()) {
    return undefined;
  }
  if (!contentType.includes('application/json')) {
    return text;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export { ApiError };

export const settingsApi = {
  ...coreApi,
  getSystemVersion() {
    return request<SystemVersionRead>('/system/version');
  },
  listAiProviderAdapters(householdId: string) {
    return request<AiProviderAdapter[]>(`/ai-config/${encodeURIComponent(householdId)}/provider-adapters`);
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
  upsertHouseholdAiRoute(householdId: string, capability: AiCapability, payload: AiCapabilityRouteUpsertPayload) {
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
      model_bindings: AgentModelBinding[];
      agent_skill_model_bindings: AgentSkillModelBinding[];
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
  updateDevice(
    deviceId: string,
    payload: Partial<{
      name: string;
      status: 'active' | 'offline' | 'inactive' | 'disabled';
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
  listDeviceEntities(deviceId: string, view: 'favorites' | 'all') {
    return request<DeviceEntityListRead>(`/devices/${encodeURIComponent(deviceId)}/entities?view=${encodeURIComponent(view)}`);
  },
  getDeviceDetailView(deviceId: string) {
    return request<DeviceDetailViewRead>(`/devices/${encodeURIComponent(deviceId)}/detail-view`);
  },
  updateDeviceEntityFavorite(deviceId: string, entityId: string, favorite: boolean) {
    return request<DeviceEntityListRead>(`/devices/${encodeURIComponent(deviceId)}/entities/${encodeURIComponent(entityId)}/favorite`, {
      method: 'PUT',
      body: JSON.stringify({ favorite }),
    });
  },
  executeDeviceAction(payload: DeviceActionExecuteRequest) {
    return request<DeviceActionExecuteResponse>('/device-actions/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  disableDevice(deviceId: string) {
    return request<Device>(`/devices/${encodeURIComponent(deviceId)}/disable`, {
      method: 'POST',
    });
  },
  deleteDevice(deviceId: string) {
    return request<void>(`/devices/${encodeURIComponent(deviceId)}`, {
      method: 'DELETE',
    });
  },
  listDeviceActionLogs(
    deviceId: string,
    params?: { page?: number; page_size?: number },
  ) {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const queryString = query.toString();
    return request<DeviceActionLogListRead>(
      `/devices/${encodeURIComponent(deviceId)}/action-logs${queryString ? `?${queryString}` : ''}`,
    );
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
  getHouseholdPluginConfigForm(
    householdId: string,
    pluginId: string,
    params: {
      scope_type: 'plugin' | 'channel_account' | 'device' | 'integration_instance';
      scope_key: string;
    },
  ) {
    const query = new URLSearchParams({
      scope_type: params.scope_type,
      scope_key: params.scope_key,
    });
    return request<PluginConfigFormRead>(
      `/ai-config/${encodeURIComponent(householdId)}/plugins/${encodeURIComponent(pluginId)}/config?${query.toString()}`,
    );
  },
  saveHouseholdPluginConfigForm(
    householdId: string,
    pluginId: string,
    payload: {
      scope_type: 'plugin' | 'channel_account' | 'device' | 'integration_instance';
      scope_key: string;
      values: Record<string, unknown>;
      clear_fields?: string[];
      clear_secret_fields: string[];
    },
  ) {
    return request<PluginConfigFormRead>(
      `/ai-config/${encodeURIComponent(householdId)}/plugins/${encodeURIComponent(pluginId)}/config`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  resolveHouseholdPluginConfigForm(
    householdId: string,
    pluginId: string,
    payload: PluginConfigResolveRequest,
  ) {
    return request<PluginConfigFormRead>(
      `/ai-config/${encodeURIComponent(householdId)}/plugins/${encodeURIComponent(pluginId)}/config/resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },
  listIntegrationCatalog(
    householdId: string,
    params?: {
      q?: string;
      resource_type?: 'device' | 'entity' | 'helper';
    },
  ) {
    const query = new URLSearchParams({ household_id: householdId });
    if (params?.q) query.set('q', params.q);
    if (params?.resource_type) query.set('resource_type', params.resource_type);
    return request<IntegrationCatalogListRead>(`/integrations/catalog?${query.toString()}`);
  },
  listIntegrationInstances(householdId: string) {
    return request<IntegrationInstanceListRead>(`/integrations/instances?household_id=${encodeURIComponent(householdId)}`);
  },
  listIntegrationResources(
    householdId: string,
    params: {
      resource_type: 'device' | 'entity' | 'helper';
      integration_instance_id?: string;
      room_id?: string;
      status?: string;
    },
  ) {
    const query = new URLSearchParams({
      household_id: householdId,
      resource_type: params.resource_type,
    });
    if (params.integration_instance_id) query.set('integration_instance_id', params.integration_instance_id);
    if (params.room_id) query.set('room_id', params.room_id);
    if (params.status) query.set('status', params.status);
    return request<IntegrationResourceListRead>(`/integrations/resources?${query.toString()}`);
  },
  async getLegacyIntegrationPageView(householdId: string) {
    // 当前设置页只用到目录、实例和已同步设备，直接走稳定的独立接口，
    // 避免被后端聚合视图里尚未落库的 discoveries 表拖死。
    const [catalog, instances, resources] = await Promise.all([
      settingsApi.listIntegrationCatalog(householdId),
      settingsApi.listIntegrationInstances(householdId),
      settingsApi.listIntegrationResources(householdId, { resource_type: 'device' }),
    ]);

    return {
      household_id: householdId,
      catalog: catalog.items,
      instances: instances.items,
      discoveries: [],
      resources: {
        device: resources.items,
        entity: [],
        helper: [],
      },
    };
  },
  getIntegrationPageView(householdId: string) {
    return request<IntegrationPageViewModel>(
      `/integrations/page-view?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  createIntegrationInstance(payload: IntegrationInstanceCreateRequest) {
    return request<IntegrationInstance>('/integrations/instances', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateIntegrationInstance(instanceId: string, payload: IntegrationInstanceUpdateRequest) {
    return request<IntegrationInstance>(`/integrations/instances/${encodeURIComponent(instanceId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  deleteIntegrationInstance(instanceId: string) {
    return request<void>(`/integrations/instances/${encodeURIComponent(instanceId)}`, {
      method: 'DELETE',
    });
  },
  executeIntegrationInstanceAction(instanceId: string, payload: IntegrationInstanceActionRequest) {
    return request<IntegrationActionResult>(`/integrations/instances/${encodeURIComponent(instanceId)}/actions`, {
      method: 'POST',
      body: JSON.stringify(payload),
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
  deleteChannelAccount(householdId: string, accountId: string) {
    return request<void>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}`,
      {
        method: 'DELETE',
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
  listChannelAccountBindingCandidates(householdId: string, accountId: string) {
    return request<ChannelBindingCandidateRead[]>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/binding-candidates`,
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
  deleteChannelAccountBinding(householdId: string, accountId: string, bindingId: string) {
    return request<void>(
      `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings/${encodeURIComponent(bindingId)}`,
      {
        method: 'DELETE',
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
  async installPluginPackage(householdId: string, file: File, options?: { overwrite?: boolean }) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('overwrite', options?.overwrite ? 'true' : 'false');

    const response = await fetch(`/api/v1/ai-config/${encodeURIComponent(householdId)}/plugin-packages`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });
    const payload = await readApiPayload(response);
    if (!response.ok) {
      throw new ApiError(
        response.status,
        resolveApiErrorMessage(payload, `Request failed with status ${response.status}`),
        payload,
      );
    }
    return payload as PluginPackageInstallRead;
  },
  listMarketplaceSources() {
    return request<MarketplaceSourceRead[]>('/plugin-marketplace/sources');
  },
  createMarketplaceSource(payload: MarketplaceSourceCreateRequest) {
    return request<MarketplaceSourceRead>('/plugin-marketplace/sources', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  syncMarketplaceSource(sourceId: string) {
    return request<MarketplaceSourceSyncResultRead>(`/plugin-marketplace/sources/${encodeURIComponent(sourceId)}/sync`, {
      method: 'POST',
    });
  },
  listMarketplaceCatalog(householdId?: string) {
    const query = new URLSearchParams();
    if (householdId) {
      query.set('household_id', householdId);
    }
    return request<MarketplaceCatalogListRead>(`/plugin-marketplace/catalog${query.toString() ? `?${query.toString()}` : ''}`);
  },
  getMarketplaceEntryDetail(sourceId: string, pluginId: string, householdId?: string) {
    const query = new URLSearchParams();
    if (householdId) {
      query.set('household_id', householdId);
    }
    return request<MarketplaceEntryDetailRead>(
      `/plugin-marketplace/catalog/${encodeURIComponent(sourceId)}/${encodeURIComponent(pluginId)}${query.toString() ? `?${query.toString()}` : ''}`,
    );
  },
  getMarketplaceVersionGovernance(sourceId: string, pluginId: string, householdId?: string) {
    const query = new URLSearchParams();
    if (householdId) {
      query.set('household_id', householdId);
    }
    return request<PluginVersionGovernanceRead>(
      `/plugin-marketplace/catalog/${encodeURIComponent(sourceId)}/${encodeURIComponent(pluginId)}/version-governance${query.toString() ? `?${query.toString()}` : ''}`,
    );
  },
  createMarketplaceInstallTask(payload: MarketplaceInstallTaskCreateRequest) {
    return request<MarketplaceInstallTaskRead>('/plugin-marketplace/install-tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  setMarketplaceInstanceEnabled(instanceId: string, payload: PluginStateUpdateRequest) {
    return request<MarketplaceInstanceRead>(`/plugin-marketplace/instances/${encodeURIComponent(instanceId)}/enable`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  operateMarketplaceInstanceVersion(instanceId: string, payload: PluginVersionOperationRequest) {
    return request<PluginVersionOperationResultRead>(
      `/plugin-marketplace/instances/${encodeURIComponent(instanceId)}/version-operations`,
      {
        method: 'POST',
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
