export function isMockApiEnabled() {
  return import.meta.env.VITE_USE_MOCK_API !== "false";
}

export function isMockAuthEnabled() {
  return isMockApiEnabled() || import.meta.env.VITE_USE_MOCK_AUTH === "true";
}

export function isAuthOnlyMockEnabled() {
  return !isMockApiEnabled() && isMockAuthEnabled();
}
