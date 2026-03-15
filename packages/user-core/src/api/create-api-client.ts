import {
  ContextConfigRead,
  ContextOverviewRead,
  Device,
  Household,
  HouseholdSetupStatus,
  LoginResponse,
  Member,
  MemberPreference,
  MemberRelationship,
  PaginatedResponse,
  PluginLocaleListResponse,
  RegionNode,
  RegionSelection,
  ReminderOverviewRead,
  Room,
} from '../domain/types';

export type RequestClient = <T>(
  path: string,
  init?: RequestInit,
  timeoutMs?: number,
) => Promise<T>;

export type ApiClientConfig = {
  baseUrl?: string;
  timeoutMs?: number;
  credentials?: RequestCredentials;
  fetchImpl?: typeof fetch;
};

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

export function createRequestClient(config: ApiClientConfig = {}): RequestClient {
  const baseUrl = config.baseUrl ?? '/api/v1';
  const timeoutMs = config.timeoutMs ?? 8000;
  const fetchImpl = config.fetchImpl ?? fetch;
  const credentials = config.credentials ?? 'include';

  return async function request<T>(path: string, init?: RequestInit, nextTimeoutMs?: number): Promise<T> {
    const headers = new Headers(init?.headers ?? {});
    if (init?.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const controller = new AbortController();
    const timeoutId = globalThis.setTimeout(() => controller.abort(), nextTimeoutMs ?? timeoutMs);

    let response: Response;

    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        ...init,
        credentials,
        headers,
        signal: controller.signal,
      });
    } catch (error) {
      globalThis.clearTimeout(timeoutId);
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(0, '请求超时，请确认后端服务是否可用', null);
      }
      throw error;
    }

    globalThis.clearTimeout(timeoutId);

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
  };
}

export function createCoreApiClient(request: RequestClient) {
  return {
    login(payload: { username: string; password: string }) {
      return request<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
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
    getAuthMe() {
      return request<LoginResponse>('/auth/me');
    },
    logout() {
      return request<void>('/auth/logout', {
        method: 'POST',
      });
    },
    listHouseholds() {
      return request<PaginatedResponse<Household>>('/households?page_size=100');
    },
    getHousehold(householdId: string) {
      return request<Household>(`/households/${encodeURIComponent(householdId)}`);
    },
    createHousehold(payload: Pick<Household, 'name' | 'timezone' | 'locale'> & {
      city?: string | null;
      region_selection?: RegionSelection | null;
    }) {
      return request<Household>('/households', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    updateHousehold(
      householdId: string,
      payload: Partial<Pick<Household, 'name' | 'city' | 'timezone' | 'locale'> & { region_selection: RegionSelection | null }>,
    ) {
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
      if (params.admin_level) {
        search.set('admin_level', params.admin_level);
      }
      if (params.parent_region_code) {
        search.set('parent_region_code', params.parent_region_code);
      }
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
      if (params.admin_level) {
        search.set('admin_level', params.admin_level);
      }
      if (params.parent_region_code) {
        search.set('parent_region_code', params.parent_region_code);
      }
      return request<RegionNode[]>(`/regions/search?${search.toString()}`);
    },
    getHouseholdSetupStatus(householdId: string) {
      return request<HouseholdSetupStatus>(`/households/${encodeURIComponent(householdId)}/setup-status`);
    },
    listRooms(householdId: string) {
      return request<PaginatedResponse<Room>>(`/rooms?household_id=${encodeURIComponent(householdId)}&page_size=100`);
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
    listMembers(householdId: string) {
      return request<PaginatedResponse<Member>>(`/members?household_id=${encodeURIComponent(householdId)}&page_size=100`);
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
    listMemberRelationships(householdId: string) {
      return request<PaginatedResponse<MemberRelationship>>(
        `/member-relationships?household_id=${encodeURIComponent(householdId)}&page_size=100`,
      );
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
    getMemberPreferences(memberId: string) {
      return request<MemberPreference>(`/member-preferences/${encodeURIComponent(memberId)}`);
    },
    upsertMemberPreferences(memberId: string, payload: Omit<MemberPreference, 'member_id' | 'updated_at'>) {
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
    getContextOverview(householdId: string) {
      return request<ContextOverviewRead>(`/context/overview?household_id=${encodeURIComponent(householdId)}`);
    },
    getContextConfig(householdId: string) {
      return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`);
    },
    updateContextConfig(
      householdId: string,
      payload: Omit<ContextConfigRead, 'household_id' | 'version' | 'updated_by' | 'updated_at'>,
    ) {
      return request<ContextConfigRead>(`/context/configs/${encodeURIComponent(householdId)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    },
    getReminderOverview(householdId: string) {
      return request<ReminderOverviewRead>(`/reminders/overview?household_id=${encodeURIComponent(householdId)}`);
    },
    listHouseholdLocales(householdId: string) {
      return request<PluginLocaleListResponse>(`/ai-config/${encodeURIComponent(householdId)}/locales`);
    },
  };
}

export type CoreApiClient = ReturnType<typeof createCoreApiClient>;
