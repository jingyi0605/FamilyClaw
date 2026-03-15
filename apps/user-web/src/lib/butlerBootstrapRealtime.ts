import { createBrowserRealtimeClient, newRealtimeRequestId, type BootstrapRealtimeEvent } from '@familyclaw/user-platform';

type ConnectOptions = {
  householdId: string;
  sessionId: string;
  onEvent: (event: BootstrapRealtimeEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: () => void;
};

export type ButlerBootstrapRealtimeClient = {
  close: () => void;
  sendPing: (nonce?: string) => void;
  sendUserMessage: (requestId: string, text: string) => void;
};

export function createButlerBootstrapRealtimeClient(options: ConnectOptions): ButlerBootstrapRealtimeClient {
  return createBrowserRealtimeClient({
    ...options,
    channel: 'agent-bootstrap',
    baseUrl: import.meta.env.VITE_REALTIME_BASE_URL ?? import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
    origin: window.location.origin,
  });
}

export { newRealtimeRequestId };
