import type { LedgerEntry } from "../api/types";
import { formatIsoDateTime } from "../utils/dateTime";

type LedgerTableProps = {
  entries: LedgerEntry[];
};

export function LedgerTable({ entries }: LedgerTableProps) {
  const summarizeEntry = (entry: LedgerEntry) => {
    let debitTotal = 0;
    let creditTotal = 0;

    for (const line of entry.lines) {
      if (line.type === "debit") {
        debitTotal += line.amount;
      } else {
        creditTotal += line.amount;
      }
    }

    return { debitTotal, creditTotal };
  };

  return (
    <div className="table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            <th>Entry ID</th>
            <th>Generated</th>
            <th>Description</th>
            <th>Accounts</th>
            <th>Debits</th>
            <th>Credits</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const { debitTotal, creditTotal } = summarizeEntry(entry);

            return (
              <tr key={entry.journal_entry_id}>
                <td>
                  <span className="ledger-entry-id">{entry.journal_entry_id}</span>
                </td>
                <td>
                  <span>{formatIsoDateTime(entry.occurred_at ?? entry.date)}</span>
                  <span className="cell-subcopy">Posting date {entry.date}</span>
                </td>
                <td>{entry.description}</td>
                <td>
                  <ul className="line-list">
                    {entry.lines.map((line) => (
                      <li key={`${entry.journal_entry_id}-${line.account_code}-${line.type}`}>
                        {line.account_name}
                        <span className="cell-subcopy">{`${line.account_code} - ${line.type}`}</span>
                      </li>
                    ))}
                  </ul>
                </td>
                <td>${debitTotal.toFixed(2)}</td>
                <td>${creditTotal.toFixed(2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
