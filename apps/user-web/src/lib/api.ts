import type {
  AgentDetail,
  AgentListResponse,
  ButlerBootstrapSession,
  AgentRuntimePolicy,
  AgentUpdatePayload,
  AgentMemberCognition,
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiProviderAdapter,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
  ContextConfigRead,
  ContextOverviewRead,
  ConversationActionExecutionResponse,
  ConversationMemoryCandidateActionResponse,
  ConversationProposalExecutionResponse,
  ConversationSessionDetail,
  ConversationSessionListResponse,
  ConversationTurnResponse,
  Device,
  FamilyQaQueryResponse,
  FamilyQaSuggestionsResponse,
  HomeAssistantConfig,
  HomeAssistantDeviceCandidatesResponse,
  HomeAssistantRoomCandidatesResponse,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  Household,
  RegionNode,
  RegionSelection,
  HouseholdSetupStatus,
  LoginResponse,
  MemoryCard,
  MemoryCardRevision,
  MemoryType,
  MemberPreference,
  MemberRelationship,
  Member,
  PaginatedResponse,
  PluginLocaleListResponse,
  ReminderTask,
  ReminderOverviewRead,
  Room,
  ScheduledTaskDefinition,
  ScheduledTaskDefinitionCreate,
  ScheduledTaskDefinitionUpdate,
  ScheduledTaskRun,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const API_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 8000);

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

function resolveErrorMessage(payload: unknown, fallbackMessage: string): string {
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

async function readResponsePayload(response: Response, isJsonResponse: boolean): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const text = await response.text().catch(() => '');
  if (!text.trim()) {
    return undefined;
  }

  if (!isJsonResponse) {
    return text;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (init?.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs ?? API_TIMEOUT_MS);

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers,
      signal: controller.signal,
    });
  } catch (error) {
    window.clearTimeout(timeoutId);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, '请求超时，请确认后端服务是否可用', null);
    }
    throw error;
  }

  window.clearTimeout(timeoutId);

  const contentType = response.headers.get('content-type') ?? '';
  const isJsonResponse = contentType.includes('application/json');

  if (!response.ok) {
    const payload = await readResponsePayload(response, isJsonResponse);
    throw new ApiError(
      response.status,
      resolveErrorMessage(payload, `Request failed with status ${response.status}`),
      payload,
    );
  }

  if (!isJsonResponse) {
    return undefined as T;
  }

  const payload = await readResponsePayload(response, isJsonResponse);
  return payload as T;
}

