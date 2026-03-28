import type { StatementsResponse } from "../api/types";

function escapeCsvCell(value: string | number) {
  const stringValue = String(value);
  if (/[",\n]/.test(stringValue)) {
    return `"${stringValue.replace(/"/g, "\"\"")}"`;
  }

  return stringValue;
}

export function buildStatementsCsv(statements: StatementsResponse) {
  const rows: string[][] = [
    ["Statement Type", statements.statement_type],
    [
      "Period",
      statements.period.as_of ??
        `${statements.period.from ?? ""} to ${statements.period.to ?? ""}`.trim(),
    ],
    [],
  ];

  for (const section of statements.sections) {
    rows.push([section.title]);
    rows.push(["Line Item", "Amount"]);

    for (const row of section.rows) {
      rows.push([row.label, row.amount.toFixed(2)]);
    }

    rows.push([]);
  }

  if (Object.keys(statements.totals).length > 0) {
    rows.push(["Totals"]);
    rows.push(["Label", "Amount"]);

    for (const [label, amount] of Object.entries(statements.totals)) {
      rows.push([label, amount.toFixed(2)]);
    }
  }

  return rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n");
}

export function downloadStatementsCsv(statements: StatementsResponse) {
  const csv = buildStatementsCsv(statements);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `statement-${statements.statement_type}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function exportStatementsPdf() {
  window.print();
}
