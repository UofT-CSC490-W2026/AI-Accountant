import { buildStatementsCsv } from "./statementsExport";
import type { StatementsResponse } from "../api/types";

describe("buildStatementsCsv", () => {
  test("formats sections and totals into csv output", () => {
    const statements: StatementsResponse = {
      statement_type: "balance_sheet",
      period: {
        as_of: "2026-03-17",
      },
      sections: [
        {
          title: "Assets",
          rows: [
            { label: "Cash", amount: 2400 },
            { label: "Equipment", amount: 2400 },
          ],
        },
      ],
      totals: {
        total_assets: 4800,
      },
    };

    const csv = buildStatementsCsv(statements);

    expect(csv).toContain("Statement Type,balance_sheet");
    expect(csv).toContain("Assets");
    expect(csv).toContain("Cash,2400.00");
    expect(csv).toContain("Totals");
    expect(csv).toContain("total_assets,4800.00");
  });
});
