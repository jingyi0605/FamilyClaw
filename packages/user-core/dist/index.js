export class ApiError extends Error {
  constructor(status, message, payload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

function resolveErrorMessage(payload, fallbackMessage) {
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }

  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = payload.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      const nestedDetail = detail.detail;
      if (typeof nestedDetail === 'string' && nestedDetail.trim()) {
        return nestedDetail;
      }
    }
  }

  return fallbackMessage;
}

async function readResponsePayload(response, isJsonResponse) {
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
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function createRequestClient(config = {}) {
  const baseUrl = config.baseUrl ?? '/api/v1';
  const timeoutMs = config.timeoutMs ?? 8000;
  const fetchImpl = config.fetchImpl ?? fetch;
  const credentials = config.credentials ?? 'include';

  return async function request(path, init, nextTimeoutMs) {
    const headers = new Headers(init?.headers ?? {});
    if (init?.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const controller = new AbortController();
    const timeoutId = globalThis.setTimeout(() => controller.abort(), nextTimeoutMs ?? timeoutMs);

    let response;

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
      return undefined;
    }

    return readResponsePayload(response, isJsonResponse);
  };
}

export function createCoreApiClient(request) {
  return {
    login(payload) {
      return request('/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    completeBootstrapAccount(payload) {
      return request('/auth/bootstrap/complete', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    getAuthMe() {
      return request('/auth/me');
    },
    logout() {
      return request('/auth/logout', {
        method: 'POST',
      });
    },
    listHouseholds() {
      return request('/households?page_size=100');
    },
    getHousehold(householdId) {
      return request(`/households/${encodeURIComponent(householdId)}`);
    },
    createHousehold(payload) {
      return request('/households', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    updateHousehold(householdId, payload) {
      return request(`/households/${encodeURIComponent(householdId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
    listRegionCatalog(params) {
      const search = new URLSearchParams();
      search.set('provider_code', params.provider_code);
      search.set('country_code', params.country_code);
      if (params.admin_level) {
        search.set('admin_level', params.admin_level);
      }
      if (params.parent_region_code) {
        search.set('parent_region_code', params.parent_region_code);
      }
      return request(`/regions/catalog?${search.toString()}`);
    },
    searchRegions(params) {
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
      return request(`/regions/search?${search.toString()}`);
    },
    getHouseholdSetupStatus(householdId) {
      return request(`/households/${encodeURIComponent(householdId)}/setup-status`);
    },
    listRooms(householdId) {
      return request(`/rooms?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    createRoom(payload) {
      return request('/rooms', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    updateRoom(roomId, payload) {
      return request(`/rooms/${encodeURIComponent(roomId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
    deleteRoom(roomId) {
      return request(`/rooms/${encodeURIComponent(roomId)}`, {
        method: 'DELETE',
      });
    },
    listMembers(householdId) {
      return request(`/members?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    createMember(payload) {
      return request('/members', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    updateMember(memberId, payload) {
      return request(`/members/${encodeURIComponent(memberId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
    listMemberRelationships(householdId) {
      return request(`/member-relationships?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    createMemberRelationship(payload) {
      return request('/member-relationships', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    deleteMemberRelationship(relationshipId) {
      return request(`/member-relationships/${encodeURIComponent(relationshipId)}`, {
        method: 'DELETE',
      });
    },
    getMemberPreferences(memberId) {
      return request(`/member-preferences/${encodeURIComponent(memberId)}`);
    },
    upsertMemberPreferences(memberId, payload) {
      return request(`/member-preferences/${encodeURIComponent(memberId)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    },
    listDevices(householdId) {
      return request(`/devices?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    updateDevice(deviceId, payload) {
      return request(`/devices/${encodeURIComponent(deviceId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
    getContextOverview(householdId) {
      return request(`/context/overview?household_id=${encodeURIComponent(householdId)}`);
    },
    getContextConfig(householdId) {
      return request(`/context/configs/${encodeURIComponent(householdId)}`);
    },
    updateContextConfig(householdId, payload) {
      return request(`/context/configs/${encodeURIComponent(householdId)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    },
    getReminderOverview(householdId) {
      return request(`/reminders/overview?household_id=${encodeURIComponent(householdId)}`);
    },
    listHouseholdLocales(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/locales`);
    },
  };
}

export const CLIENT_ONLY_STORAGE_PREFIXES = [
  'familyclaw-conversation-sessions',
  'familyclaw-assistant-sessions',
];

export async function clearClientOnlyStorage(storage, prefixes = CLIENT_ONLY_STORAGE_PREFIXES) {
  if (!storage.keys) {
    return;
  }

  const keys = await storage.keys();
  await Promise.all(
    keys
      .filter(key => prefixes.some(prefix => key.startsWith(prefix)))
      .map(key => storage.removeItem(key)),
  );
}

export const HOUSEHOLD_STORAGE_KEY = 'familyclaw-household';

export async function getStoredHouseholdId(storage, storageKey = HOUSEHOLD_STORAGE_KEY) {
  return (await storage.getItem(storageKey)) ?? '';
}

export async function persistHouseholdId(storage, householdId, storageKey = HOUSEHOLD_STORAGE_KEY) {
  if (!householdId) {
    await storage.removeItem(storageKey);
    return;
  }

  await storage.setItem(storageKey, householdId);
}

export function toHouseholdSummary(household) {
  return {
    id: household.id,
    name: household.name,
    city: household.city,
    timezone: household.timezone,
    locale: household.locale,
    status: household.status,
    region: household.region,
  };
}

export const LOCALE_STORAGE_KEY = 'familyclaw-locale';
export const DEFAULT_LOCALE_ID = 'zh-CN';

const BUILTIN_LOCALE_DEFINITIONS = [
  {
    id: 'zh-CN',
    label: '简体中文',
    nativeLabel: '简体中文',
    flag: 'CN',
    source: 'builtin',
    sourceType: 'builtin',
  },
  {
    id: 'en-US',
    label: 'English',
    nativeLabel: 'English',
    flag: 'US',
    fallback: 'zh-CN',
    source: 'builtin',
    sourceType: 'builtin',
  },
];

function normalizeLocaleLookup(value) {
  return (value ?? '').trim().toLowerCase();
}

function sanitizeLocaleId(value) {
  return (value ?? '').trim();
}

export function listBuiltinLocaleDefinitions() {
  return BUILTIN_LOCALE_DEFINITIONS.map(definition => ({ ...definition }));
}

export function buildLocaleDefinitions(pluginLocales = []) {
  const registry = new Map();

  for (const definition of BUILTIN_LOCALE_DEFINITIONS) {
    registry.set(definition.id, { ...definition });
  }

  for (const pluginLocale of pluginLocales) {
    const id = sanitizeLocaleId(pluginLocale.locale_id);
    if (!id) {
      continue;
    }

    registry.set(id, {
      id,
      label: pluginLocale.label || id,
      nativeLabel: pluginLocale.native_label || pluginLocale.label || id,
      fallback: sanitizeLocaleId(pluginLocale.fallback) || undefined,
      messages: pluginLocale.messages,
      source: 'plugin',
      sourceType: pluginLocale.source_type,
      pluginId: pluginLocale.plugin_id,
      overriddenPluginIds: pluginLocale.overridden_plugin_ids,
    });
  }

  return Array.from(registry.values());
}

export function formatLocaleOptionLabel(definition) {
  return `${definition.nativeLabel} (${definition.id})`;
}

export function getLocaleSourceLabel(definition) {
  if (definition.source === 'builtin' || definition.sourceType === 'builtin') {
    return 'builtin';
  }
  if (definition.sourceType === 'official') {
    return 'official';
  }
  return 'third_party';
}

export function getLocaleDefinition(definitions, locale) {
  if (!locale) {
    return undefined;
  }

  const normalized = normalizeLocaleLookup(locale);
  return definitions.find(item => normalizeLocaleLookup(item.id) === normalized);
}

export function isRegisteredLocale(definitions, locale) {
  return Boolean(getLocaleDefinition(definitions, locale));
}

export function resolveSupportedLocale(
  locale,
  definitions = BUILTIN_LOCALE_DEFINITIONS,
  fallback = DEFAULT_LOCALE_ID,
) {
  const matched = getLocaleDefinition(definitions, locale);
  if (matched) {
    return matched.id;
  }

  const normalized = normalizeLocaleLookup(locale);
  if (!normalized) {
    return fallback;
  }

  if (
    (normalized.includes('hant')
      || normalized.startsWith('zh-tw')
      || normalized.startsWith('zh-hk')
      || normalized.startsWith('zh-mo'))
    && isRegisteredLocale(definitions, 'zh-TW')
  ) {
    return 'zh-TW';
  }

  if (normalized.startsWith('zh') && isRegisteredLocale(definitions, 'zh-CN')) {
    return 'zh-CN';
  }

  const languageCode = normalized.split(/[-_]/)[0];
  const languageMatched = definitions.find(item => normalizeLocaleLookup(item.id).split(/[-_]/)[0] === languageCode);
  return languageMatched?.id ?? fallback;
}

export async function getStoredLocaleId(
  storage,
  definitions = BUILTIN_LOCALE_DEFINITIONS,
  fallback = DEFAULT_LOCALE_ID,
  storageKey = LOCALE_STORAGE_KEY,
) {
  const stored = await storage.getItem(storageKey);
  return resolveSupportedLocale(stored, definitions, fallback);
}

export async function persistLocaleId(
  storage,
  locale,
  definitions = BUILTIN_LOCALE_DEFINITIONS,
  fallback = DEFAULT_LOCALE_ID,
  storageKey = LOCALE_STORAGE_KEY,
) {
  const nextLocale = resolveSupportedLocale(locale, definitions, fallback);
  await storage.setItem(storageKey, nextLocale);
  return nextLocale;
}

export const THEME_STORAGE_KEY = 'familyclaw-theme';
export const DEFAULT_THEME_ID = 'chun-he-jing-ming';

const THEME_OPTIONS = [
  {
    id: 'chun-he-jing-ming',
    label: '春和景明',
    description: '温暖宁静，适合日常使用',
    accentColor: '#d97756',
    previewSurface: '#f7f5f2',
  },
  {
    id: 'yue-lang-xing-xi',
    label: '月朗星稀',
    description: '柔和深色，减少视觉疲劳',
    accentColor: '#7c9ef5',
    previewSurface: '#1a1d27',
  },
  {
    id: 'ming-cha-qiu-hao',
    label: '明察秋毫',
    description: '更大字号、更高对比度',
    accentColor: '#b04020',
    previewSurface: '#f5f5f0',
  },
  {
    id: 'wan-zi-qian-hong',
    label: '万紫千红',
    description: '鲜艳活泼，色彩缤纷',
    accentColor: '#e040a0',
    previewSurface: '#fef8ff',
  },
  {
    id: 'feng-chi-dian-che',
    label: '风驰电掣',
    description: '霓虹电网，赛博激光',
    accentColor: '#00f0ff',
    previewSurface: '#1f1032',
  },
  {
    id: 'xing-he-wan-li',
    label: '星河万里',
    description: '星云浮动，宇宙漫游',
    accentColor: '#b480ff',
    previewSurface: '#161a35',
  },
  {
    id: 'qing-shan-lv-shui',
    label: '青山绿水',
    description: '自然清新，森林氧吧',
    accentColor: '#2e8b57',
    previewSurface: '#f2f7f3',
  },
  {
    id: 'jin-xiu-qian-cheng',
    label: '锦绣前程',
    description: '正金尊贵，大气磅礴',
    accentColor: '#ffd700',
    previewSurface: '#181408',
  },
];

export function listThemeOptions() {
  return THEME_OPTIONS.map(option => ({ ...option }));
}

export function resolveThemeId(themeId, fallback = DEFAULT_THEME_ID) {
  const normalized = (themeId ?? '').trim();
  const matched = THEME_OPTIONS.find(option => option.id === normalized);
  return matched?.id ?? fallback;
}

export function isElderFriendlyTheme(themeId) {
  return resolveThemeId(themeId) === 'ming-cha-qiu-hao';
}

export async function getStoredThemeId(storage, storageKey = THEME_STORAGE_KEY, fallback = DEFAULT_THEME_ID) {
  const stored = await storage.getItem(storageKey);
  return resolveThemeId(stored, fallback);
}

export async function persistThemeId(storage, themeId, storageKey = THEME_STORAGE_KEY, fallback = DEFAULT_THEME_ID) {
  const nextThemeId = resolveThemeId(themeId, fallback);
  await storage.setItem(storageKey, nextThemeId);
  return nextThemeId;
}

export const ROOM_TYPE_OPTIONS = [
  { value: 'living_room', label: '客厅' },
  { value: 'bedroom', label: '卧室' },
  { value: 'study', label: '书房' },
  { value: 'entrance', label: '玄关' },
  { value: 'kitchen', label: '厨房' },
  { value: 'bathroom', label: '卫生间' },
  { value: 'gym', label: '健身房' },
  { value: 'garage', label: '车库' },
  { value: 'dining_room', label: '餐厅' },
  { value: 'balcony', label: '阳台' },
  { value: 'kids_room', label: '儿童房' },
  { value: 'storage_room', label: '储物间' },
];

const ROOM_TYPE_LABELS = Object.fromEntries(
  ROOM_TYPE_OPTIONS.map(option => [option.value, option.label]),
);

export function formatRoomType(roomType) {
  return ROOM_TYPE_LABELS[roomType];
}

export async function loadSetupStatus(client, householdId) {
  if (!householdId) {
    return null;
  }

  return client.getHouseholdSetupStatus(householdId);
}

export async function loadBootstrapSnapshot(options) {
  const { client, platformTarget, storage } = options;

  let actor = null;
  try {
    const authResult = await client.getAuthMe();
    actor = authResult.actor;
  } catch {
    actor = null;
  }

  if (!actor?.authenticated) {
    return {
      actor: null,
      households: [],
      currentHousehold: null,
      setupStatus: null,
      platformTarget,
      locales: [],
    };
  }

  const householdsResponse = await client.listHouseholds();
  const storedHouseholdId = await getStoredHouseholdId(storage);
  const preferredHouseholdId = storedHouseholdId || actor.household_id || householdsResponse.items[0]?.id || '';
  const currentHousehold = householdsResponse.items.find(item => item.id === preferredHouseholdId) ?? null;

  if (currentHousehold) {
    await persistHouseholdId(storage, currentHousehold.id);
  }

  const [setupStatus, locales] = await Promise.all([
    currentHousehold ? client.getHouseholdSetupStatus(currentHousehold.id).catch(() => null) : Promise.resolve(null),
    currentHousehold ? client.listHouseholdLocales(currentHousehold.id).then(result => result.items).catch(() => []) : Promise.resolve([]),
  ]);

  return {
    actor,
    households: householdsResponse.items,
    currentHousehold,
    setupStatus,
    platformTarget,
    locales,
  };
}
