// packages/user-core/src/api/create-api-client.ts
var ApiError = class extends Error {
  status;
  payload;
  constructor(status, message, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
};
function resolveErrorMessage(payload, fallbackMessage) {
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object" && "detail" in detail) {
      const nestedDetail = detail.detail;
      if (typeof nestedDetail === "string" && nestedDetail.trim()) {
        return nestedDetail;
      }
    }
  }
  return fallbackMessage;
}
async function readResponsePayload(response, isJsonResponse) {
  if (response.status === 204 || response.status === 205) {
    return void 0;
  }
  const text = await response.text().catch(() => "");
  if (!text.trim()) {
    return void 0;
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
function createRequestClient(config = {}) {
  const baseUrl = config.baseUrl ?? "/api/v1";
  const timeoutMs = config.timeoutMs ?? 8e3;
  const fetchImpl = config.fetchImpl ?? fetch;
  const credentials = config.credentials ?? "include";
  return async function request(path, init, nextTimeoutMs) {
    const headers = new Headers(init?.headers ?? {});
    if (init?.body !== void 0 && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const controller = new AbortController();
    const timeoutId = globalThis.setTimeout(() => controller.abort(), nextTimeoutMs ?? timeoutMs);
    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        ...init,
        credentials,
        headers,
        signal: controller.signal
      });
    } catch (error) {
      globalThis.clearTimeout(timeoutId);
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError(0, "\u8BF7\u6C42\u8D85\u65F6\uFF0C\u8BF7\u786E\u8BA4\u540E\u7AEF\u670D\u52A1\u662F\u5426\u53EF\u7528", null);
      }
      throw error;
    }
    globalThis.clearTimeout(timeoutId);
    const contentType = response.headers.get("content-type") ?? "";
    const isJsonResponse = contentType.includes("application/json");
    if (!response.ok) {
      const payload2 = await readResponsePayload(response, isJsonResponse);
      throw new ApiError(
        response.status,
        resolveErrorMessage(payload2, `Request failed with status ${response.status}`),
        payload2
      );
    }
    if (!isJsonResponse) {
      return void 0;
    }
    const payload = await readResponsePayload(response, isJsonResponse);
    return payload;
  };
}
function createCoreApiClient(request) {
  return {
    login(payload) {
      return request("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    completeBootstrapAccount(payload) {
      return request("/auth/bootstrap/complete", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    getAuthMe() {
      return request("/auth/me");
    },
    logout() {
      return request("/auth/logout", {
        method: "POST"
      });
    },
    createHouseholdAccount(payload) {
      return request("/accounts/household", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    listAiProviderAdapters() {
      return request("/ai-config/provider-adapters");
    },
    listHouseholdAiProviders(householdId, options) {
      const query = new URLSearchParams();
      if (options?.enabled !== void 0) {
        query.set("enabled", String(options.enabled));
      }
      if (options?.capability) {
        query.set("capability", options.capability);
      }
      const queryString = query.toString();
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/provider-profiles${queryString ? `?${queryString}` : ""}`
      );
    },
    createHouseholdAiProvider(householdId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/provider-profiles`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    deleteHouseholdAiProvider(householdId, profileId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/provider-profiles/${encodeURIComponent(profileId)}`,
        {
          method: "DELETE"
        }
      );
    },
    updateHouseholdAiProvider(householdId, profileId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/provider-profiles/${encodeURIComponent(profileId)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    listHouseholdAiRoutes(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/provider-routes`);
    },
    upsertHouseholdAiRoute(householdId, capability, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/provider-routes/${encodeURIComponent(capability)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    createButlerBootstrapSession(householdId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions`,
        { method: "POST" },
        6e4
      );
    },
    getLatestButlerBootstrapSession(householdId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/latest`,
        { method: "GET" },
        6e4
      );
    },
    restartButlerBootstrapSession(householdId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/restart`,
        { method: "POST" },
        6e4
      );
    },
    confirmButlerBootstrapSession(householdId, sessionId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/butler-bootstrap/sessions/${encodeURIComponent(sessionId)}/confirm`,
        {
          method: "POST",
          body: JSON.stringify(payload)
        },
        6e4
      );
    },
    listAgents(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}`);
    },
    createAgent(householdId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/agents`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    getAgentDetail(householdId, agentId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`);
    },
    updateAgent(householdId, agentId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    },
    upsertAgentSoul(householdId, agentId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/soul`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
    },
    upsertAgentRuntimePolicy(householdId, agentId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/runtime-policy`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    upsertAgentMemberCognitions(householdId, agentId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/agents/${encodeURIComponent(agentId)}/member-cognitions`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    listRegisteredPlugins(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/plugins`);
    },
    updatePluginState(householdId, pluginId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/plugins/${encodeURIComponent(pluginId)}/state`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    listPluginMounts(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/plugin-mounts`);
    },
    createPluginMount(householdId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/plugin-mounts`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    updatePluginMount(householdId, pluginId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/plugin-mounts/${encodeURIComponent(pluginId)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    deletePluginMount(householdId, pluginId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/plugin-mounts/${encodeURIComponent(pluginId)}`, {
        method: "DELETE"
      });
    },
    listHouseholds() {
      return request("/households?page_size=100");
    },
    getHousehold(householdId) {
      return request(`/households/${encodeURIComponent(householdId)}`);
    },
    createHousehold(payload) {
      return request("/households", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    updateHousehold(householdId, payload) {
      return request(`/households/${encodeURIComponent(householdId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    },
    listRegionCatalog(params) {
      const search = new URLSearchParams();
      search.set("provider_code", params.provider_code);
      search.set("country_code", params.country_code);
      if (params.admin_level) {
        search.set("admin_level", params.admin_level);
      }
      if (params.parent_region_code) {
        search.set("parent_region_code", params.parent_region_code);
      }
      return request(`/regions/catalog?${search.toString()}`);
    },
    searchRegions(params) {
      const search = new URLSearchParams();
      search.set("provider_code", params.provider_code);
      search.set("country_code", params.country_code);
      search.set("keyword", params.keyword);
      if (params.admin_level) {
        search.set("admin_level", params.admin_level);
      }
      if (params.parent_region_code) {
        search.set("parent_region_code", params.parent_region_code);
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
      return request("/rooms", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    updateRoom(roomId, payload) {
      return request(`/rooms/${encodeURIComponent(roomId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    },
    deleteRoom(roomId) {
      return request(`/rooms/${encodeURIComponent(roomId)}`, {
        method: "DELETE"
      });
    },
    listMembers(householdId) {
      return request(`/members?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    createMember(payload) {
      return request("/members", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    updateMember(memberId, payload) {
      return request(`/members/${encodeURIComponent(memberId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    },
    listMemberRelationships(householdId) {
      return request(
        `/member-relationships?household_id=${encodeURIComponent(householdId)}&page_size=100`
      );
    },
    createMemberRelationship(payload) {
      return request("/member-relationships", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    deleteMemberRelationship(relationshipId) {
      return request(`/member-relationships/${encodeURIComponent(relationshipId)}`, {
        method: "DELETE"
      });
    },
    getMemberPreferences(memberId) {
      return request(`/member-preferences/${encodeURIComponent(memberId)}`);
    },
    upsertMemberPreferences(memberId, payload) {
      return request(`/member-preferences/${encodeURIComponent(memberId)}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
    },
    listDevices(householdId) {
      return request(`/devices?household_id=${encodeURIComponent(householdId)}&page_size=100`);
    },
    listVoiceTerminalDiscoveries(householdId) {
      return request(
        `/devices/voice-terminals/discoveries?household_id=${encodeURIComponent(householdId)}`
      );
    },
    claimVoiceTerminalDiscovery(fingerprint, payload) {
      return request(
        `/devices/voice-terminals/discoveries/${encodeURIComponent(fingerprint)}/claim`,
        {
          method: "POST",
          body: JSON.stringify(payload)
        }
      );
    },
    updateDevice(deviceId, payload) {
      return request(`/devices/${encodeURIComponent(deviceId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      });
    },
    getHomeAssistantConfig(householdId) {
      return request(`/devices/ha-config/${encodeURIComponent(householdId)}`);
    },
    updateHomeAssistantConfig(householdId, payload) {
      return request(`/devices/ha-config/${encodeURIComponent(householdId)}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
    },
    listHomeAssistantDeviceCandidates(householdId) {
      return request(`/devices/ha-candidates/${encodeURIComponent(householdId)}`);
    },
    syncHomeAssistant(householdId) {
      return request("/devices/sync/ha", {
        method: "POST",
        body: JSON.stringify({ household_id: householdId, external_device_ids: [] })
      });
    },
    syncSelectedHomeAssistantDevices(householdId, externalDeviceIds) {
      return request("/devices/sync/ha", {
        method: "POST",
        body: JSON.stringify({ household_id: householdId, external_device_ids: externalDeviceIds })
      });
    },
    syncHomeAssistantRooms(householdId) {
      return request("/devices/rooms/sync/ha", {
        method: "POST",
        body: JSON.stringify({ household_id: householdId, room_names: [] })
      });
    },
    listHomeAssistantRoomCandidates(householdId) {
      return request(`/devices/rooms/ha-candidates/${encodeURIComponent(householdId)}`);
    },
    syncSelectedHomeAssistantRooms(householdId, roomNames) {
      return request("/devices/rooms/sync/ha", {
        method: "POST",
        body: JSON.stringify({ household_id: householdId, room_names: roomNames })
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
        method: "PUT",
        body: JSON.stringify(payload)
      });
    },
    getReminderOverview(householdId) {
      return request(`/reminders/overview?household_id=${encodeURIComponent(householdId)}`);
    },
    listMemoryCards(params) {
      const query = new URLSearchParams({
        household_id: params.household_id,
        page_size: String(params.page_size ?? 100)
      });
      if (params.memory_type) {
        query.set("memory_type", params.memory_type);
      }
      return request(`/memories/cards?${query.toString()}`);
    },
    listMemoryCardRevisions(memoryId) {
      return request(`/memories/cards/${encodeURIComponent(memoryId)}/revisions`);
    },
    correctMemoryCard(memoryId, payload) {
      return request(`/memories/cards/${encodeURIComponent(memoryId)}/corrections`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    createConversationSession(payload) {
      return request("/conversations/sessions", {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    listConversationSessions(params) {
      const query = new URLSearchParams({
        household_id: params.household_id,
        limit: String(params.limit ?? 50)
      });
      if (params.requester_member_id) {
        query.set("requester_member_id", params.requester_member_id);
      }
      return request(`/conversations/sessions?${query.toString()}`, void 0, 2e4);
    },
    getConversationSession(sessionId) {
      return request(`/conversations/sessions/${encodeURIComponent(sessionId)}`, void 0, 2e4);
    },
    createConversationTurn(sessionId, payload) {
      return request(`/conversations/sessions/${encodeURIComponent(sessionId)}/turns`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    confirmConversationAction(actionId) {
      return request(
        `/conversations/actions/${encodeURIComponent(actionId)}/confirm`,
        { method: "POST" }
      );
    },
    dismissConversationAction(actionId) {
      return request(
        `/conversations/actions/${encodeURIComponent(actionId)}/dismiss`,
        { method: "POST" }
      );
    },
    undoConversationAction(actionId) {
      return request(
        `/conversations/actions/${encodeURIComponent(actionId)}/undo`,
        { method: "POST" }
      );
    },
    confirmConversationProposal(proposalItemId) {
      return request(
        `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/confirm`,
        { method: "POST" }
      );
    },
    dismissConversationProposal(proposalItemId) {
      return request(
        `/conversations/proposal-items/${encodeURIComponent(proposalItemId)}/dismiss`,
        { method: "POST" }
      );
    },
    listPluginJobs(householdId, params) {
      const query = new URLSearchParams({ household_id: householdId });
      if (params?.status) {
        query.set("status", params.status);
      }
      if (params?.plugin_id) {
        query.set("plugin_id", params.plugin_id);
      }
      if (params?.created_from) {
        query.set("created_from", params.created_from);
      }
      if (params?.created_to) {
        query.set("created_to", params.created_to);
      }
      if (params?.page) {
        query.set("page", String(params.page));
      }
      if (params?.page_size) {
        query.set("page_size", String(params.page_size));
      }
      return request(`/plugin-jobs?${query.toString()}`);
    },
    listHouseholdLocales(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/locales`);
    },
    listChannelAccounts(householdId) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/channel-accounts`);
    },
    createChannelAccount(householdId, payload) {
      return request(`/ai-config/${encodeURIComponent(householdId)}/channel-accounts`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
    },
    updateChannelAccount(householdId, accountId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    },
    probeChannelAccount(householdId, accountId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/probe`,
        { method: "POST" }
      );
    },
    getChannelAccountStatus(householdId, accountId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/status`
      );
    },
    listChannelDeliveries(householdId, params) {
      const query = new URLSearchParams();
      if (params?.channel_account_id) {
        query.set("channel_account_id", params.channel_account_id);
      }
      if (params?.platform_code) {
        query.set("platform_code", params.platform_code);
      }
      if (params?.status) {
        query.set("status", params.status);
      }
      const queryString = query.toString();
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-deliveries${queryString ? `?${queryString}` : ""}`
      );
    },
    listChannelInboundEvents(householdId, params) {
      const query = new URLSearchParams();
      if (params?.channel_account_id) {
        query.set("channel_account_id", params.channel_account_id);
      }
      if (params?.platform_code) {
        query.set("platform_code", params.platform_code);
      }
      if (params?.status) {
        query.set("status", params.status);
      }
      const queryString = query.toString();
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-inbound-events${queryString ? `?${queryString}` : ""}`
      );
    },
    listChannelAccountBindings(householdId, accountId) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings`
      );
    },
    createChannelAccountBinding(householdId, accountId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings`,
        {
          method: "POST",
          body: JSON.stringify(payload)
        }
      );
    },
    updateChannelAccountBinding(householdId, accountId, bindingId, payload) {
      return request(
        `/ai-config/${encodeURIComponent(householdId)}/channel-accounts/${encodeURIComponent(accountId)}/bindings/${encodeURIComponent(bindingId)}`,
        {
          method: "PUT",
          body: JSON.stringify(payload)
        }
      );
    }
  };
}

// packages/user-core/src/domain/types.ts
var ROOM_TYPE_OPTIONS = [
  { value: "living_room", label: "\u5BA2\u5385" },
  { value: "bedroom", label: "\u5367\u5BA4" },
  { value: "study", label: "\u4E66\u623F" },
  { value: "entrance", label: "\u7384\u5173" },
  { value: "kitchen", label: "\u53A8\u623F" },
  { value: "bathroom", label: "\u536B\u751F\u95F4" },
  { value: "gym", label: "\u5065\u8EAB\u623F" },
  { value: "garage", label: "\u8F66\u5E93" },
  { value: "dining_room", label: "\u9910\u5385" },
  { value: "balcony", label: "\u9633\u53F0" },
  { value: "kids_room", label: "\u513F\u7AE5\u623F" },
  { value: "storage_room", label: "\u50A8\u7269\u95F4" }
];
var ROOM_TYPE_LABELS = Object.fromEntries(
  ROOM_TYPE_OPTIONS.map((option) => [option.value, option.label])
);
function formatRoomType(roomType) {
  return ROOM_TYPE_LABELS[roomType];
}

// packages/user-core/src/state/auth.ts
var CLIENT_ONLY_STORAGE_PREFIXES = [
  "familyclaw-conversation-sessions",
  "familyclaw-assistant-sessions"
];
async function clearClientOnlyStorage(storage, prefixes = CLIENT_ONLY_STORAGE_PREFIXES) {
  if (!storage.keys) {
    return;
  }
  const keys = await storage.keys();
  await Promise.all(
    keys.filter((key) => prefixes.some((prefix) => key.startsWith(prefix))).map((key) => storage.removeItem(key))
  );
}
function isAuthenticatedActor(actor) {
  return Boolean(actor?.authenticated);
}

// packages/user-core/src/state/household.ts
var HOUSEHOLD_STORAGE_KEY = "familyclaw-household";
async function getStoredHouseholdId(storage, storageKey = HOUSEHOLD_STORAGE_KEY) {
  return await storage.getItem(storageKey) ?? "";
}
async function persistHouseholdId(storage, householdId, storageKey = HOUSEHOLD_STORAGE_KEY) {
  if (!householdId) {
    await storage.removeItem(storageKey);
    return;
  }
  await storage.setItem(storageKey, householdId);
}
function toHouseholdSummary(household) {
  return {
    id: household.id,
    name: household.name,
    city: household.city,
    timezone: household.timezone,
    locale: household.locale,
    status: household.status,
    region: household.region
  };
}

// packages/user-core/src/state/locale.ts
var LOCALE_STORAGE_KEY = "familyclaw-locale";
var DEFAULT_LOCALE_ID = "zh-CN";
var BUILTIN_LOCALE_DEFINITIONS = [
  {
    id: "zh-CN",
    label: "\u7B80\u4F53\u4E2D\u6587",
    nativeLabel: "\u7B80\u4F53\u4E2D\u6587",
    flag: "CN",
    source: "builtin",
    sourceType: "builtin"
  },
  {
    id: "en-US",
    label: "English",
    nativeLabel: "English",
    flag: "US",
    fallback: "zh-CN",
    source: "builtin",
    sourceType: "builtin"
  }
];
function normalizeLocaleLookup(value) {
  return (value ?? "").trim().toLowerCase();
}
function sanitizeLocaleId(value) {
  return (value ?? "").trim();
}
function listBuiltinLocaleDefinitions() {
  return BUILTIN_LOCALE_DEFINITIONS.map((definition) => ({ ...definition }));
}
function buildLocaleDefinitions(pluginLocales = []) {
  const registry = /* @__PURE__ */ new Map();
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
      fallback: sanitizeLocaleId(pluginLocale.fallback) || void 0,
      messages: pluginLocale.messages,
      source: "plugin",
      sourceType: pluginLocale.source_type,
      pluginId: pluginLocale.plugin_id,
      overriddenPluginIds: pluginLocale.overridden_plugin_ids
    });
  }
  return Array.from(registry.values());
}
function formatLocaleOptionLabel(definition) {
  return `${definition.nativeLabel} (${definition.id})`;
}
function getLocaleSourceLabel(definition) {
  if (definition.source === "builtin" || definition.sourceType === "builtin") {
    return "builtin";
  }
  if (definition.sourceType === "official") {
    return "official";
  }
  return "third_party";
}
function getLocaleDefinition(definitions, locale) {
  if (!locale) {
    return void 0;
  }
  const normalized = normalizeLocaleLookup(locale);
  return definitions.find((item) => normalizeLocaleLookup(item.id) === normalized);
}
function isRegisteredLocale(definitions, locale) {
  return Boolean(getLocaleDefinition(definitions, locale));
}
function resolveSupportedLocale(locale, definitions = BUILTIN_LOCALE_DEFINITIONS, fallback = DEFAULT_LOCALE_ID) {
  const matched = getLocaleDefinition(definitions, locale);
  if (matched) {
    return matched.id;
  }
  const normalized = normalizeLocaleLookup(locale);
  if (!normalized) {
    return fallback;
  }
  if ((normalized.includes("hant") || normalized.startsWith("zh-tw") || normalized.startsWith("zh-hk") || normalized.startsWith("zh-mo")) && isRegisteredLocale(definitions, "zh-TW")) {
    return "zh-TW";
  }
  if (normalized.startsWith("zh") && isRegisteredLocale(definitions, "zh-CN")) {
    return "zh-CN";
  }
  const languageCode = normalized.split(/[-_]/)[0];
  const languageMatched = definitions.find((item) => normalizeLocaleLookup(item.id).split(/[-_]/)[0] === languageCode);
  return languageMatched?.id ?? fallback;
}
async function getStoredLocaleId(storage, definitions = BUILTIN_LOCALE_DEFINITIONS, fallback = DEFAULT_LOCALE_ID, storageKey = LOCALE_STORAGE_KEY) {
  const stored = await storage.getItem(storageKey);
  return resolveSupportedLocale(stored, definitions, fallback);
}
async function persistLocaleId(storage, locale, definitions = BUILTIN_LOCALE_DEFINITIONS, fallback = DEFAULT_LOCALE_ID, storageKey = LOCALE_STORAGE_KEY) {
  const nextLocale = resolveSupportedLocale(locale, definitions, fallback);
  await storage.setItem(storageKey, nextLocale);
  return nextLocale;
}

// packages/user-core/src/state/setup.ts
async function loadSetupStatus(client, householdId) {
  if (!householdId) {
    return null;
  }
  return client.getHouseholdSetupStatus(householdId);
}

// packages/user-core/src/state/theme.ts
var THEME_STORAGE_KEY = "familyclaw-theme";
var DEFAULT_THEME_ID = "chun-he-jing-ming";
var THEME_OPTIONS = [
  {
    id: "chun-he-jing-ming",
    label: "\u6625\u548C\u666F\u660E",
    description: "\u6E29\u6696\u5B81\u9759\uFF0C\u9002\u5408\u65E5\u5E38\u4F7F\u7528",
    accentColor: "#d97756",
    previewSurface: "#f7f5f2"
  },
  {
    id: "yue-lang-xing-xi",
    label: "\u6708\u6717\u661F\u7A00",
    description: "\u67D4\u548C\u6DF1\u8272\uFF0C\u51CF\u5C11\u89C6\u89C9\u75B2\u52B3",
    accentColor: "#7c9ef5",
    previewSurface: "#1a1d27"
  },
  {
    id: "ming-cha-qiu-hao",
    label: "\u660E\u5BDF\u79CB\u6BEB",
    description: "\u66F4\u5927\u5B57\u53F7\u3001\u66F4\u9AD8\u5BF9\u6BD4\u5EA6",
    accentColor: "#b04020",
    previewSurface: "#f5f5f0"
  },
  {
    id: "wan-zi-qian-hong",
    label: "\u4E07\u7D2B\u5343\u7EA2",
    description: "\u9C9C\u8273\u6D3B\u6CFC\uFF0C\u8272\u5F69\u7F24\u7EB7",
    accentColor: "#e040a0",
    previewSurface: "#fef8ff"
  },
  {
    id: "feng-chi-dian-che",
    label: "\u98CE\u9A70\u7535\u63A3",
    description: "\u9713\u8679\u7535\u7F51\uFF0C\u8D5B\u535A\u6FC0\u5149",
    accentColor: "#00f0ff",
    previewSurface: "#1f1032"
  },
  {
    id: "xing-he-wan-li",
    label: "\u661F\u6CB3\u4E07\u91CC",
    description: "\u661F\u4E91\u6D6E\u52A8\uFF0C\u5B87\u5B99\u6F2B\u6E38",
    accentColor: "#b480ff",
    previewSurface: "#161a35"
  },
  {
    id: "qing-shan-lv-shui",
    label: "\u9752\u5C71\u7EFF\u6C34",
    description: "\u81EA\u7136\u6E05\u65B0\uFF0C\u68EE\u6797\u6C27\u5427",
    accentColor: "#2e8b57",
    previewSurface: "#f2f7f3"
  },
  {
    id: "jin-xiu-qian-cheng",
    label: "\u9526\u7EE3\u524D\u7A0B",
    description: "\u6B63\u91D1\u5C0A\u8D35\uFF0C\u5927\u6C14\u78C5\u7934",
    accentColor: "#ffd700",
    previewSurface: "#181408"
  }
];
function listThemeOptions() {
  return THEME_OPTIONS.map((option) => ({ ...option }));
}
function resolveThemeId(themeId, fallback = DEFAULT_THEME_ID) {
  const normalized = (themeId ?? "").trim();
  const matched = THEME_OPTIONS.find((option) => option.id === normalized);
  return matched?.id ?? fallback;
}
function isElderFriendlyTheme(themeId) {
  return resolveThemeId(themeId) === "ming-cha-qiu-hao";
}
async function getStoredThemeId(storage, storageKey = THEME_STORAGE_KEY, fallback = DEFAULT_THEME_ID) {
  const stored = await storage.getItem(storageKey);
  return resolveThemeId(stored, fallback);
}
async function persistThemeId(storage, themeId, storageKey = THEME_STORAGE_KEY, fallback = DEFAULT_THEME_ID) {
  const nextThemeId = resolveThemeId(themeId, fallback);
  await storage.setItem(storageKey, nextThemeId);
  return nextThemeId;
}

// packages/user-core/src/services/bootstrap.ts
async function loadBootstrapSnapshot(options) {
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
      locales: []
    };
  }
  const householdsResponse = await client.listHouseholds();
  const storedHouseholdId = await getStoredHouseholdId(storage);
  const currentHousehold = (storedHouseholdId ? householdsResponse.items.find((item) => item.id === storedHouseholdId) : null) ?? (actor.household_id ? householdsResponse.items.find((item) => item.id === actor.household_id) : null) ?? householdsResponse.items[0] ?? null;
  await persistHouseholdId(storage, currentHousehold?.id ?? "");
  const [setupStatus, locales] = await Promise.all([
    currentHousehold ? client.getHouseholdSetupStatus(currentHousehold.id).catch(() => null) : Promise.resolve(null),
    currentHousehold ? client.listHouseholdLocales(currentHousehold.id).then((result) => result.items).catch(() => []) : Promise.resolve([])
  ]);
  return {
    actor,
    households: householdsResponse.items,
    currentHousehold,
    setupStatus,
    platformTarget,
    locales
  };
}

// packages/user-core/src/services/setup-wizard.ts
var SETUP_ROUTE_CAPABILITIES = ["qa_generation", "qa_structured_answer"];
var CORE_PROVIDER_FIELD_KEYS = /* @__PURE__ */ new Set([
  "display_name",
  "provider_code",
  "base_url",
  "secret_ref",
  "model_name",
  "privacy_level",
  "latency_budget_ms"
]);
function buildSetupProviderFormState(adapter) {
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? []).filter((field) => !CORE_PROVIDER_FIELD_KEYS.has(field.key)).map((field) => [field.key, readAdapterDefault(adapter, field.key)])
  );
  return {
    adapterCode: adapter?.adapter_code ?? "",
    displayName: "",
    providerCode: "",
    baseUrl: readAdapterDefault(adapter, "base_url"),
    secretRef: "",
    modelName: "",
    privacyLevel: String(readAdapterDefault(adapter, "privacy_level") ?? adapter?.default_privacy_level ?? "public_cloud"),
    latencyBudgetMs: String(readAdapterDefault(adapter, "latency_budget_ms") ?? ""),
    enabled: true,
    supportedCapabilities: [...adapter?.default_supported_capabilities ?? SETUP_ROUTE_CAPABILITIES],
    dynamicFields
  };
}
function toSetupProviderFormState(provider, adapter) {
  const dynamicFields = Object.fromEntries(
    (adapter?.field_schema ?? []).filter((field) => !CORE_PROVIDER_FIELD_KEYS.has(field.key)).map((field) => [field.key, readProviderExtraConfigValue(provider, field)])
  );
  return {
    adapterCode: getProviderAdapterCode(provider) || adapter?.adapter_code || "",
    displayName: provider.display_name,
    providerCode: provider.provider_code,
    baseUrl: provider.base_url ?? "",
    secretRef: provider.secret_ref ?? "",
    modelName: getProviderModelName(provider) ?? "",
    privacyLevel: provider.privacy_level,
    latencyBudgetMs: provider.latency_budget_ms ? String(provider.latency_budget_ms) : "",
    enabled: provider.enabled,
    supportedCapabilities: provider.supported_capabilities,
    dynamicFields
  };
}
function buildCreateSetupProviderPayload(form, adapter) {
  return {
    provider_code: form.providerCode.trim() || buildSetupProviderCode(adapter.adapter_code),
    display_name: form.displayName.trim(),
    transport_type: adapter.transport_type,
    api_family: adapter.api_family,
    base_url: form.baseUrl.trim() || null,
    api_version: null,
    secret_ref: form.secretRef.trim() || null,
    enabled: form.enabled,
    supported_capabilities: form.supportedCapabilities,
    privacy_level: form.privacyLevel,
    latency_budget_ms: parseOptionalNumber(form.latencyBudgetMs),
    cost_policy: {},
    extra_config: {
      adapter_code: adapter.adapter_code,
      model_name: form.modelName.trim(),
      ...buildDynamicExtraConfig(form.dynamicFields, adapter)
    }
  };
}
function buildUpdateSetupProviderPayload(form, adapter) {
  return {
    display_name: form.displayName.trim(),
    transport_type: adapter.transport_type,
    api_family: adapter.api_family,
    base_url: form.baseUrl.trim() || null,
    api_version: null,
    secret_ref: form.secretRef.trim() || null,
    enabled: form.enabled,
    supported_capabilities: form.supportedCapabilities,
    privacy_level: form.privacyLevel,
    latency_budget_ms: parseOptionalNumber(form.latencyBudgetMs),
    cost_policy: {},
    extra_config: {
      adapter_code: adapter.adapter_code,
      model_name: form.modelName.trim(),
      ...buildDynamicExtraConfig(form.dynamicFields, adapter)
    }
  };
}
function readSetupProviderFormValue(form, fieldKey) {
  if (fieldKey === "display_name") return form.displayName;
  if (fieldKey === "provider_code") return form.providerCode;
  if (fieldKey === "base_url") return form.baseUrl;
  if (fieldKey === "secret_ref") return form.secretRef;
  if (fieldKey === "model_name") return form.modelName;
  if (fieldKey === "privacy_level") return form.privacyLevel;
  if (fieldKey === "latency_budget_ms") return form.latencyBudgetMs;
  return form.dynamicFields[fieldKey] ?? "";
}
function assignSetupProviderFormValue(form, fieldKey, value) {
  if (fieldKey === "display_name") return { ...form, displayName: value };
  if (fieldKey === "provider_code") return { ...form, providerCode: value };
  if (fieldKey === "base_url") return { ...form, baseUrl: value };
  if (fieldKey === "secret_ref") return { ...form, secretRef: value };
  if (fieldKey === "model_name") return { ...form, modelName: value };
  if (fieldKey === "privacy_level") return { ...form, privacyLevel: value };
  if (fieldKey === "latency_budget_ms") return { ...form, latencyBudgetMs: value };
  return {
    ...form,
    dynamicFields: {
      ...form.dynamicFields,
      [fieldKey]: value
    }
  };
}
function buildSetupRoutePayload(householdId, capability, currentRoute, primaryProviderProfileId, enabled) {
  return {
    capability,
    household_id: householdId,
    primary_provider_profile_id: primaryProviderProfileId,
    fallback_provider_profile_ids: currentRoute?.fallback_provider_profile_ids ?? [],
    routing_mode: currentRoute?.routing_mode ?? "primary_then_fallback",
    timeout_ms: currentRoute?.timeout_ms ?? 15e3,
    max_retry_count: currentRoute?.max_retry_count ?? 0,
    allow_remote: currentRoute?.allow_remote ?? true,
    prompt_policy: currentRoute?.prompt_policy ?? {},
    response_policy: currentRoute?.response_policy ?? {},
    enabled
  };
}
function pickSetupProviderProfile(providers, routes) {
  const routeProviderIds = SETUP_ROUTE_CAPABILITIES.map((capability) => routes.find((item) => item.capability === capability)?.primary_provider_profile_id).filter((providerId) => Boolean(providerId));
  for (const providerId of routeProviderIds) {
    const matchedProvider = providers.find((item) => item.id === providerId);
    if (matchedProvider) {
      return matchedProvider;
    }
  }
  return providers[0] ?? null;
}
function resolveSetupRoutableCapabilities(capabilities) {
  return SETUP_ROUTE_CAPABILITIES.filter((capability) => capabilities.includes(capability));
}
function parseTagList(raw) {
  return Array.from(new Set(raw.split(/[,，、\n]/).map((item) => item.trim()).filter(Boolean)));
}
function stringifyTagList(values) {
  return values.join(", ");
}
function getProviderModelName(provider) {
  const raw = provider.extra_config?.model_name;
  return typeof raw === "string" && raw.trim() ? raw.trim() : provider.api_version;
}
function getProviderAdapterCode(provider) {
  const raw = provider.extra_config?.adapter_code;
  return typeof raw === "string" && raw.trim() ? raw.trim() : "";
}
function parseOptionalNumber(value) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}
function readAdapterDefault(adapter, key) {
  if (!adapter) {
    return "";
  }
  return String(adapter.field_schema.find((item) => item.key === key)?.default_value ?? "");
}
function readProviderExtraConfigValue(provider, field) {
  const raw = provider.extra_config?.[field.key];
  if (typeof raw === "boolean") {
    return raw ? "true" : "false";
  }
  if (typeof raw === "number") {
    return String(raw);
  }
  if (typeof raw === "string") {
    return raw;
  }
  return String(field.default_value ?? "");
}
function buildDynamicExtraConfig(dynamicFields, adapter) {
  const result = {};
  for (const field of adapter.field_schema) {
    if (CORE_PROVIDER_FIELD_KEYS.has(field.key)) {
      continue;
    }
    const rawValue = dynamicFields[field.key] ?? "";
    if (!rawValue.trim()) {
      continue;
    }
    if (field.field_type === "number") {
      const parsed = Number(rawValue);
      if (Number.isFinite(parsed)) {
        result[field.key] = parsed;
      }
      continue;
    }
    if (field.field_type === "boolean") {
      result[field.key] = rawValue === "true";
      continue;
    }
    result[field.key] = rawValue.trim();
  }
  return result;
}
function buildSetupProviderCode(adapterCode) {
  return `setup-${adapterCode}-${Date.now()}`;
}
export {
  ApiError,
  CLIENT_ONLY_STORAGE_PREFIXES,
  DEFAULT_LOCALE_ID,
  DEFAULT_THEME_ID,
  HOUSEHOLD_STORAGE_KEY,
  LOCALE_STORAGE_KEY,
  ROOM_TYPE_OPTIONS,
  SETUP_ROUTE_CAPABILITIES,
  THEME_STORAGE_KEY,
  assignSetupProviderFormValue,
  buildCreateSetupProviderPayload,
  buildLocaleDefinitions,
  buildSetupProviderFormState,
  buildSetupRoutePayload,
  buildUpdateSetupProviderPayload,
  clearClientOnlyStorage,
  createCoreApiClient,
  createRequestClient,
  formatLocaleOptionLabel,
  formatRoomType,
  getLocaleDefinition,
  getLocaleSourceLabel,
  getStoredHouseholdId,
  getStoredLocaleId,
  getStoredThemeId,
  isAuthenticatedActor,
  isElderFriendlyTheme,
  isRegisteredLocale,
  listBuiltinLocaleDefinitions,
  listThemeOptions,
  loadBootstrapSnapshot,
  loadSetupStatus,
  parseTagList,
  persistHouseholdId,
  persistLocaleId,
  persistThemeId,
  pickSetupProviderProfile,
  readSetupProviderFormValue,
  resolveSetupRoutableCapabilities,
  resolveSupportedLocale,
  resolveThemeId,
  stringifyTagList,
  toHouseholdSummary,
  toSetupProviderFormState
};
