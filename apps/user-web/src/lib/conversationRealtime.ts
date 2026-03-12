import { buildConversationRealtimeUrl, parseBootstrapRealtimeEvent, type BootstrapRealtimeEvent } from './realtime';
import { newRealtimeRequestId } from './butlerBootstrapRealtime';

type ConnectOptions = {
  householdId: string;
  sessionId: string;
  onEvent: (event: BootstrapRealtimeEvent) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: () => void;
};

export type ConversationRealtimeClient = {
  close: () => void;
  sendPing: (nonce?: string) => void;
  sendUserMessage: (requestId: string, text: string) => void;
};

export function createConversationRealtimeClient(options: ConnectOptions): ConversationRealtimeClient {
  const socket = new WebSocket(buildConversationRealtimeUrl(options.sessionId, options.householdId));

  socket.addEventListener('open', () => {
    options.onOpen?.();
  });

  socket.addEventListener('message', (message) => {
    try {
      const raw = JSON.parse(String(message.data));
      const event = parseBootstrapRealtimeEvent(raw);
      options.onEvent(event);
    } catch {
      options.onError?.();
    }
  });

  socket.addEventListener('close', (event) => {
    options.onClose?.(event);
  });

  socket.addEventListener('error', () => {
    options.onError?.();
  });

  return {
    close() {
      socket.close();
    },
    sendPing(nonce) {
      if (socket.readyState !== WebSocket.OPEN) {
        return;
      }
      socket.send(JSON.stringify({
        type: 'ping',
        session_id: options.sessionId,
        payload: { nonce: nonce ?? null },
      }));
    },
    sendUserMessage(requestId, text) {
      if (socket.readyState !== WebSocket.OPEN) {
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

export { newRealtimeRequestId };
