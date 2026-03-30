import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

describe("api client auth contract", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("sends bearer auth on protected read APIs and resolve", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_access_token", "token-123");

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");

    await client.getClarifications();
    await client.resolveClarification("cl_123", { action: "approve" });
    await client.getLedger();
    await client.getStatements();

    for (const call of calls) {
      expect(call.init?.headers).toBeInstanceOf(Headers);
      expect((call.init?.headers as Headers).get("Authorization")).toBe("Bearer token-123");
    }

    expect(calls[0].url).toBe("http://localhost:8000/api/v1/clarifications");
    expect(calls[1].url).toBe("http://localhost:8000/api/v1/clarifications/cl_123/resolve");
    expect(calls[2].url).toBe("http://localhost:8000/api/v1/ledger");
    expect(calls[3].url).toBe("http://localhost:8000/api/v1/statements");
  });

  test("surfaces backend detail text for failed clarification requests", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_access_token", "token-123");

    globalThis.fetch = vi.fn(async () =>
      new Response('{"detail":"journal entry does not balance: debits=100 credits=50"}', {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    ) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");

    await expect(
      client.resolveClarification("cl_123", { action: "approve" }),
    ).rejects.toThrow("Request failed: 400 - journal entry does not balance: debits=100 credits=50");
  });

  test("includes upload source and bearer token in file upload requests", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_access_token", "token-123");

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response('{"parse_id":"parse_1","status":"accepted"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");
    const file = new File(["date,description,amount\n2026-03-17,Bank payment,2400"], "march-bank.csv", {
      type: "text/csv",
    });

    await client.uploadTransactionFile(file, {
      stages: ["precedent", "ml", "llm"],
      store: true,
      post_stages: ["precedent", "ml"],
    });

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("http://localhost:8000/api/v1/parse/upload");
    expect(calls[0].init?.headers).toEqual({ Authorization: "Bearer token-123" });
    const formData = calls[0].init?.body as FormData;
    expect(formData.get("source")).toBe("csv_upload");
    expect(formData.get("file")).toBeInstanceOf(File);
    expect(formData.get("store")).toBe("true");
    expect(formData.getAll("stages")).toEqual(["precedent", "ml", "llm"]);
    expect(formData.getAll("post_stages")).toEqual(["precedent", "ml"]);
  });

  test("sends manual text with the explicit manual_text source and auth header", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000/api/v1");
    localStorage.setItem("autobook_access_token", "token-123");

    const calls: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return new Response('{"parse_id":"parse_1","status":"accepted"}', {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    vi.resetModules();
    const client = await import("./client");

    await client.parseTransaction({
      input_text: "Bought a laptop for $2400",
      source: "manual_text",
      currency: "CAD",
    });

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("http://localhost:8000/api/v1/parse");
    expect((calls[0].init?.headers as Headers).get("Authorization")).toBe("Bearer token-123");
    expect(calls[0].init?.body).toBe(
      JSON.stringify({
        input_text: "Bought a laptop for $2400",
        source: "manual_text",
        currency: "CAD",
      }),
    );
  });
});
