import type { RealtimeEvent } from "./types";

const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== "false";

type Callback = (event: RealtimeEvent) => void;
type Unsubscribe = () => void;

// --- Mock event bus (used in mock mode) ---

const mockListeners = new Set<Callback>();

export function emitMockEvent(event: RealtimeEvent): void {
  for (const cb of mockListeners) {
    cb(event);
  }
}

function subscribeToMockEvents(callback: Callback): Unsubscribe {
  mockListeners.add(callback);
  return () => {
    mockListeners.delete(callback);
  };
}

// --- WebSocket client (used in live mode) ---

function getWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const base = apiBase.replace(/\/api\/v1\/?$/, "").replace(/^http/, "ws");
  return `${base}/ws`;
}

function subscribeToWebSocket(callback: Callback): Unsubscribe {
  let ws: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    ws = new WebSocket(getWsUrl());

    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as RealtimeEvent;
        callback(event);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!closed) {
        setTimeout(connect, 1000);
      }
    };
  }

  connect();

  return () => {
    closed = true;
    ws?.close();
  };
}

// --- Public API ---

export function subscribeToRealtimeUpdates(callback: Callback): Unsubscribe {
  if (USE_MOCK_API) {
    return subscribeToMockEvents(callback);
  }
  return subscribeToWebSocket(callback);
}
