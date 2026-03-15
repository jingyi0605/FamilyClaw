import Taro, { ENV_TYPE } from '@tarojs/taro';

function createMemoryStorage(initialState = {}) {
  const store = new Map(Object.entries(initialState));

  return {
    async getItem(key) {
      return store.get(key) ?? null;
    },
    async setItem(key, value) {
      store.set(key, value);
    },
    async removeItem(key) {
      store.delete(key);
    },
    async keys() {
      return Array.from(store.keys());
    },
  };
}

export function createBrowserStorageAdapter() {
  const fallback = createMemoryStorage();

  return {
    async getItem(key) {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return fallback.getItem(key);
      }
    },
    async setItem(key, value) {
      try {
        globalThis.localStorage?.setItem(key, value);
        return;
      } catch {
        await fallback.setItem(key, value);
      }
    },
    async removeItem(key) {
      try {
        globalThis.localStorage?.removeItem(key);
        return;
      } catch {
        await fallback.removeItem(key);
      }
    },
    async keys() {
      try {
        if (!globalThis.localStorage) {
          return fallback.keys();
        }

        return Array.from({ length: globalThis.localStorage.length }, (_, index) => globalThis.localStorage.key(index))
          .filter(Boolean);
      } catch {
        return fallback.keys();
      }
    },
  };
}

export function createTaroStorageAdapter() {
  return {
    async getItem(key) {
      try {
        return Taro.getStorageSync(key) ?? null;
      } catch {
        return null;
      }
    },
    async setItem(key, value) {
      Taro.setStorageSync(key, value);
    },
    async removeItem(key) {
      Taro.removeStorageSync(key);
    },
    async keys() {
      try {
        return Taro.getStorageInfoSync().keys ?? [];
      } catch {
        return [];
      }
    },
  };
}

export function getPlatformTarget() {
  const env = Taro.getEnv();

  if (env === ENV_TYPE.WEB) {
    return {
      platform: 'h5',
      runtime: 'h5',
      supports_push: false,
      supports_file_picker: true,
      supports_camera: false,
      supports_share: typeof navigator !== 'undefined' && 'share' in navigator,
      supports_deeplink: true,
    };
  }

  if (env === ENV_TYPE.RN) {
    const systemInfo = Taro.getSystemInfoSync();
    const platform = systemInfo.platform === 'android' ? 'rn-android' : 'rn-ios';

    return {
      platform,
      runtime: 'rn',
      supports_push: true,
      supports_file_picker: true,
      supports_camera: true,
      supports_share: true,
      supports_deeplink: true,
    };
  }

  return {
    platform: 'harmony',
    runtime: 'harmony',
    supports_push: true,
    supports_file_picker: true,
    supports_camera: true,
    supports_share: true,
    supports_deeplink: true,
  };
}

export const BOOTSTRAP_REALTIME_EVENT_TYPES = [
  'session.ready',
  'session.snapshot',
  'user.message.accepted',
  'agent.chunk',
  'agent.state_patch',
  'agent.done',
  'agent.error',
  'ping',
  'pong',
];

export const DISPLAY_TEXT_EVENT_TYPES = ['agent.chunk'];
export const STATE_PATCH_EVENT_TYPES = ['agent.state_patch'];
export const FORBIDDEN_TEXT_PROTOCOL_MARKERS = ['<config', '</config>', '<json', '</json>', '---'];

const DISPLAY_TEXT_EVENT_TYPE_SET = new Set(DISPLAY_TEXT_EVENT_TYPES);
const STATE_PATCH_EVENT_TYPE_SET = new Set(STATE_PATCH_EVENT_TYPES);

function isObject(value) {
  return typeof value === 'object' && value !== null;
}

function isBootstrapRealtimeEventType(value) {
  return typeof value === 'string' && BOOTSTRAP_REALTIME_EVENT_TYPES.includes(value);
}

function hasForbiddenTextProtocol(text) {
  const lowered = text.toLowerCase();
  return FORBIDDEN_TEXT_PROTOCOL_MARKERS.some(marker => lowered.includes(marker));
}

function resolveBaseUrl(baseUrl) {
  return baseUrl ?? '/api/v1';
}

function resolveOrigin(origin) {
  if (origin) {
    return origin;
  }

  if (typeof globalThis.location?.origin === 'string' && globalThis.location.origin) {
    return globalThis.location.origin;
  }

  return 'http://localhost';
}

