import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("app routing", () => {
  test("renders dashboard on the home route", async () => {
    renderRoute("/");
    expect(await screen.findByRole("heading", { name: /operations snapshot/i })).toBeInTheDocument();
    expect(screen.getByText(/live clock/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new transaction/i })).toBeInTheDocument();
  });

  test("renders transaction page on the transaction route", () => {
    renderRoute("/transactions");
    expect(
      screen.getByRole("heading", { name: /natural language transaction/i }),
    ).toBeInTheDocument();
  });

  test("renders clarification page on the clarification route", async () => {
    renderRoute("/clarifications");
    expect(await screen.findByRole("heading", { name: /clarifications/i })).toBeInTheDocument();
    expect(screen.getByText(/human-in-the-loop control point/i)).toBeInTheDocument();
  });

  test("renders ledger page on the ledger route", async () => {
    renderRoute("/ledger");
    expect(await screen.findByRole("heading", { name: /^ledger$/i })).toBeInTheDocument();
    expect(
      await screen.findByLabelText(/search by description, account name, or account code/i),
    ).toBeInTheDocument();
  });

  test("renders statements page on the statements route", async () => {
    renderRoute("/statements");
    expect(await screen.findByRole("heading", { name: /^statements$/i })).toBeInTheDocument();
    expect(await screen.findByText(/isolates the financial statement view/i)).toBeInTheDocument();
  });
});
