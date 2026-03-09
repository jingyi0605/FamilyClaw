import type {
  AuditLog,
  Device,
  HomeAssistantSyncResponse,
  Household,
  Member,
  PaginatedResponse,
  Room,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Actor-Role": "admin",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
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
  syncHomeAssistant(householdId: string) {
    return request<HomeAssistantSyncResponse>("/devices/sync/ha", {
      method: "POST",
      body: JSON.stringify({ household_id: householdId }),
    });
  },
  listAuditLogs(householdId: string) {
    return request<PaginatedResponse<AuditLog>>(
      `/audit-logs?household_id=${encodeURIComponent(householdId)}`,
    );
  },
};

