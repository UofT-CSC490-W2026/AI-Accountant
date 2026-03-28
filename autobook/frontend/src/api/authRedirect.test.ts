import { describe, expect, test } from "vitest";
import { resolveHostedUiRedirectUrl } from "./auth";

describe("hosted auth redirect compatibility", () => {
  test("rewrites a legacy login_url payload to Cognito signup", () => {
    const url = resolveHostedUiRedirectUrl("signup", {
      login_url: "https://autobook-dev.auth.ca-central-1.amazoncognito.com/login?client_id=abc",
    });

    expect(url).toBe("https://autobook-dev.auth.ca-central-1.amazoncognito.com/signup?client_id=abc");
  });

  test("accepts the legacy login_url response shape for login", () => {
    const url = resolveHostedUiRedirectUrl("login", {
      login_url: "https://autobook-dev.auth.ca-central-1.amazoncognito.com/login?client_id=abc",
    });

    expect(url).toBe("https://autobook-dev.auth.ca-central-1.amazoncognito.com/login?client_id=abc");
  });
});
