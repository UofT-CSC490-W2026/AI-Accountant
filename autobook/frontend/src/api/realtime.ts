import { subscribeToRealtimeUpdates as subscribeToMockRealtimeUpdates } from "../mocks/mockApi";
import { isMockApiEnabled } from "../config/env";
import { getAccessToken } from "./auth";
import type { RealtimeEvent, RealtimeListener } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const realtimeListeners = new Set<RealtimeListener>();

let eventSource: EventSource | null = null;

function deriveEventsUrl() {
  const token = getAccessToken();
  if (!token) {
    return null;
  }
  const params = new URLSearchParams({ access_token: token });
  return `${API_BASE_URL}/events?${params.toString()}`;
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

export function ensureSocketConnection() {
  if (isMockApiEnabled() || eventSource) {
    return;
  }

  const url = deriveEventsUrl();
  if (!url) {
    return;
  }

  const source = new EventSource(url);
  eventSource = source;

  source.onmessage = (event) => {
    const parsed = parseRealtimeEvent(event.data);
    if (parsed) {
      notifyListeners(parsed);
    }
  };

  source.onerror = () => {
    // EventSource auto-reconnects by default — no manual reconnect needed
    // If the connection is permanently dead, the browser keeps retrying
  };
}

export function subscribeToRealtimeUpdates(listener: RealtimeListener) {
  if (isMockApiEnabled()) {
    return subscribeToMockRealtimeUpdates(listener);
  }

  realtimeListeners.add(listener);
  ensureSocketConnection();

  return () => {
    realtimeListeners.delete(listener);
  };
}
