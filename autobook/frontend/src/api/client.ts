import { mockApi } from "../mocks/mockApi";
import { getAccessToken } from "./auth";
import type {
  ClarificationsResponse,
  LedgerResponse,
  ParseAccepted,
  ParseRequest,
  ResolveClarificationRequest,
  ResolveClarificationResponse,
  StatementsResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== "false";


function buildHeaders(extraHeaders?: HeadersInit) {
  const token = getAccessToken();
  const headers = new Headers(extraHeaders);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: buildHeaders(init?.headers),
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function parseTransaction(input: ParseRequest): Promise<ParseAccepted> {
  if (USE_MOCK_API) {
    return mockApi.parseTransaction(input);
  }

  return request<ParseAccepted>("/parse", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function uploadTransactionFile(file: File): Promise<ParseAccepted> {
  if (USE_MOCK_API) {
    return mockApi.uploadTransactionFile(file);
  }

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/parse/upload`, {
    method: "POST",
    headers: (() => {
      const token = getAccessToken();
      return token ? { Authorization: `Bearer ${token}` } : undefined;
    })(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as ParseAccepted;
}

export async function getClarifications(): Promise<ClarificationsResponse> {
  if (USE_MOCK_API) {
    return mockApi.getClarifications();
  }

  return request<ClarificationsResponse>("/clarifications");
}

export async function resolveClarification(
  clarificationId: string,
  input: ResolveClarificationRequest,
): Promise<ResolveClarificationResponse> {
  if (USE_MOCK_API) {
    return mockApi.resolveClarification(clarificationId, input);
  }

  return request<ResolveClarificationResponse>(`/clarifications/${clarificationId}/resolve`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getLedger(): Promise<LedgerResponse> {
  if (USE_MOCK_API) {
    return mockApi.getLedger();
  }

  return request<LedgerResponse>("/ledger");
}

export async function getStatements(): Promise<StatementsResponse> {
  if (USE_MOCK_API) {
    return mockApi.getStatements();
  }

  return request<StatementsResponse>("/statements");
}
