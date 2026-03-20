import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getLedger } from "../api/ledger";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import type { LedgerResponse } from "../api/types";
import { LedgerTable } from "../components/LedgerTable";

export function LedgerPage() {
  const navigate = useNavigate();
  const [ledger, setLedger] = useState<LedgerResponse | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [accountFilter, setAccountFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  function loadLedger() {
    return getLedger().then((response) => {
      setLedger(response);
    });
  }

  useEffect(() => {
    void loadLedger();
    const unsub = subscribeToRealtimeUpdates((event) => {
      if (event.type === "entry.posted") {
        void loadLedger();
      }
    });
    return unsub;
  }, []);

  const accountOptions = useMemo(() => {
    if (!ledger) {
      return [];
    }

    const uniqueAccounts = new Map<string, string>();
    for (const entry of ledger.entries) {
      for (const line of entry.lines) {
        uniqueAccounts.set(line.account_code, line.account_name);
      }
    }

    return Array.from(uniqueAccounts.entries())
      .map(([accountCode, accountName]) => ({
        accountCode,
        accountName,
      }))
      .sort((left, right) => left.accountCode.localeCompare(right.accountCode));
  }, [ledger]);

  const filteredEntries = useMemo(() => {
    if (!ledger) {
      return [];
    }

    const normalized = searchTerm.trim().toLowerCase();

    return ledger.entries.filter((entry) => {
      const matchesSearch =
        !normalized ||
        entry.description.toLowerCase().includes(normalized) ||
        entry.lines.some(
          (line) =>
            line.account_name.toLowerCase().includes(normalized) ||
            line.account_code.toLowerCase().includes(normalized),
        );
      const matchesAccount =
        accountFilter === "all" ||
        entry.lines.some((line) => line.account_code === accountFilter);
      const matchesFrom = !dateFrom || entry.date >= dateFrom;
      const matchesTo = !dateTo || entry.date <= dateTo;

      return matchesSearch && matchesAccount && matchesFrom && matchesTo;
    });
  }, [accountFilter, dateFrom, dateTo, ledger, searchTerm]);

  const clearFilters = () => {
    setSearchTerm("");
    setAccountFilter("all");
    setDateFrom("");
    setDateTo("");
  };

  const hasActiveFilters =
    searchTerm.trim().length > 0 || accountFilter !== "all" || dateFrom.length > 0 || dateTo.length > 0;

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-header panel-header-spread">
          <div>
            <p className="eyebrow">Accounting Output</p>
            <h2>Ledger</h2>
          </div>
          <div className="panel-actions panel-actions-tight">
            <button className="secondary-button" onClick={() => navigate("/statements")}>
              Open Statements
            </button>
          </div>
        </div>
        <p className="body-copy ledger-intro">
          Inspect posted entries, confirm the ledger remains balanced, and filter by date, account, or description during the demo.
        </p>

        {ledger ? (
          <>
            <div className="metric-row">
              <div className="metric-card">
                <span className="metric-label">Posted Entries</span>
                <strong>{ledger.entries.length}</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Total Debits</span>
                <strong>${ledger.summary.total_debits.toFixed(2)}</strong>
              </div>
              <div className="metric-card">
                <span className="metric-label">Total Credits</span>
                <strong>${ledger.summary.total_credits.toFixed(2)}</strong>
              </div>
            </div>

            <div
              className={
                ledger.summary.total_debits === ledger.summary.total_credits
                  ? "integrity-banner integrity-balanced"
                  : "integrity-banner integrity-warning"
              }
            >
              {ledger.summary.total_debits === ledger.summary.total_credits
                ? "Ledger integrity check passed: debits and credits are balanced."
                : "Ledger integrity warning: debits and credits do not match."}
            </div>

            <section className="panel compact-panel filter-panel">
              <div className="section-subheader">
                <h3>Filter Ledger</h3>
                <span className="section-subcopy">{filteredEntries.length} entries shown</span>
              </div>
              <div className="filter-grid">
                <div>
                  <label className="field-label" htmlFor="ledger-search">
                    Search by description, account name, or account code
                  </label>
                  <input
                    id="ledger-search"
                    className="text-input"
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Try equipment, cash, or laptop"
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="ledger-account-filter">
                    Filter by account
                  </label>
                  <select
                    id="ledger-account-filter"
                    className="text-input"
                    value={accountFilter}
                    onChange={(event) => setAccountFilter(event.target.value)}
                  >
                    <option value="all">All accounts</option>
                    {accountOptions.map((account) => (
                      <option key={account.accountCode} value={account.accountCode}>
                        {account.accountCode} - {account.accountName}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label" htmlFor="ledger-date-from">
                    Date from
                  </label>
                  <input
                    id="ledger-date-from"
                    className="text-input"
                    type="date"
                    value={dateFrom}
                    onChange={(event) => setDateFrom(event.target.value)}
                  />
                </div>
                <div>
                  <label className="field-label" htmlFor="ledger-date-to">
                    Date to
                  </label>
                  <input
                    id="ledger-date-to"
                    className="text-input"
                    type="date"
                    value={dateTo}
                    onChange={(event) => setDateTo(event.target.value)}
                  />
                </div>
              </div>
              <div className="panel-actions">
                <button className="secondary-button" onClick={clearFilters} disabled={!hasActiveFilters}>
                  Clear Filters
                </button>
              </div>
            </section>

            {ledger.balances.length > 0 ? (
              <section className="balance-preview">
                <div className="section-subheader">
                  <h3>Account Balances</h3>
                  <span className="section-subcopy">Snapshot derived from posted entries</span>
                </div>
                <div className="balance-grid">
                  {ledger.balances.map((balance) => (
                    <div key={balance.account_code} className="balance-card">
                      <span className="metric-label">{balance.account_name}</span>
                      <strong>${balance.balance.toFixed(2)}</strong>
                      <span className="cell-subcopy">{balance.account_code}</span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {filteredEntries.length > 0 ? (
              <LedgerTable entries={filteredEntries} />
            ) : (
              <div className="empty-review-state panel compact-panel">
                <p className="review-title">No ledger entries match these filters.</p>
                <p className="body-copy">Adjust the account or date range, or clear filters to return to the full ledger.</p>
              </div>
            )}
          </>
        ) : (
          <p className="body-copy">Loading ledger...</p>
        )}
      </section>
    </div>
  );
}
