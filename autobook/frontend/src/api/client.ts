import { mockApi } from "../mocks/mockApi";
import { getUserId } from "./realtime";
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

function withUserId(path: string) {
  const url = new URL(`${API_BASE_URL}${path}`);
  url.searchParams.set("userId", getUserId());
  return url.toString();
}

async function request<T>(path: string, init?: RequestInit, includeUserId = false): Promise<T> {
  const target = includeUserId ? withUserId(path) : `${API_BASE_URL}${path}`;
  const response = await fetch(target, {
    headers: {
      "Content-Type": "application/json",
    },
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
    body: JSON.stringify({ ...input, user_id: getUserId() }),
  });
}

export async function uploadTransactionFile(file: File): Promise<ParseAccepted> {
  if (USE_MOCK_API) {
    return mockApi.uploadTransactionFile(file);
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", getUserId());

  const response = await fetch(`${API_BASE_URL}/parse/upload`, {
    method: "POST",
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

  return request<ClarificationsResponse>("/clarifications", undefined, true);
}

export async function resolveClarification(
  clarificationId: string,
  input: ResolveClarificationRequest,
): Promise<ResolveClarificationResponse> {
  if (USE_MOCK_API) {
    return mockApi.resolveClarification(clarificationId, input);
  }

  return request<ResolveClarificationResponse>(
    `/clarifications/${clarificationId}/resolve`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    true,
  );
}

export async function getLedger(): Promise<LedgerResponse> {
  if (USE_MOCK_API) {
    return mockApi.getLedger();
  }

  return request<LedgerResponse>("/ledger", undefined, true);
}

export async function getStatements(): Promise<StatementsResponse> {
  if (USE_MOCK_API) {
    return mockApi.getStatements();
  }

  return request<StatementsResponse>("/statements", undefined, true);
}
