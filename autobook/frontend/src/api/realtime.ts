import { subscribeToRealtimeUpdates as subscribeToMockRealtimeUpdates } from "../mocks/mockApi";
import { isMockApiEnabled } from "../config/env";
import { getAccessToken } from "./auth";
import type { RealtimeEvent, RealtimeListener } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const realtimeListeners = new Set<RealtimeListener>();

let eventSource: EventSource | null = null;
let connectionKey: string | null = null;
let connectionReady: Promise<void> | null = null;
let resolveConnectionReady: (() => void) | null = null;

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
        parsed.type === "clarification.resolved" ||
        parsed.type === "pipeline.result" ||
        parsed.type === "pipeline.error") &&
      typeof parsed.occurred_at === "string"
    ) {
      return parsed as RealtimeEvent;
    }
  } catch {
    return null;
  }

  return null;
}

function resetConnectionState() {
  eventSource = null;
  connectionKey = null;
  connectionReady = null;
  resolveConnectionReady = null;
}

export function disconnectRealtimeUpdates() {
  if (eventSource) {
    eventSource.close();
  }
  resetConnectionState();
}

function connectEventSource(url: string): Promise<void> {
  connectionReady = new Promise<void>((resolve) => {
    resolveConnectionReady = resolve;
  });

  const source = new EventSource(url);
  eventSource = source;
  connectionKey = url;

  source.onopen = () => {
    resolveConnectionReady?.();
    resolveConnectionReady = null;
  };

  source.onmessage = (event) => {
    const parsed = parseRealtimeEvent(event.data);
    if (parsed) {
      notifyListeners(parsed);
    }
  };

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED && eventSource === source) {
      resetConnectionState();
    }
  };

  return connectionReady;
}

export function ensureConnection(): Promise<void> {
  if (isMockApiEnabled()) {
    return Promise.resolve();
  }

  const sseUrl = deriveEventsUrl();
  if (!sseUrl) {
    disconnectRealtimeUpdates();
    return Promise.resolve();
  }

  if (eventSource && connectionKey === sseUrl && connectionReady) {
    return connectionReady;
  }

  disconnectRealtimeUpdates();
  return connectEventSource(sseUrl);
}

export async function waitForRealtimeConnection(timeoutMs = 1500) {
  await Promise.race([
    ensureConnection(),
    new Promise<void>((resolve) => {
      window.setTimeout(resolve, timeoutMs);
    }),
  ]);
}

export function subscribeToRealtimeUpdates(listener: RealtimeListener) {
  if (isMockApiEnabled()) {
    return subscribeToMockRealtimeUpdates(listener);
  }

  realtimeListeners.add(listener);
  void ensureConnection();

  return () => {
    realtimeListeners.delete(listener);
  };
}
