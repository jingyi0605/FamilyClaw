import type {
  AuditLog,
  ContextConfigRead,
  ContextConfigUpsertPayload,
  ContextOverviewRead,
  Device,
  HomeAssistantSyncResponse,
  Household,
  Member,
  MemberPermissionListResponse,
  MemberPermissionRule,
  MemberPreference,
  MemberRelationship,
  PaginatedResponse,
  Room,
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
};
