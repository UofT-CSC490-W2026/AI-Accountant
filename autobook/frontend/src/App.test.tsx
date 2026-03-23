import { render, screen } from "@testing-library/react";
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
  });
});