export function assertBootstrapRealtimeEvent(value) {
  if (!isObject(value)) {
    throw new Error('实时事件必须是对象');
  }
  if (!isBootstrapRealtimeEventType(value.type)) {
    throw new Error('未知的实时事件类型');
  }
  if (typeof value.session_id !== 'string' || !value.session_id.trim()) {
    throw new Error('实时事件缺少 session_id');
  }
  if (typeof value.seq !== 'number' || value.seq < 0) {
    throw new Error('实时事件缺少合法的 seq');
  }
  if (typeof value.ts !== 'string' || !value.ts.trim()) {
    throw new Error('实时事件缺少 ts');
  }
  if (!isObject(value.payload)) {
    throw new Error('实时事件缺少 payload');
  }

  if (DISPLAY_TEXT_EVENT_TYPE_SET.has(value.type) && (typeof value.request_id !== 'string' || !value.request_id.trim())) {
    throw new Error(`${value.type} 必须携带 request_id`);
  }
  if (STATE_PATCH_EVENT_TYPE_SET.has(value.type) && (typeof value.request_id !== 'string' || !value.request_id.trim())) {
    throw new Error(`${value.type} 必须携带 request_id`);
  }
  if ((value.type === 'user.message.accepted' || value.type === 'agent.done') && (typeof value.request_id !== 'string' || !value.request_id.trim())) {
    throw new Error(`${value.type} 必须携带 request_id`);
  }

  if (value.type === 'agent.chunk') {
    if (typeof value.payload.text !== 'string' || !value.payload.text.trim()) {
      throw new Error('agent.chunk.payload.text 不能为空');
    }
    if (hasForbiddenTextProtocol(value.payload.text)) {
      throw new Error('agent.chunk 只能承载纯展示文本');
    }
  }

  if (value.type === 'agent.state_patch') {
    const payload = value.payload;
    const hasAnyField =
      typeof payload.display_name === 'string'
      || typeof payload.speaking_style === 'string'
      || Array.isArray(payload.personality_traits);
    if (!hasAnyField) {
      throw new Error('agent.state_patch 至少要包含一个字段');
    }
  }

  if (value.type === 'agent.error') {
    if (typeof value.payload.detail !== 'string' || !value.payload.detail.trim()) {
      throw new Error('agent.error.payload.detail 不能为空');
    }
    if (typeof value.payload.error_code !== 'string' || !value.payload.error_code.trim()) {
      throw new Error('agent.error.payload.error_code 不能为空');
    }
  }
}

export function parseBootstrapRealtimeEvent(value) {
  assertBootstrapRealtimeEvent(value);
  return value;
}

export function buildBootstrapRealtimeUrl(sessionId, householdId, baseUrl, origin) {
  const resolvedUrl = new URL(resolveBaseUrl(baseUrl), resolveOrigin(origin));
  resolvedUrl.protocol = resolvedUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  resolvedUrl.pathname = `${resolvedUrl.pathname.replace(/\/$/, '')}/realtime/agent-bootstrap`;
  resolvedUrl.searchParams.set('session_id', sessionId);
  resolvedUrl.searchParams.set('household_id', householdId);
  return resolvedUrl.toString();
}

export function buildConversationRealtimeUrl(sessionId, householdId, baseUrl, origin) {
  const resolvedUrl = new URL(resolveBaseUrl(baseUrl), resolveOrigin(origin));
  resolvedUrl.protocol = resolvedUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  resolvedUrl.pathname = `${resolvedUrl.pathname.replace(/\/$/, '')}/realtime/conversation`;
  resolvedUrl.searchParams.set('session_id', sessionId);
  resolvedUrl.searchParams.set('household_id', householdId);
  return resolvedUrl.toString();
}

function resolveWebSocketFactory(factory) {
  if (factory) {
    return factory;
  }

  return url => new WebSocket(url);
}

export function createBrowserRealtimeClient(options) {
  const factory = resolveWebSocketFactory(options.socketFactory);
  const url = options.channel === 'conversation'
    ? buildConversationRealtimeUrl(options.sessionId, options.householdId, options.baseUrl, options.origin)
    : buildBootstrapRealtimeUrl(options.sessionId, options.householdId, options.baseUrl, options.origin);
  const socket = factory(url);

  let state = 'connecting';
  let reason = null;

  socket.addEventListener('open', () => {
    state = 'connected';
    reason = null;
    options.onOpen?.();
  });

  socket.addEventListener('message', message => {
    try {
      const raw = JSON.parse(String(message.data));
      const event = parseBootstrapRealtimeEvent(raw);
      options.onEvent(event);
    } catch {
      options.onError?.();
    }
  });

  socket.addEventListener('close', event => {
    state = 'closed';
    reason = '实时连接已关闭';
    options.onClose?.(event);
  });

  socket.addEventListener('error', () => {
    reason = '实时连接发生错误';
    options.onError?.();
  });

  return {
    get state() {
      return state;
    },
    get reason() {
      return reason;
    },
    close() {
      socket.close();
    },
    sendPing(nonce) {
      if (socket.readyState !== 1) {
        return;
      }

      socket.send(JSON.stringify({
        type: 'ping',
        session_id: options.sessionId,
        payload: { nonce: nonce ?? null },
      }));
    },
    sendUserMessage(requestId, text) {
      if (socket.readyState !== 1) {
        throw new Error('实时连接还没建立完成');
      }

      socket.send(JSON.stringify({
        type: 'user.message',
        session_id: options.sessionId,
        request_id: requestId,
        payload: { text },
      }));
    },
  };
}

export function newRealtimeRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function createUnavailableRealtimeConnection(reason = '当前阶段尚未接入实时连接适配层') {
  return {
    state: 'unavailable',
    reason,
    close() {},
  };
}
