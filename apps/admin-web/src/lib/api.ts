import type {
  AgentDetail,
  AgentListResponse,
  AgentMemberCognition,
  AgentMemberCognitionsUpsertPayload,
  AgentRuntimePolicy,
  AgentRuntimePolicyUpsertPayload,
  AgentSoulProfile,
  AgentSoulProfileUpsertPayload,
  AiCallLog,
  AiCapabilityRoute,
  AiCapabilityRouteUpsertPayload,
  AiGatewayInvokeResponse,
  AiProviderProfile,
  AiProviderProfileCreatePayload,
  AiProviderProfileUpdatePayload,
  AuditLog,
  ContextConfigRead,
  ContextConfigUpsertPayload,
  ContextOverviewRead,
  Device,
  FamilyQaQueryResponse,
  FamilyQaSuggestionsResponse,
  HomeAssistantConfig,
  HomeAssistantRoomCandidatesResponse,
  HomeAssistantRoomSyncResponse,
  HomeAssistantSyncResponse,
  Household,
  MemoryCard,
  MemoryContextBundleRead,
  MemoryCardRevision,
  MemoryDebugOverviewRead,
  MemoryEventRecord,
  MemoryEventWriteResponse,
  MemoryHotSummaryRead,
  MemoryQueryResponse,
  Member,
  MemberPermissionListResponse,
  MemberPermissionRule,
  MemberPreference,
  MemberRelationship,
  PaginatedResponse,
  ReminderAckResponse,
  ReminderOverviewRead,
  ReminderSchedulerDispatchResponse,
  ReminderTask,
  ReminderTriggerResponse,
  Room,
  SceneExecution,
  SceneExecutionDetailRead,
  ScenePreviewResponse,
  SceneTemplate,
  SceneTemplatePresetItem,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function resolveErrorMessage(payload: unknown, fallbackMessage: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }

  return fallbackMessage;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Actor-Role": "admin",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJsonResponse = contentType.includes("application/json");

  if (!response.ok) {
    const payload = isJsonResponse
      ? await response.json().catch(() => null)
      : await response.text().catch(() => "");
    const fallbackMessage = `Request failed with status ${response.status}`;
    throw new ApiError(
      response.status,
      resolveErrorMessage(payload, fallbackMessage),
      payload,
    );
  }

  if (!isJsonResponse) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  listHouseholds() {
    return request<PaginatedResponse<Household>>("/households");
  },
  createHousehold(payload: Pick<Household, "name" | "timezone" | "locale">) {
    return request<Household>("/households", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getHousehold(householdId: string) {
    return request<Household>(`/households/${householdId}`);
  },
  listMembers(householdId: string) {
    return request<PaginatedResponse<Member>>(
      `/members?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  createMember(payload: {
    household_id: string;
    name: string;
    nickname?: string | null;
    role: Member["role"];
    age_group?: Member["age_group"];
    phone?: string | null;
    guardian_member_id?: string | null;
  }) {
    return request<Member>("/members", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateMember(memberId: string, payload: Partial<Member>) {
    return request<Member>(`/members/${memberId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  listMemberRelationships(params: {
    householdId: string;
    sourceMemberId?: string;
    targetMemberId?: string;
    relationType?: MemberRelationship["relation_type"];
  }) {
    const searchParams = new URLSearchParams({
      household_id: params.householdId,
    });

    if (params.sourceMemberId) {
      searchParams.set("source_member_id", params.sourceMemberId);
    }
    if (params.targetMemberId) {
      searchParams.set("target_member_id", params.targetMemberId);
    }
    if (params.relationType) {
      searchParams.set("relation_type", params.relationType);
    }

    return request<PaginatedResponse<MemberRelationship>>(
      `/member-relationships?${searchParams.toString()}`,
    );
  },
  createMemberRelationship(payload: {
    household_id: string;
    source_member_id: string;
    target_member_id: string;
    relation_type: MemberRelationship["relation_type"];
    visibility_scope: MemberRelationship["visibility_scope"];
    delegation_scope: MemberRelationship["delegation_scope"];
  }) {
    return request<MemberRelationship>("/member-relationships", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getMemberPreferences(memberId: string) {
    return request<MemberPreference>(`/member-preferences/${memberId}`);
  },
  upsertMemberPreferences(
    memberId: string,
    payload: Omit<MemberPreference, "member_id" | "updated_at">,
  ) {
    return request<MemberPreference>(`/member-preferences/${memberId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  getMemberPermissions(memberId: string) {
    return request<MemberPermissionListResponse>(`/member-permissions/${memberId}`);
  },
  replaceMemberPermissions(memberId: string, payload: { rules: MemberPermissionRule[] }) {
    return request<MemberPermissionListResponse>(`/member-permissions/${memberId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  listRooms(householdId: string) {
    return request<PaginatedResponse<Room>>(
      `/rooms?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  createRoom(payload: {
    household_id: string;
    name: string;
    room_type: Room["room_type"];
    privacy_level: Room["privacy_level"];
  }) {
    return request<Room>("/rooms", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateRoom(roomId: string, payload: Partial<Pick<Room, "name" | "room_type" | "privacy_level">>) {
    return request<Room>(`/rooms/${encodeURIComponent(roomId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteRoom(roomId: string) {
    return request<void>(`/rooms/${encodeURIComponent(roomId)}`, {
      method: "DELETE",
    });
  },
  listDevices(householdId: string) {
    return request<PaginatedResponse<Device>>(
      `/devices?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  updateDevice(deviceId: string, payload: Partial<Device>) {
    return request<Device>(`/devices/${deviceId}`, {
      method: "PATCH",
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
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  syncHomeAssistant(householdId: string) {
    return request<HomeAssistantSyncResponse>("/devices/sync/ha", {
      method: "POST",
      body: JSON.stringify({ household_id: householdId }),
    });
  },
  syncHomeAssistantRooms(householdId: string) {
    return request<HomeAssistantRoomSyncResponse>("/devices/rooms/sync/ha", {
      method: "POST",
      body: JSON.stringify({ household_id: householdId, room_names: [] }),
    });
  },
  listHomeAssistantRoomCandidates(householdId: string) {
    return request<HomeAssistantRoomCandidatesResponse>(`/devices/rooms/ha-candidates/${encodeURIComponent(householdId)}`);
  },
  syncSelectedHomeAssistantRooms(householdId: string, roomNames: string[]) {
    return request<HomeAssistantRoomSyncResponse>("/devices/rooms/sync/ha", {
      method: "POST",
      body: JSON.stringify({ household_id: householdId, room_names: roomNames }),
    });
  },
  listAuditLogs(householdId: string) {
    return request<PaginatedResponse<AuditLog>>(
      `/audit-logs?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  getContextOverview(householdId: string) {
    return request<ContextOverviewRead>(
      `/context/overview?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  getContextConfig(householdId: string) {
    return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`);
  },
  updateContextConfig(householdId: string, payload: ContextConfigUpsertPayload) {
    return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  queryFamilyQa(payload: {
    household_id: string;
    requester_member_id?: string | null;
    question: string;
    channel?: string;
    context?: Record<string, unknown>;
  }) {
    return request<FamilyQaQueryResponse>("/family-qa/query", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listFamilyQaSuggestions(householdId: string, requesterMemberId?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (requesterMemberId) {
      params.set("requester_member_id", requesterMemberId);
    }
    return request<FamilyQaSuggestionsResponse>(`/family-qa/suggestions?${params.toString()}`);
  },
  getMemoryDebugOverview(householdId: string) {
    return request<MemoryDebugOverviewRead>(
      `/memories/overview?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  listMemoryEvents(householdId: string, processingStatus?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (processingStatus) {
      params.set("processing_status", processingStatus);
    }
    return request<PaginatedResponse<MemoryEventRecord>>(`/memories/events?${params.toString()}`);
  },
  ingestMemoryEvent(payload: {
    household_id: string;
    event_type: string;
    source_type: string;
    source_ref?: string | null;
    subject_member_id?: string | null;
    room_id?: string | null;
    payload?: Record<string, unknown>;
    dedupe_key?: string | null;
    generate_memory_card?: boolean;
    occurred_at?: string | null;
  }) {
    return request<MemoryEventWriteResponse>("/memories/events", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listMemoryCards(householdId: string, memoryType?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (memoryType) {
      params.set("memory_type", memoryType);
    }
    return request<PaginatedResponse<MemoryCard>>(`/memories/cards?${params.toString()}`);
  },
  queryMemoryCards(payload: {
    household_id: string;
    requester_member_id?: string | null;
    member_id?: string | null;
    memory_type?: MemoryCard["memory_type"] | null;
    status?: MemoryCard["status"] | null;
    visibility?: MemoryCard["visibility"] | null;
    query?: string | null;
    limit?: number;
  }) {
    return request<MemoryQueryResponse>("/memories/query", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getMemoryHotSummary(householdId: string, requesterMemberId?: string | null) {
    const params = new URLSearchParams({ household_id: householdId });
    if (requesterMemberId) {
      params.set("requester_member_id", requesterMemberId);
    }
    return request<MemoryHotSummaryRead>(`/memories/hot-summary?${params.toString()}`);
  },
  previewMemoryContextBundle(payload: {
    household_id: string;
    requester_member_id?: string | null;
    capability?: string;
    question?: string | null;
  }) {
    return request<MemoryContextBundleRead>("/memories/context-bundle/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  createManualMemoryCard(payload: {
    household_id: string;
    memory_type: MemoryCard["memory_type"];
    title: string;
    summary: string;
    content?: Record<string, unknown>;
    status?: MemoryCard["status"];
    visibility?: MemoryCard["visibility"];
    importance?: number;
    confidence?: number;
    subject_member_id?: string | null;
    source_event_id?: string | null;
    dedupe_key?: string | null;
    effective_at?: string | null;
    last_observed_at?: string | null;
    related_members?: { member_id: string; relation_role: "subject" | "participant" | "mentioned" | "owner" }[];
    reason?: string | null;
  }) {
    return request<MemoryCard>("/memories/cards/manual", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listMemoryCardRevisions(memoryId: string) {
    return request<{ items: MemoryCardRevision[] }>(`/memories/cards/${encodeURIComponent(memoryId)}/revisions`);
  },
  correctMemoryCard(
    memoryId: string,
    payload: {
      action: "correct" | "invalidate" | "delete";
      title?: string | null;
      summary?: string | null;
      content?: Record<string, unknown> | null;
      visibility?: MemoryCard["visibility"] | null;
      status?: MemoryCard["status"] | null;
      importance?: number | null;
      confidence?: number | null;
      reason?: string | null;
    },
  ) {
    return request<MemoryCard>(`/memories/cards/${encodeURIComponent(memoryId)}/corrections`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listReminderTasks(householdId: string, enabled?: boolean) {
    const params = new URLSearchParams({ household_id: householdId });
    if (enabled !== undefined) {
      params.set("enabled", String(enabled));
    }
    return request<ReminderTask[]>(`/reminders?${params.toString()}`);
  },
  createReminderTask(payload: Omit<ReminderTask, "id" | "version" | "updated_at">) {
    return request<ReminderTask>("/reminders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateReminderTask(reminderId: string, payload: Partial<ReminderTask>) {
    return request<ReminderTask>(`/reminders/${reminderId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  deleteReminderTask(reminderId: string) {
    return request<void>(`/reminders/${reminderId}`, {
      method: "DELETE",
    });
  },
  getReminderOverview(householdId: string) {
    return request<ReminderOverviewRead>(`/reminders/overview?household_id=${encodeURIComponent(householdId)}`);
  },
  triggerReminder(reminderId: string) {
    return request<ReminderTriggerResponse>(`/reminders/${reminderId}/trigger`, {
      method: "POST",
    });
  },
  dispatchReminderScheduler(householdId: string) {
    return request<ReminderSchedulerDispatchResponse>(
      `/reminders/scheduler/dispatch?household_id=${encodeURIComponent(householdId)}`,
      {
        method: "POST",
      },
    );
  },
  acknowledgeReminderRun(runId: string, payload: {
    run_id: string;
    member_id?: string | null;
    action: "heard" | "done" | "dismissed" | "delegated";
    note?: string | null;
  }) {
    return request<ReminderAckResponse>(`/reminder-runs/${runId}/ack`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listSceneTemplatePresets(householdId: string) {
    return request<SceneTemplatePresetItem[]>(
      `/scenes/template-presets?household_id=${encodeURIComponent(householdId)}`,
    );
  },
  listSceneTemplates(householdId: string, enabled?: boolean) {
    const params = new URLSearchParams({ household_id: householdId });
    if (enabled !== undefined) {
      params.set("enabled", String(enabled));
    }
    return request<SceneTemplate[]>(`/scenes/templates?${params.toString()}`);
  },
  upsertSceneTemplate(templateCode: string, payload: Omit<SceneTemplate, "id" | "version" | "updated_at"> & { updated_by?: string | null }) {
    return request<SceneTemplate>(`/scenes/templates/${encodeURIComponent(templateCode)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  previewSceneTemplate(templateCode: string, payload: {
    household_id: string;
    trigger_source?: string;
    trigger_payload?: Record<string, unknown>;
    confirm_high_risk?: boolean;
  }) {
    return request<ScenePreviewResponse>(`/scenes/templates/${encodeURIComponent(templateCode)}/preview`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  triggerSceneTemplate(templateCode: string, payload: {
    household_id: string;
    trigger_source?: string;
    trigger_payload?: Record<string, unknown>;
    confirm_high_risk?: boolean;
    updated_by?: string | null;
  }) {
    return request<SceneExecutionDetailRead>(`/scenes/templates/${encodeURIComponent(templateCode)}/trigger`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  listSceneExecutions(householdId: string) {
    return request<SceneExecution[]>(`/scenes/executions?household_id=${encodeURIComponent(householdId)}`);
  },
  getSceneExecutionDetail(executionId: string) {
    return request<SceneExecutionDetailRead>(`/scenes/executions/${encodeURIComponent(executionId)}`);
  },
  getAiRuntimeDefaults() {
    return request<Record<string, unknown>>("/ai/runtime-defaults");
  },
  listAgents(householdId: string) {
    return request<AgentListResponse>(`/ai-config/${encodeURIComponent(householdId)}`);
  },
  getAgentDetail(householdId: string, agentId: string) {
    return request<AgentDetail>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`);
  },
  updateAgentSoul(householdId: string, agentId: string, payload: AgentSoulProfileUpsertPayload) {
    return request<AgentSoulProfile>(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/soul`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  updateAgentMemberCognitions(householdId: string, agentId: string, payload: AgentMemberCognitionsUpsertPayload) {
    return request<AgentMemberCognition[]>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/member-cognitions`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  },
  updateAgentRuntimePolicy(householdId: string, agentId: string, payload: AgentRuntimePolicyUpsertPayload) {
    return request<AgentRuntimePolicy>(
      `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/runtime-policy`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  },
  listAiProviders(enabled?: boolean) {
    const params = new URLSearchParams();
    if (enabled !== undefined) {
      params.set("enabled", String(enabled));
    }
    return request<AiProviderProfile[]>(`/ai/providers${params.toString() ? `?${params.toString()}` : ""}`);
  },
  listAiRoutes(householdId?: string) {
    const params = new URLSearchParams();
    if (householdId) {
      params.set("household_id", householdId);
    }
    return request<AiCapabilityRoute[]>(`/ai/routes${params.toString() ? `?${params.toString()}` : ""}`);
  },
  listAiCallLogs(householdId?: string) {
    const params = new URLSearchParams();
    if (householdId) {
      params.set("household_id", householdId);
    }
    return request<AiCallLog[]>(`/ai/call-logs${params.toString() ? `?${params.toString()}` : ""}`);
  },
  createAiProvider(payload: AiProviderProfileCreatePayload) {
    return request<AiProviderProfile>("/ai/providers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateAiProvider(providerProfileId: string, payload: AiProviderProfileUpdatePayload) {
    return request<AiProviderProfile>(`/ai/providers/${encodeURIComponent(providerProfileId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  upsertAiRoute(capability: string, payload: AiCapabilityRouteUpsertPayload) {
    return request<AiCapabilityRoute>(`/ai/routes/${encodeURIComponent(capability)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  invokeAiPreview(payload: {
    capability: string;
    household_id?: string | null;
    requester_member_id?: string | null;
    payload: Record<string, unknown>;
  }) {
    return request<AiGatewayInvokeResponse>("/ai/invoke-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
