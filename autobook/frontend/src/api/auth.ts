import type { AuthTokenResponse, AuthUser } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API !== "false";
const ACCESS_TOKEN_KEY = "autobook_access_token";
const REFRESH_TOKEN_KEY = "autobook_refresh_token";
const PKCE_VERIFIER_KEY = "autobook_pkce_verifier";
const PKCE_STATE_KEY = "autobook_pkce_state";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setRefreshToken(token: string | null) {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
    return;
  }
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function clearAuthSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(PKCE_STATE_KEY);
}

export async function fetchAuthMe(): Promise<AuthUser> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("Missing access token.");
  }

  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Auth validation failed: ${response.status}`);
  }
  return (await response.json()) as AuthUser;
}

export async function beginHostedLogin(): Promise<void> {
  if (USE_MOCK_API) {
    setAccessToken("mock-access-token");
    return;
  }

  const verifier = randomString(64);
  const state = randomString(32);
  const challenge = await createPkceChallenge(verifier);
  const redirectUri = `${window.location.origin}/auth/callback`;
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  sessionStorage.setItem(PKCE_STATE_KEY, state);

  const url = new URL(`${API_BASE_URL}/auth/login-url`);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("state", state);

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Unable to start login: ${response.status}`);
  }

  const payload = (await response.json()) as { login_url: string };
  window.location.assign(payload.login_url);
}

export async function completeHostedLogin(search: string): Promise<AuthUser> {
  const params = new URLSearchParams(search);
  const code = params.get("code");
  const state = params.get("state");
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  const expectedState = sessionStorage.getItem(PKCE_STATE_KEY);

  if (!code || !verifier) {
    throw new Error("Missing Cognito callback parameters.");
  }
  if (!state || state !== expectedState) {
    throw new Error("Invalid auth callback state.");
  }

  const response = await fetch(`${API_BASE_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      redirect_uri: `${window.location.origin}/auth/callback`,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) {
    throw new Error(`Token exchange failed: ${response.status}`);
  }

  const payload = (await response.json()) as AuthTokenResponse;
  persistTokenResponse(payload);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(PKCE_STATE_KEY);
  return fetchAuthMe();
}

export async function refreshAuthSession(): Promise<AuthUser> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("Missing refresh token.");
  }

  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    throw new Error(`Token refresh failed: ${response.status}`);
  }

  const payload = (await response.json()) as AuthTokenResponse;
  persistTokenResponse({
    ...payload,
    refresh_token: payload.refresh_token ?? refreshToken,
  });
  return fetchAuthMe();
}

export async function beginLogout(): Promise<void> {
  if (USE_MOCK_API) {
    clearAuthSession();
    return;
  }

  const response = await fetch(
    `${API_BASE_URL}/auth/logout-url?logout_uri=${encodeURIComponent(`${window.location.origin}/login`)}`,
  );
  clearAuthSession();
  if (!response.ok) {
    return;
  }

  const payload = (await response.json()) as { logout_url: string };
  window.location.assign(payload.logout_url);
}

function persistTokenResponse(payload: AuthTokenResponse) {
  setAccessToken(payload.access_token);
  setRefreshToken(payload.refresh_token ?? null);
}

function randomString(length: number): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes).slice(0, length);
}

async function createPkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

function base64UrlEncode(bytes: Uint8Array): string {
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