export const api = {
  login(payload: { username: string; password: string }) {
    return request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getAuthMe() {
    return request<LoginResponse>('/auth/me');
  },
  logout() {
    return request<void>('/auth/logout', {
      method: 'POST',
    });
  },
  completeBootstrapAccount(payload: {
    household_id: string;
    member_id: string;
    username: string;
    password: string;
  }) {
    return request<LoginResponse>('/auth/bootstrap/complete', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listHouseholds() {
    return request<PaginatedResponse<Household>>('/households?page_size=100');
  },
  createHousehold(payload: Pick<Household, 'name' | 'timezone' | 'locale'> & { city?: string | null; region_selection?: RegionSelection | null }) {
    return request<Household>('/households', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getHousehold(householdId: string) {
    return request<Household>(`/households/${encodeURIComponent(householdId)}`);
  },
  updateHousehold(householdId: string, payload: Partial<Pick<Household, 'name' | 'city' | 'timezone' | 'locale'> & { region_selection: RegionSelection | null }>) {
    return request<Household>(`/households/${encodeURIComponent(householdId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  listRegionCatalog(params: {
    provider_code: string;
    country_code: string;
    admin_level?: 'province' | 'city' | 'district';
    parent_region_code?: string;
  }) {
    const search = new URLSearchParams();
    search.set('provider_code', params.provider_code);
    search.set('country_code', params.country_code);
    if (params.admin_level) search.set('admin_level', params.admin_level);
    if (params.parent_region_code) search.set('parent_region_code', params.parent_region_code);
    return request<RegionNode[]>(`/regions/catalog?${search.toString()}`);
  },
  searchRegions(params: {
    provider_code: string;
    country_code: string;
    keyword: string;
    admin_level?: 'province' | 'city' | 'district';
    parent_region_code?: string;
  }) {
    const search = new URLSearchParams();
    search.set('provider_code', params.provider_code);
    search.set('country_code', params.country_code);
    search.set('keyword', params.keyword);
    if (params.admin_level) search.set('admin_level', params.admin_level);
    if (params.parent_region_code) search.set('parent_region_code', params.parent_region_code);
    return request<RegionNode[]>(`/regions/search?${search.toString()}`);
  },
  getHouseholdSetupStatus(householdId: string) {
    return request<HouseholdSetupStatus>(`/households/${encodeURIComponent(householdId)}/setup-status`);
  },
  listAiProviderAdapters() {
    return request<AiProviderAdapter[]>('/ai-config/provider-adapters');
  },
  listHouseholdAiProviders(householdId: string, options?: { enabled?: boolean; capability?: string }) {
    const params = new URLSearchParams();
    if (options?.enabled !== undefined) {
      params.set('enabled', String(options.enabled));
    }
    if (options?.capability) {
      params.set('capability', options.capability);
    }
    const query = params.toString();
    return request<AiProviderProfile[]>(
      `/ai-config/${encodeURIComponent(householdId)}/provider-profiles${query ? `?${query}` : ''}`,
    );
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
  listHouseholdLocales(householdId: string) {
    return request<PluginLocaleListResponse>(`/ai-config/${encodeURIComponent(householdId)}/locales`);
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
  listAiProviders() {
    return request<AiProviderProfile[]>('/ai/providers?enabled=true');
  },
  createAiProvider(payload: AiProviderProfileCreatePayload) {
    return request<AiProviderProfile>('/ai/providers', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listAiRoutes(householdId: string) {
    return request<AiCapabilityRoute[]>(`/ai/routes?household_id=${encodeURIComponent(householdId)}`);
  },
  upsertAiRoute(capability: string, payload: AiCapabilityRouteUpsertPayload) {
    return request<AiCapabilityRoute>(`/ai/routes/${encodeURIComponent(capability)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  createRoom(payload: {
    household_id: string;
    name: string;
    room_type: Room['room_type'];
    privacy_level: Room['privacy_level'];
  }) {
    return request<Room>('/rooms', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listRooms(householdId: string) {
    return request<PaginatedResponse<Room>>(`/rooms?household_id=${encodeURIComponent(householdId)}&page_size=100`);
  },
  updateRoom(roomId: string, payload: Partial<Pick<Room, 'name' | 'room_type' | 'privacy_level'>>) {
    return request<Room>(`/rooms/${encodeURIComponent(roomId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  deleteRoom(roomId: string) {
    return request<void>(`/rooms/${encodeURIComponent(roomId)}`, {
      method: 'DELETE',
    });
  },
  createMember(payload: {
    household_id: string;
    name: string;
    nickname?: string | null;
    gender?: 'male' | 'female' | null;
    role: Member['role'];
    age_group?: Member['age_group'];
    birthday?: string | null;
    phone?: string | null;
    status?: Member['status'];
    guardian_member_id?: string | null;
  }) {
    return request<Member>('/members', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateMember(memberId: string, payload: Partial<Member>) {
    return request<Member>(`/members/${encodeURIComponent(memberId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  listMembers(householdId: string) {
    return request<PaginatedResponse<Member>>(`/members?household_id=${encodeURIComponent(householdId)}&page_size=100`);
  },
  createMemberRelationship(payload: {
    household_id: string;
    source_member_id: string;
    target_member_id: string;
    relation_type: MemberRelationship['relation_type'];
    reverse_relation_type?: MemberRelationship['relation_type'] | null;
    visibility_scope: MemberRelationship['visibility_scope'];
    delegation_scope: MemberRelationship['delegation_scope'];
  }) {
    return request<MemberRelationship>('/member-relationships', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  deleteMemberRelationship(relationshipId: string) {
    return request<void>(`/member-relationships/${encodeURIComponent(relationshipId)}`, {
      method: 'DELETE',
    });
  },
  listMemberRelationships(householdId: string) {
    return request<PaginatedResponse<MemberRelationship>>(`/member-relationships?household_id=${encodeURIComponent(householdId)}&page_size=100`);
  },
  getMemberPreferences(memberId: string) {
    return request<MemberPreference>(`/member-preferences/${encodeURIComponent(memberId)}`);
  },
  upsertMemberPreferences(
    memberId: string,
    payload: Omit<MemberPreference, 'member_id' | 'updated_at'>,
  ) {
    return request<MemberPreference>(`/member-preferences/${encodeURIComponent(memberId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  listDevices(householdId: string) {
    return request<PaginatedResponse<Device>>(`/devices?household_id=${encodeURIComponent(householdId)}&page_size=100`);
  },
  updateDevice(deviceId: string, payload: Partial<Pick<Device, 'name' | 'status' | 'room_id' | 'controllable'>>) {
    return request<Device>(`/devices/${encodeURIComponent(deviceId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  getHomeAssistantConfig(householdId: string) {
    return request<HomeAssistantConfig>(`/devices/ha-config/${encodeURIComponent(householdId)}`);
  },
  updateHomeAssistantConfig(householdId: string, payload: {
    base_url: string | null;
    access_token?: string | null;
    clear_access_token?: boolean;
    sync_rooms_enabled: boolean;
  }) {
    return request<HomeAssistantConfig>(`/devices/ha-config/${encodeURIComponent(householdId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  listHomeAssistantDeviceCandidates(householdId: string) {
    return request<HomeAssistantDeviceCandidatesResponse>(`/devices/ha-candidates/${encodeURIComponent(householdId)}`);
  },
  syncHomeAssistant(householdId: string) {
    return request<HomeAssistantSyncResponse>('/devices/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId, external_device_ids: [] }),
    });
  },
  syncSelectedHomeAssistantDevices(householdId: string, externalDeviceIds: string[]) {
    return request<HomeAssistantSyncResponse>('/devices/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId, external_device_ids: externalDeviceIds }),
    });
  },
  syncHomeAssistantRooms(householdId: string) {
    return request<HomeAssistantRoomSyncResponse>('/devices/rooms/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId, room_names: [] }),
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
  getContextConfig(householdId: string) {
    return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`);
  },
  updateContextConfig(householdId: string, payload: Omit<ContextConfigRead, 'household_id' | 'version' | 'updated_by' | 'updated_at'>) {
    return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  getReminderOverview(householdId: string) {
    return request<ReminderOverviewRead>(`/reminders/overview?household_id=${encodeURIComponent(householdId)}`);
  },
  createButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession>(
      `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions`,
      { method: 'POST' },
      60000, // LLM 调用需要更长超时
    );
  },
  getLatestButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession | null>(
      `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/latest`,
      { method: 'GET' },
      60000,
    );
  },
  restartButlerBootstrapSession(householdId: string) {
    return request<ButlerBootstrapSession>(
      `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/restart`,
      { method: 'POST' },
      60000,
    );
  },
  confirmButlerBootstrapSession(
    householdId: string,
    sessionId: string,
    payload: { draft: ButlerBootstrapSession['draft']; created_by?: string },
  ) {
    return request<AgentDetail>(
      `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/${encodeURIComponent(sessionId)}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    );
  },
  listAgents(householdId: string) {
    return request<AgentListResponse>(`/ai-config/${encodeURIComponent(householdId)}`);
  },
  createAgent(householdId: string, payload: {
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
  }) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  getAgentDetail(householdId: string, agentId: string) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`);
  },
  updateAgent(householdId: string, agentId: string, payload: AgentUpdatePayload) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  upsertAgentSoul(householdId: string, agentId: string, payload: {
    self_identity: string;
    role_summary: string;
    intro_message?: string | null;
    speaking_style?: string | null;
    personality_traits: string[];
    service_focus: string[];
    service_boundaries?: Record<string, unknown> | null;
    created_by?: string;
  }) {
    return request<AgentDetail['soul']>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/soul`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  upsertAgentRuntimePolicy(householdId: string, agentId: string, payload: Omit<AgentRuntimePolicy, 'agent_id' | 'updated_at'>) {
    return request<AgentRuntimePolicy>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/runtime-policy`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  upsertAgentMemberCognitions(householdId: string, agentId: string, payload: {
    items: Array<{
      member_id: string;
      display_address?: string | null;
      closeness_level: number;
      service_priority: number;
      communication_style?: string | null;
      care_notes?: Record<string, unknown> | null;
      prompt_notes?: string | null;
    }>;
  }) {
    return request<AgentMemberCognition[]>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/member-cognitions`,
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
    );
  },
  getFamilyQaSuggestions(householdId: string, requesterMemberId?: string, agentId?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (requesterMemberId) {
      params.set('requester_member_id', requesterMemberId);
    }
    if (agentId) {
      params.set('agent_id', agentId);
    }
    return request<FamilyQaSuggestionsResponse>(`/family-qa/suggestions?${params.toString()}`);
  },
  queryFamilyQa(payload: {
    household_id: string;
    requester_member_id?: string;
    agent_id?: string;
    question: string;
    channel?: string;
    context?: Record<string, unknown>;
  }) {
    return request<FamilyQaQueryResponse>('/family-qa/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  createConversationSession(payload: {
    household_id: string;
    requester_member_id?: string;
    active_agent_id?: string;
    session_mode?: 'family_chat' | 'agent_bootstrap' | 'agent_config';
    title?: string;
  }) {
    return request<ConversationSessionDetail>('/conversations/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listConversationSessions(params: {
    household_id: string;
    requester_member_id?: string;
    limit?: number;
  }) {
    const query = new URLSearchParams({
      household_id: params.household_id,
      limit: String(params.limit ?? 50),
    });
    if (params.requester_member_id) {
      query.set('requester_member_id', params.requester_member_id);
    }
    return request<ConversationSessionListResponse>(`/conversations/sessions?${query.toString()}`, undefined, 20000);
  },
  getConversationSession(sessionId: string) {
    return request<ConversationSessionDetail>(`/conversations/sessions/${encodeURIComponent(sessionId)}`, undefined, 20000);
  },
  createConversationTurn(sessionId: string, payload: {
    message: string;
    agent_id?: string;
    channel?: string;
  }) {
    return request<ConversationTurnResponse>(`/conversations/sessions/${encodeURIComponent(sessionId)}/turns`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  confirmConversationMemoryCandidate(candidateId: string) {
    return request<ConversationMemoryCandidateActionResponse>(
      `/conversations/memory-candidates/${encodeURIComponent(candidateId)}/confirm`,
      { method: 'POST' },
    );
  },
  dismissConversationMemoryCandidate(candidateId: string) {
    return request<ConversationMemoryCandidateActionResponse>(
      `/conversations/memory-candidates/${encodeURIComponent(candidateId)}/dismiss`,
      { method: 'POST' },
    );
  },
  confirmConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/confirm`,
      { method: 'POST' },
    );
  },
  dismissConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/dismiss`,
      { method: 'POST' },
    );
  },
  confirmConversationProposal(proposalItemId: string) {
    return request<ConversationProposalExecutionResponse>(
      `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/confirm`,
      { method: 'POST' },
    );
  },
  dismissConversationProposal(proposalItemId: string) {
    return request<ConversationProposalExecutionResponse>(
      `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/dismiss`,
      { method: 'POST' },
    );
  },
  undoConversationAction(actionId: string) {
    return request<ConversationActionExecutionResponse>(
      `/conversations/actions/${encodeURIComponent(actionId)}/undo`,
      { method: 'POST' },
    );
  },
  listMemoryCards(params: { householdId: string; memoryType?: MemoryType; pageSize?: number }) {
    const query = new URLSearchParams({
      household_id: params.householdId,
      page_size: String(params.pageSize ?? 100),
    });
    if (params.memoryType) {
      query.set('memory_type', params.memoryType);
    }
    return request<PaginatedResponse<MemoryCard>>(`/memories/cards?${query.toString()}`);
  },
  createManualMemoryCard(payload: {
    household_id: string;
    memory_type: MemoryCard['memory_type'];
    title: string;
    summary: string;
    content?: Record<string, unknown>;
    status?: MemoryCard['status'];
    visibility?: MemoryCard['visibility'];
    importance?: number;
    confidence?: number;
    subject_member_id?: string | null;
    source_event_id?: string | null;
    dedupe_key?: string | null;
    effective_at?: string | null;
    last_observed_at?: string | null;
    related_members?: { member_id: string; relation_role: 'subject' | 'participant' | 'mentioned' | 'owner' }[];
    reason?: string | null;
  }) {
    return request<MemoryCard>('/memories/cards/manual', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listMemoryCardRevisions(memoryId: string) {
    return request<{ items: MemoryCardRevision[] }>(`/memories/cards/${encodeURIComponent(memoryId)}/revisions`);
  },
  correctMemoryCard(memoryId: string, payload: {
    action: 'correct' | 'invalidate' | 'delete';
    title?: string | null;
    summary?: string | null;
    content?: Record<string, unknown> | null;
    visibility?: MemoryCard['visibility'] | null;
    status?: MemoryCard['status'] | null;
    importance?: number | null;
    confidence?: number | null;
    reason?: string | null;
  }) {
    return request<MemoryCard>(`/memories/cards/${encodeURIComponent(memoryId)}/corrections`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  createReminderTask(payload: Omit<ReminderTask, 'id' | 'version' | 'updated_at'>) {
    return request<ReminderTask>('/reminders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  listScheduledTasks(params: {
    household_id: string;
    owner_scope?: 'household' | 'member';
    owner_member_id?: string;
    enabled?: boolean;
    trigger_type?: 'schedule' | 'heartbeat';
    target_type?: 'plugin_job' | 'agent_reminder' | 'system_notice';
    status?: 'active' | 'paused' | 'error' | 'invalid_dependency';
  }) {
    const query = new URLSearchParams({ household_id: params.household_id });
    if (params.owner_scope) query.set('owner_scope', params.owner_scope);
    if (params.owner_member_id) query.set('owner_member_id', params.owner_member_id);
    if (params.enabled !== undefined) query.set('enabled', String(params.enabled));
    if (params.trigger_type) query.set('trigger_type', params.trigger_type);
    if (params.target_type) query.set('target_type', params.target_type);
    if (params.status) query.set('status', params.status);
    return request<ScheduledTaskDefinition[]>(`/scheduled-tasks?${query.toString()}`);
  },
  getScheduledTask(taskId: string) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}`);
  },
  createScheduledTask(payload: ScheduledTaskDefinitionCreate) {
    return request<ScheduledTaskDefinition>('/scheduled-tasks', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  updateScheduledTask(taskId: string, payload: ScheduledTaskDefinitionUpdate) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  enableScheduledTask(taskId: string) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}/enable`, {
      method: 'POST',
    });
  },
  disableScheduledTask(taskId: string) {
    return request<ScheduledTaskDefinition>(`/scheduled-tasks/${encodeURIComponent(taskId)}/disable`, {
      method: 'POST',
    });
  },
  listScheduledTaskRuns(params: {
    household_id: string;
    task_definition_id?: string;
    owner_scope?: 'household' | 'member';
    owner_member_id?: string;
    status?: 'queued' | 'dispatching' | 'succeeded' | 'failed' | 'skipped' | 'suppressed';
    created_from?: string;
    created_to?: string;
    limit?: number;
  }) {
    const query = new URLSearchParams({ household_id: params.household_id });
    if (params.task_definition_id) query.set('task_definition_id', params.task_definition_id);
    if (params.owner_scope) query.set('owner_scope', params.owner_scope);
    if (params.owner_member_id) query.set('owner_member_id', params.owner_member_id);
    if (params.status) query.set('status', params.status);
    if (params.created_from) query.set('created_from', params.created_from);
    if (params.created_to) query.set('created_to', params.created_to);
    if (params.limit) query.set('limit', String(params.limit));
    return request<ScheduledTaskRun[]>(`/scheduled-task-runs?${query.toString()}`);
  },

  deleteScheduledTask(taskId: string) {
    return request<void>(`/scheduled-tasks/${encodeURIComponent(taskId)}`, {
      method: 'DELETE',
    });
  },
};
