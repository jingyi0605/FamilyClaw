import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import type { ButlerBootstrapDraft } from './setupTypes';

export type BootstrapRealtimeEventType =
  | 'session.ready'
  | 'session.snapshot'
  | 'user.message.accepted'
  | 'agent.chunk'
  | 'agent.state_patch'
  | 'agent.done'
  | 'agent.error'
  | 'ping'
  | 'pong';

export type BootstrapRealtimeSessionSnapshot = {
  session_id: string;
  status: 'collecting' | 'reviewing' | 'completed' | 'cancelled';
  pending_field: 'display_name' | 'speaking_style' | 'personality_traits' | null;
  draft: ButlerBootstrapDraft;
  assistant_message: string;
  messages: Array<{ id?: string; role: 'assistant' | 'user'; content: string; request_id?: string | null; seq?: number; created_at?: string }>;
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
  request_id: string | null | undefined;
  seq: number;
  payload: BootstrapRealtimePayloadByType[TType];
  ts: string;
};

type WebSocketLike = {
  readyState: number;
  addEventListener: (type: 'open' | 'message' | 'close' | 'error', listener: (event: any) => void) => void;
  send: (data: string) => void;
  close: () => void;
};

function parseBootstrapRealtimeEvent(value: unknown): BootstrapRealtimeEvent {
  return value as BootstrapRealtimeEvent;
}

function resolveRuntimeLocale() {
  if (typeof navigator !== 'undefined' && navigator.language) {
    return navigator.language;
  }
  return 'zh-CN';
}

function buildBootstrapRealtimeUrl(sessionId: string, householdId: string, baseUrl = '/api/v1', origin = window.location.origin) {
  const resolvedUrl = new URL(baseUrl, origin);
  resolvedUrl.protocol = resolvedUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  resolvedUrl.pathname = `${resolvedUrl.pathname.replace(/\/$/, '')}/realtime/agent-bootstrap`;
  resolvedUrl.searchParams.set('session_id', sessionId);
  resolvedUrl.searchParams.set('household_id', householdId);
  return resolvedUrl.toString();
}

export function createBrowserRealtimeClient(options: {
  householdId: string;
  sessionId: string;
  onEvent: (event: BootstrapRealtimeEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: () => void;
}) {
  const socket = new WebSocket(buildBootstrapRealtimeUrl(options.sessionId, options.householdId)) as unknown as WebSocketLike;
  socket.addEventListener('open', () => options.onOpen?.());
  socket.addEventListener('message', message => {
    try {
      const raw = JSON.parse(String(message.data));
      options.onEvent(parseBootstrapRealtimeEvent(raw));
    } catch {
      options.onError?.();
    }
  });
  socket.addEventListener('close', event => options.onClose?.(event));
  socket.addEventListener('error', () => options.onError?.());
  return {
    close() { socket.close(); },
    sendPing(nonce?: string) {
      if (socket.readyState !== 1) return;
      socket.send(JSON.stringify({ type: 'ping', session_id: options.sessionId, payload: { nonce: nonce ?? null } }));
    },
    sendUserMessage(requestId: string, text: string) {
      if (socket.readyState !== 1) throw new Error(getPageMessage(resolveRuntimeLocale(), 'setup.butler.error.realtimeNotReady'));
      socket.send(JSON.stringify({ type: 'user.message', session_id: options.sessionId, request_id: requestId, payload: { text } }));
    },
  };
}

export function newRealtimeRequestId() {
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
