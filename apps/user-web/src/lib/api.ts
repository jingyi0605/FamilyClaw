import type {
  ContextConfigRead,
  ContextOverviewRead,
  Device,
  FamilyQaQueryResponse,
  FamilyQaSuggestionsResponse,
  HomeAssistantSyncResponse,
  Household,
  MemoryCard,
  MemoryCardRevision,
  MemoryType,
  MemberPreference,
  MemberRelationship,
  Member,
  PaginatedResponse,
  ReminderTask,
  ReminderOverviewRead,
  Room,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const ACTOR_ROLE = import.meta.env.VITE_API_ACTOR_ROLE ?? 'admin';
const ACTOR_ID = import.meta.env.VITE_API_ACTOR_ID;

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
  }

  return fallbackMessage;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  headers.set('Content-Type', 'application/json');
  headers.set('X-Actor-Role', ACTOR_ROLE);
  if (ACTOR_ID) {
    headers.set('X-Actor-Id', ACTOR_ID);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  const contentType = response.headers.get('content-type') ?? '';
  const isJsonResponse = contentType.includes('application/json');

  if (!response.ok) {
    const payload = isJsonResponse
      ? await response.json().catch(() => null)
      : await response.text().catch(() => '');
    throw new ApiError(
      response.status,
      resolveErrorMessage(payload, `Request failed with status ${response.status}`),
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
    return request<PaginatedResponse<Household>>('/households?page_size=100');
  },
  getHousehold(householdId: string) {
    return request<Household>(`/households/${encodeURIComponent(householdId)}`);
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
  createMember(payload: {
    household_id: string;
    name: string;
    nickname?: string | null;
    gender?: 'male' | 'female' | null;
    role: Member['role'];
    age_group?: Member['age_group'];
    phone?: string | null;
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
  syncHomeAssistant(householdId: string) {
    return request<HomeAssistantSyncResponse>('/devices/sync/ha', {
      method: 'POST',
      body: JSON.stringify({ household_id: householdId }),
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
  getFamilyQaSuggestions(householdId: string, requesterMemberId?: string) {
    const params = new URLSearchParams({ household_id: householdId });
    if (requesterMemberId) {
      params.set('requester_member_id', requesterMemberId);
    }
    return request<FamilyQaSuggestionsResponse>(`/family-qa/suggestions?${params.toString()}`);
  },
  queryFamilyQa(payload: { household_id: string; requester_member_id?: string; question: string; channel?: string; context?: Record<string, unknown> }) {
    return request<FamilyQaQueryResponse>('/family-qa/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
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
};
