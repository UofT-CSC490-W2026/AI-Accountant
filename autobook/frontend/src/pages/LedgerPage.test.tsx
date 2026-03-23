import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { parseTransaction } from "../api/parse";
import { formatIsoDateTime } from "../utils/dateTime";
import { LedgerPage } from "./LedgerPage";

function renderLedgerPage() {
  return render(
    <MemoryRouter>
      <LedgerPage />
    </MemoryRouter>,
  );
}

describe("ledger filters", () => {
  test("filters ledger entries by account and date range and can clear filters", async () => {
    renderLedgerPage();

    expect(await screen.findByRole("heading", { name: /^ledger$/i })).toBeInTheDocument();
    expect(await screen.findByText("Bought laptop for $2400")).toBeInTheDocument();
    expect(screen.getByText("Recorded client retainer invoice")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/filter by account/i), {
      target: { value: "1500" },
    });

    expect(screen.getByText("Bought laptop for $2400")).toBeInTheDocument();
    expect(screen.queryByText("Recorded client retainer invoice")).not.toBeInTheDocument();
    expect(screen.getByText(/1 entries shown/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/date to/i), {
      target: { value: "2026-03-16" },
    });

    expect(await screen.findByText(/no ledger entries match these filters/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));

    expect(await screen.findByText("Recorded client retainer invoice")).toBeInTheDocument();
    expect(screen.getByText("Bought laptop for $2400")).toBeInTheDocument();
  });

  test("shows debit and credit columns for each ledger row", async () => {
    renderLedgerPage();

    expect(await screen.findByText(/ledger synced/i)).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Generated")).toBeInTheDocument();
    expect(within(table).getByText("Debits")).toBeInTheDocument();
    expect(within(table).getByText("Credits")).toBeInTheDocument();
    expect(within(table).getByText(formatIsoDateTime("2026-03-17T14:08:12Z"))).toBeInTheDocument();
    expect(within(table).getAllByText("$2400.00")).toHaveLength(2);
    expect(within(table).getAllByText("$1500.00")).toHaveLength(2);
  });

  test("refreshes the ledger when a posted entry arrives over the live update channel", async () => {
    renderLedgerPage();

    expect(await screen.findByText("Bought laptop for $2400")).toBeInTheDocument();

    await act(async () => {
      await parseTransaction({
        input_text: "Purchased insurance policy",
        source: "manual_text",
        currency: "CAD",
      });
    });

    expect(await screen.findByText("Purchased insurance policy")).toBeInTheDocument();
  });
});
