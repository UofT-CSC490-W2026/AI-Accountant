import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import App from "./App";
import { AuthProvider } from "./auth/AuthProvider";

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  localStorage.clear();
  sessionStorage.clear();
});

function enableMockSession() {
  vi.stubEnv("VITE_USE_MOCK_API", "true");
  localStorage.setItem("autobook_access_token", "mock-access-token");
}

describe("app routing", () => {
  test("renders dashboard on the home route", async () => {
    enableMockSession();
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: /operations snapshot/i })).toBeInTheDocument();
    expect(screen.getByText(/live clock/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new transaction/i })).toBeInTheDocument();
  });

  test("renders transaction page on the transaction route", () => {
    enableMockSession();
    renderRoute("/transactions");
    expect(
      screen.getByRole("heading", { name: /translate plain language into ledger-ready journal entries/i }),
    ).toBeInTheDocument();
  });

  test("renders clarification page on the clarification route", async () => {
    enableMockSession();
    renderRoute("/clarifications");
    expect(await screen.findByRole("heading", { name: /clarifications/i })).toBeInTheDocument();
    expect(screen.getByText(/human-in-the-loop control point/i)).toBeInTheDocument();
  });

  test("renders ledger page on the ledger route", async () => {
    enableMockSession();
    renderRoute("/ledger");
    expect(await screen.findByRole("heading", { name: /^ledger$/i })).toBeInTheDocument();
    expect(
      await screen.findByLabelText(/search by description, account name, or account code/i),
    ).toBeInTheDocument();
  });

  test("renders statements page on the statements route", async () => {
    enableMockSession();
    renderRoute("/statements");
    expect(await screen.findByRole("heading", { name: /^statements$/i })).toBeInTheDocument();
    expect(await screen.findByText(/isolates the financial statement view/i)).toBeInTheDocument();
  });

  test("redirects protected routes to login when auth is required and no token is present", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    renderRoute("/ledger");
    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with cognito/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  test("auth-only demo mode shows demo sign-in controls while leaving full api mock disabled", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_USE_MOCK_AUTH", "true");
    renderRoute("/login");

    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /demo sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /demo register/i })).toBeInTheDocument();
    expect(screen.getByText(/rest of the app still talks to the real backend apis/i)).toBeInTheDocument();
  });

  test("demo auth mode signs in as the entered email when mock api is enabled", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "true");
    renderRoute("/login");

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "teammate@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "anything-works" },
    });
    fireEvent.click(screen.getByRole("button", { name: /demo sign in/i }));

    expect(await screen.findByRole("heading", { name: /operations snapshot/i })).toBeInTheDocument();
    expect(screen.getByText(/teammate@example\.com/i)).toBeInTheDocument();
  });

  test("redirects callback without oauth params back to login with a sign-in notice", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    renderRoute("/auth/callback");

    expect(await screen.findByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/account verified\. sign in to continue\./i);
  });

  test("processes the auth callback only once in strict mode", async () => {
    vi.stubEnv("VITE_USE_MOCK_API", "false");

    const completeHostedLogin = vi.fn(async () => ({
      id: "user-1",
      cognito_sub: "sub-1",
      email: "user@example.com",
      role: "regular",
      role_source: "cognito:groups",
      token_use: "access",
    }));

    vi.doMock("./api/auth", async () => {
      const actual = await vi.importActual<typeof import("./api/auth")>("./api/auth");
      return {
        ...actual,
        fetchAuthMe: vi.fn(async () => ({
          id: "user-1",
          cognito_sub: "sub-1",
          email: "user@example.com",
          role: "regular",
          role_source: "cognito:groups",
          token_use: "access",
        })),
        completeHostedLogin,
      };
    });

    vi.resetModules();
    const StrictApp = (await import("./App")).default;
    const { AuthProvider: StrictAuthProvider } = await import("./auth/AuthProvider");

    render(
      <React.StrictMode>
        <MemoryRouter initialEntries={["/auth/callback?code=abc&state=state-123"]}>
          <StrictAuthProvider>
            <StrictApp />
          </StrictAuthProvider>
        </MemoryRouter>
      </React.StrictMode>,
    );

    expect(await screen.findByRole("heading", { name: /operations snapshot/i })).toBeInTheDocument();
    expect(completeHostedLogin).toHaveBeenCalledTimes(1);
  });
});
