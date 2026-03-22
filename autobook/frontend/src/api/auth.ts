const ACCESS_TOKEN_KEY = "autobook_access_token";


export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}


export function setAccessToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}


export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}
