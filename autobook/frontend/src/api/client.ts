import { mockApi } from "../mocks/mockApi";
import { isMockApiEnabled } from "../config/env";
import { getAccessToken } from "./auth";
import type {
  ClarificationsResponse,
  LedgerResponse,
  ParseAccepted,
  ParseStatus,
  ParseRequest,
  ResolveClarificationRequest,
  ResolveClarificationResponse,
  StatementsResponse,
  TransactionInputSource,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function deriveUploadSource(file: File): Extract<TransactionInputSource, "csv_upload" | "pdf_upload"> {
  const fileName = file.name.toLowerCase();
  if (file.type === "text/csv" || fileName.endsWith(".csv")) {
    return "csv_upload";
  }

  if (file.type === "application/pdf" || fileName.endsWith(".pdf")) {
    return "pdf_upload";
  }

  throw new Error("Unsupported file type. Upload a CSV or text-based PDF.");
}

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
  if (isMockApiEnabled()) {
    return mockApi.parseTransaction(input);
  }

  return request<ParseAccepted>("/parse", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function uploadTransactionFile(
  file: File,
  options?: Pick<ParseRequest, "stages" | "store" | "post_stages">,
): Promise<ParseAccepted> {
  if (isMockApiEnabled()) {
    return mockApi.uploadTransactionFile(file, options);
  }

  const source = deriveUploadSource(file);
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source", source);
  if (options?.store !== undefined) {
    formData.append("store", String(options.store));
  }
  for (const stage of options?.stages ?? []) {
    formData.append("stages", stage);
  }
  for (const stage of options?.post_stages ?? []) {
    formData.append("post_stages", stage);
  }

  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}/parse/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as ParseAccepted;
}

export async function getParseStatus(parseId: string): Promise<ParseStatus> {
  if (isMockApiEnabled()) {
    throw new Error("Parse status polling is unavailable in mock mode.");
  }

  return request<ParseStatus>(`/parse/${parseId}`);
}

export async function getClarifications(): Promise<ClarificationsResponse> {
  if (isMockApiEnabled()) {
    return mockApi.getClarifications();
  }

  return request<ClarificationsResponse>("/clarifications");
}

export async function resolveClarification(
  clarificationId: string,
  input: ResolveClarificationRequest,
): Promise<ResolveClarificationResponse> {
  if (isMockApiEnabled()) {
    return mockApi.resolveClarification(clarificationId, input);
  }

  return request<ResolveClarificationResponse>(`/clarifications/${clarificationId}/resolve`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getLedger(): Promise<LedgerResponse> {
  if (isMockApiEnabled()) {
    return mockApi.getLedger();
  }

  return request<LedgerResponse>("/ledger");
}

export async function getStatements(): Promise<StatementsResponse> {
  if (isMockApiEnabled()) {
    return mockApi.getStatements();
  }

  return request<StatementsResponse>("/statements");
}
