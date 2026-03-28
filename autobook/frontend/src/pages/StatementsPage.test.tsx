import { act, fireEvent, render, screen } from "@testing-library/react";
import { parseTransaction } from "../api/parse";
import { StatementsPage } from "./StatementsPage";
import { downloadStatementsCsv, exportStatementsPdf } from "../utils/statementsExport";

vi.mock("../utils/statementsExport", () => ({
  downloadStatementsCsv: vi.fn(),
  exportStatementsPdf: vi.fn(),
}));

describe("statement export controls", () => {
  test("triggers csv and pdf export actions after the statement loads", async () => {
    render(<StatementsPage />);

    expect(
      await screen.findByText(/isolates the financial statement view/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/statements synced/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));
    fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));

    expect(vi.mocked(downloadStatementsCsv)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(exportStatementsPdf)).toHaveBeenCalledTimes(1);
  });

  test("refreshes statement balances after a posted ledger update", async () => {
    render(<StatementsPage />);

    expect(await screen.findByText("$-2400.00")).toBeInTheDocument();

    await act(async () => {
      await parseTransaction({
        input_text: "Purchased office chairs",
        source: "manual_text",
        currency: "CAD",
      });
    });

    expect(await screen.findByText("$-4800.00")).toBeInTheDocument();
    expect(screen.getByText("$4800.00")).toBeInTheDocument();
  });
});
