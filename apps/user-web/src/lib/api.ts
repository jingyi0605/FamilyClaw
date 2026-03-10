import type {
  ContextConfigRead,
  ContextOverviewRead,
  Device,
  HomeAssistantSyncResponse,
  Household,
  MemberPreference,
  MemberRelationship,
  Member,
  PaginatedResponse,
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
    return request<PaginatedResponse<Household>>('/households');
  },
  getHousehold(householdId: string) {
    return request<Household>(`/households/${encodeURIComponent(householdId)}`);
  },
  listRooms(householdId: string) {
    return request<PaginatedResponse<Room>>(`/rooms?household_id=${encodeURIComponent(householdId)}`);
  },
  listMembers(householdId: string) {
    return request<PaginatedResponse<Member>>(`/members?household_id=${encodeURIComponent(householdId)}`);
  },
  listMemberRelationships(householdId: string) {
    return request<PaginatedResponse<MemberRelationship>>(`/member-relationships?household_id=${encodeURIComponent(householdId)}`);
  },
  getMemberPreferences(memberId: string) {
    return request<MemberPreference>(`/member-preferences/${encodeURIComponent(memberId)}`);
  },
  listDevices(householdId: string) {
    return request<PaginatedResponse<Device>>(`/devices?household_id=${encodeURIComponent(householdId)}`);
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
};
