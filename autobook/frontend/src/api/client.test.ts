import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

describe("api client user scoping", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test("adds userId query param to read APIs and resolve", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_user_id", "demo-user-1");

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");

    await client.getClarifications();
    await client.resolveClarification("cl_123", { action: "approve" });
    await client.getLedger();
    await client.getStatements();

    expect(calls[0].url).toBe("http://localhost:8000/api/v1/clarifications?userId=demo-user-1");
    expect(calls[1].url).toBe(
      "http://localhost:8000/api/v1/clarifications/cl_123/resolve?userId=demo-user-1",
    );
    expect(calls[2].url).toBe("http://localhost:8000/api/v1/ledger?userId=demo-user-1");
    expect(calls[3].url).toBe("http://localhost:8000/api/v1/statements?userId=demo-user-1");
  });

  test("includes user_id in upload form data", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_user_id", "demo-user-1");

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response('{"parse_id":"parse_1","status":"accepted"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");
    const file = new File(["fake-bytes"], "receipt-demo.png", { type: "image/png" });

    await client.uploadTransactionFile(file);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("http://localhost:8000/api/v1/parse/upload");
    const formData = calls[0].init?.body as FormData;
    expect(formData.get("user_id")).toBe("demo-user-1");
    expect(formData.get("file")).toBeInstanceOf(File);
  });
});
