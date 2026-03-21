import { subscribeToRealtimeUpdates as subscribeToMockRealtimeUpdates } from "../mocks/mockApi";
import type { RealtimeEvent, RealtimeListener } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== "false";

const realtimeListeners = new Set<RealtimeListener>();

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function getUserId(): string {
  const stored = localStorage.getItem("autobook_user_id");
  if (stored) return stored;
  const id = crypto.randomUUID();
  localStorage.setItem("autobook_user_id", id);
  return id;
}

function deriveWebSocketUrl() {
  const userId = getUserId();
  const configuredUrl = import.meta.env.VITE_WS_URL;

  let baseUrl: string;
  if (configuredUrl) {
    baseUrl = configuredUrl;
  } else {
    try {
      const apiUrl = new URL(API_BASE_URL);
      const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
      baseUrl = `${protocol}//${apiUrl.host}/ws`;
    } catch {
      baseUrl = "ws://localhost:8000/ws";
    }
  }

  const separator = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${separator}userId=${userId}`;
}

function notifyListeners(event: RealtimeEvent) {
  for (const listener of realtimeListeners) {
    listener(event);
  }
}

function parseRealtimeEvent(payload: string) {
  try {
    const parsed = JSON.parse(payload) as Partial<RealtimeEvent>;
    if (
      (parsed.type === "entry.posted" ||
        parsed.type === "clarification.created" ||
        parsed.type === "clarification.resolved") &&
      typeof parsed.occurred_at === "string"
    ) {
      return parsed as RealtimeEvent;
    }
  } catch {
    return null;
  }

  return null;
}

function scheduleReconnect() {
  if (reconnectTimer || typeof WebSocket === "undefined") {
    return;
  }

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    ensureSocketConnection();
  }, 1000);
}

export function ensureSocketConnection() {
  if (USE_MOCK_API || socket || typeof WebSocket === "undefined") {
    return;
  }

  const nextSocket = new WebSocket(deriveWebSocketUrl());
  socket = nextSocket;

  nextSocket.addEventListener("message", (event) => {
    if (typeof event.data !== "string") {
      return;
    }

    const parsed = parseRealtimeEvent(event.data);
    if (parsed) {
      notifyListeners(parsed);
    }
  });

  nextSocket.addEventListener("close", () => {
    if (socket === nextSocket) {
      socket = null;
    }

    scheduleReconnect();
  });

  nextSocket.addEventListener("error", () => {
    nextSocket.close();
  });
}

export function subscribeToRealtimeUpdates(listener: RealtimeListener) {
  if (USE_MOCK_API) {
    return subscribeToMockRealtimeUpdates(listener);
  }

  realtimeListeners.add(listener);
  ensureSocketConnection();

  return () => {
    realtimeListeners.delete(listener);
  };
}
