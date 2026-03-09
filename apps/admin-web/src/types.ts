export type Household = {
  id: string;
  name: string;
  timezone: string;
  locale: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Member = {
  id: string;
  household_id: string;
  name: string;
  nickname: string | null;
  role: "admin" | "adult" | "child" | "elder" | "guest";
  age_group: "toddler" | "child" | "teen" | "adult" | "elder" | null;
  birthday: string | null;
  phone: string | null;
  status: "active" | "inactive";
  guardian_member_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Room = {
  id: string;
  household_id: string;
  name: string;
  room_type: "living_room" | "bedroom" | "study" | "entrance";
  privacy_level: "public" | "private" | "sensitive";
  created_at: string;
};

export type Device = {
  id: string;
  household_id: string;
  room_id: string | null;
  name: string;
  device_type: "light" | "ac" | "curtain" | "speaker" | "camera" | "sensor" | "lock";
  vendor: "xiaomi" | "ha" | "other";
  status: "active" | "offline" | "inactive";
  controllable: boolean;
  created_at: string;
  updated_at: string;
};

export type AuditLog = {
  id: string;
  household_id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  result: string;
  details: string | null;
  created_at: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type HomeAssistantSyncResponse = {
  household_id: string;
  created_devices: number;
  updated_devices: number;
  created_bindings: number;
  skipped_entities: number;
  failed_entities: number;
  devices: Device[];
  failures: { entity_id: string | null; reason: string }[];
};

