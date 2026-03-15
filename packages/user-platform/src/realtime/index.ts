import type { ButlerBootstrapDraft } from '@familyclaw/user-core';

export type RealtimeConnectionState = 'unavailable' | 'connecting' | 'connected' | 'closed';

export type RealtimeConnection = {
  state: RealtimeConnectionState;
  reason: string | null;
  close: () => void;
};

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
] as const;

export type BootstrapRealtimeEventType = (typeof BOOTSTRAP_REALTIME_EVENT_TYPES)[number];

export const DISPLAY_TEXT_EVENT_TYPES = ['agent.chunk'] as const;
export const STATE_PATCH_EVENT_TYPES = ['agent.state_patch'] as const;
export const FORBIDDEN_TEXT_PROTOCOL_MARKERS = ['<config', '</config>', '<json', '</json>', '---'] as const;

const DISPLAY_TEXT_EVENT_TYPE_SET = new Set<BootstrapRealtimeEventType>(DISPLAY_TEXT_EVENT_TYPES);
const STATE_PATCH_EVENT_TYPE_SET = new Set<BootstrapRealtimeEventType>(STATE_PATCH_EVENT_TYPES);

export type BootstrapRealtimeSessionSnapshot = {
  session_id: string;
  status: 'collecting' | 'reviewing' | 'completed' | 'cancelled';
  pending_field: 'display_name' | 'speaking_style' | 'personality_traits' | null;
  draft: ButlerBootstrapDraft;
  assistant_message: string;
  messages: Array<{
    id?: string;
    role: 'assistant' | 'user';
    content: string;
    request_id?: string | null;
    seq?: number;
    created_at?: string;
  }>;
  can_confirm: boolean;
  current_request_id: string | null;
  last_event_seq: number;
};

export type BootstrapRealtimePayloadByType = {
  'session.ready': Record<string, never>;
  'session.snapshot': { snapshot: BootstrapRealtimeSessionSnapshot };
  'user.message.accepted': Record<string, never>;
  'agent.chunk': { text: string };
  'agent.state_patch': Partial<Pick<ButlerBootstrapDraft, 'display_name' | 'speaking_style' | 'personality_traits'>>;
  'agent.done': Record<string, never>;
  'agent.error': { detail: string; error_code: string };
  ping: { nonce?: string | null };
  pong: { nonce?: string | null };
};

export type BootstrapRealtimeEvent<TType extends BootstrapRealtimeEventType = BootstrapRealtimeEventType> = {
  type: TType;
  session_id: string;
  request_id: TType extends 'user.message.accepted' | 'agent.chunk' | 'agent.state_patch' | 'agent.done'
    ? string
    : string | null | undefined;
  seq: number;
  payload: BootstrapRealtimePayloadByType[TType];
  ts: string;
};

export type WebSocketLike = {
  readyState: number;
  addEventListener: (type: 'open' | 'message' | 'close' | 'error', listener: (event: any) => void) => void;
  send: (data: string) => void;
  close: () => void;
};

export type WebSocketFactory = (url: string) => WebSocketLike;

export type BrowserRealtimeClient = RealtimeConnection & {
  sendPing: (nonce?: string) => void;
  sendUserMessage: (requestId: string, text: string) => void;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isBootstrapRealtimeEventType(value: unknown): value is BootstrapRealtimeEventType {
  return typeof value === 'string' && BOOTSTRAP_REALTIME_EVENT_TYPES.includes(value as BootstrapRealtimeEventType);
}

function hasForbiddenTextProtocol(text: string): boolean {
  const lowered = text.toLowerCase();
  return FORBIDDEN_TEXT_PROTOCOL_MARKERS.some(marker => lowered.includes(marker));
}

function resolveBaseUrl(baseUrl?: string): string {
  return baseUrl ?? '/api/v1';
}

function resolveOrigin(origin?: string): string {
  if (origin) {
    return origin;
  }

  if (typeof globalThis.location?.origin === 'string' && globalThis.location.origin) {
    return globalThis.location.origin;
  }

  return 'http://localhost';
}

export function assertBootstrapRealtimeEvent(value: unknown): asserts value is BootstrapRealtimeEvent {
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

export function parseBootstrapRealtimeEvent(value: unknown): BootstrapRealtimeEvent {
  assertBootstrapRealtimeEvent(value);
  return value;
}

export function buildBootstrapRealtimeUrl(
  sessionId: string,
  householdId: string,
  baseUrl?: string,
  origin?: string,
): string {
  const resolvedUrl = new URL(resolveBaseUrl(baseUrl), resolveOrigin(origin));
  resolvedUrl.protocol = resolvedUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  resolvedUrl.pathname = `${resolvedUrl.pathname.replace(/\/$/, '')}/realtime/agent-bootstrap`;
  resolvedUrl.searchParams.set('session_id', sessionId);
  resolvedUrl.searchParams.set('household_id', householdId);
  return resolvedUrl.toString();
}

export function buildConversationRealtimeUrl(
  sessionId: string,
  householdId: string,
  baseUrl?: string,
  origin?: string,
): string {
  const resolvedUrl = new URL(resolveBaseUrl(baseUrl), resolveOrigin(origin));
  resolvedUrl.protocol = resolvedUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  resolvedUrl.pathname = `${resolvedUrl.pathname.replace(/\/$/, '')}/realtime/conversation`;
  resolvedUrl.searchParams.set('session_id', sessionId);
  resolvedUrl.searchParams.set('household_id', householdId);
  return resolvedUrl.toString();
}

function resolveWebSocketFactory(factory?: WebSocketFactory): WebSocketFactory {
  if (factory) {
    return factory;
  }

  return url => new WebSocket(url) as unknown as WebSocketLike;
}

export function createBrowserRealtimeClient(options: {
  householdId: string;
  sessionId: string;
  channel: 'agent-bootstrap' | 'conversation';
  baseUrl?: string;
  origin?: string;
  socketFactory?: WebSocketFactory;
  onEvent: (event: BootstrapRealtimeEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: () => void;
}): BrowserRealtimeClient {
  const factory = resolveWebSocketFactory(options.socketFactory);
  const url = options.channel === 'conversation'
    ? buildConversationRealtimeUrl(options.sessionId, options.householdId, options.baseUrl, options.origin)
    : buildBootstrapRealtimeUrl(options.sessionId, options.householdId, options.baseUrl, options.origin);
  const socket = factory(url);

  let state: RealtimeConnectionState = 'connecting';
  let reason: string | null = null;

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

export function newRealtimeRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function createUnavailableRealtimeConnection(reason = '当前阶段尚未接入实时连接适配层'): RealtimeConnection {
  return {
    state: 'unavailable',
    reason,
    close() {
      // 当前为占位实现，无需处理
    },
  };
}
