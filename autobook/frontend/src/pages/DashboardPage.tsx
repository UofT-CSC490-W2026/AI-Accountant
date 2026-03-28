import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getClarifications } from "../api/clarifications";
import { getLedger } from "../api/ledger";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import { getStatements } from "../api/statements";
import { FreshnessStatus } from "../components/FreshnessStatus";
import type { ClarificationsResponse, LedgerResponse, StatementsResponse } from "../api/types";
import { formatIsoDateTime } from "../utils/dateTime";

type DashboardState = {
  clarifications: ClarificationsResponse | null;
  ledger: LedgerResponse | null;
  statements: StatementsResponse | null;
};

function formatCurrency(amount: number | null) {
  if (amount === null) {
    return "--";
  }

  return `$${amount.toFixed(2)}`;
}

export function DashboardPage() {
  const [state, setState] = useState<DashboardState>({
    clarifications: null,
    ledger: null,
    statements: null,
  });
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboardState() {
      const [clarifications, ledger, statements] = await Promise.all([
        getClarifications(),
        getLedger(),
        getStatements(),
      ]);

      if (isMounted) {
        setState({ clarifications, ledger, statements });
        setLastUpdatedAt(new Date());
      }
    }

    void loadDashboardState();
    const unsubscribe = subscribeToRealtimeUpdates(() => {
      void loadDashboardState();
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  const latestEntry = state.ledger?.entries[0];
  const keyBalances = useMemo(() => {
    if (!state.ledger) {
      return {
        cashPosition: null,
        revenue: null,
        amountsOwing: null,
      };
    }

    const cashBalance =
      state.ledger.balances.find((balance) => balance.account_code === "1000")?.balance ??
      state.statements?.sections
        .flatMap((section) => section.rows)
        .find((row) => row.label.toLowerCase() === "cash")?.amount ??
      null;

    const accountsReceivableBalance =
      state.ledger.balances.find((balance) => balance.account_code === "1100")?.balance ?? null;

    const revenueAmount = Math.abs(
      state.ledger.entries.reduce((total, entry) => {
        for (const line of entry.lines) {
          if (line.account_name.toLowerCase().includes("revenue")) {
            total += line.type === "credit" ? line.amount : -line.amount;
          }
        }

        return total;
      }, 0),
    );

    return {
      cashPosition: cashBalance,
      revenue: revenueAmount,
      amountsOwing: accountsReceivableBalance,
    };
  }, [state.ledger, state.statements]);

  return (
    <div className="page-grid dashboard-page">
      <section className="panel hero-panel dashboard-hero dashboard-hero-panel">
        <div className="hero-copy">
          <div>
            <p className="eyebrow">Home</p>
            <h2>Operations snapshot for the AI accounting workflow.</h2>
          </div>
          <p className="body-copy">
            Use this dashboard to monitor incoming transactions, review exceptions, and jump into the ledger or statements quickly during the demo.
          </p>
        </div>
        <div className="hero-meta">
          <span className="hero-pill">Workflow live in mock-first mode</span>
          <span className="hero-pill hero-pill-muted">Three views ready for review</span>
          <FreshnessStatus
            label="Snapshot Synced"
            lastUpdatedAt={lastUpdatedAt}
            variant="hero"
          />
        </div>
      </section>

      <section className="metric-row dashboard-metrics dashboard-metrics-primary">
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-cash">
          <span className="metric-label">Cash Position</span>
          <strong>{formatCurrency(keyBalances.cashPosition)}</strong>
          <p className="body-copy">Current cash balance visible from the posted ledger snapshot.</p>
        </article>
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-revenue">
          <span className="metric-label">Revenue</span>
          <strong>{formatCurrency(keyBalances.revenue)}</strong>
          <p className="body-copy">Recognized service revenue derived from posted journal lines.</p>
        </article>
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-receivables">
          <span className="metric-label">Amounts Owing</span>
          <strong>{formatCurrency(keyBalances.amountsOwing)}</strong>
          <p className="body-copy">Open receivables still owed to the business.</p>
        </article>
      </section>

      <section className="metric-row dashboard-metrics dashboard-metrics-secondary">
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-pending">
          <span className="metric-label">Pending Clarifications</span>
          <strong>{state.clarifications?.count ?? "--"}</strong>
          <p className="body-copy">Items waiting on human review before posting.</p>
        </article>
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-posted">
          <span className="metric-label">Posted Entries</span>
          <strong>{state.ledger?.entries.length ?? "--"}</strong>
          <p className="body-copy">Journal entries currently visible in the ledger.</p>
        </article>
        <article className="metric-card dashboard-card dashboard-metric-card dashboard-metric-statements">
          <span className="metric-label">Statement Ready</span>
          <strong>{state.statements?.statement_type ? "Yes" : "--"}</strong>
          <p className="body-copy">
            Current statement template: {(state.statements?.statement_type ?? "loading").replace(/_/g, " ")}
          </p>
        </article>
      </section>

      <section className="dashboard-grid dashboard-content-grid">
        <section className="panel dashboard-section dashboard-actions-panel">
          <div className="section-subheader">
            <h3>Quick Actions</h3>
            <span className="section-subcopy">Fastest path through the product demo</span>
          </div>
          <div className="quick-actions-grid">
            <Link
              to="/transactions"
              className="quick-action-card dashboard-quick-action dashboard-quick-action-parse"
            >
              <strong>New Transaction</strong>
              <span>Parse a transaction and route it into the workflow.</span>
            </Link>
            <Link
              to="/clarifications"
              className="quick-action-card dashboard-quick-action dashboard-quick-action-review"
            >
              <strong>Clarification Queue</strong>
              <span>Review low-confidence items before posting.</span>
            </Link>
            <Link
              to="/ledger"
              className="quick-action-card dashboard-quick-action dashboard-quick-action-ledger"
            >
              <strong>Ledger View</strong>
              <span>Inspect posted entries and account balances.</span>
            </Link>
            <Link
              to="/statements"
              className="quick-action-card dashboard-quick-action dashboard-quick-action-statements"
            >
              <strong>Financial Statements</strong>
              <span>Show balance sheet style output from the ledger.</span>
            </Link>
          </div>
        </section>

        <section className="panel dashboard-section dashboard-activity-panel">
          <div className="section-subheader">
            <h3>Recent Activity</h3>
            <span className="section-subcopy">Latest available ledger signal</span>
          </div>
          {latestEntry ? (
            <div className="activity-card dashboard-activity-card">
              <span className="ledger-entry-id">{latestEntry.journal_entry_id}</span>
              <p className="review-title">{latestEntry.description}</p>
              <p className="body-copy">
                Posted at {formatIsoDateTime(latestEntry.occurred_at ?? latestEntry.date)} with{" "}
                {latestEntry.lines.length} journal lines.
              </p>
            </div>
          ) : (
            <div className="empty-review-state">
              <p className="review-title">No activity yet.</p>
              <p className="body-copy">Create or approve a transaction to populate recent activity.</p>
            </div>
          )}

          <div className="dashboard-callout dashboard-story-card">
            <p className="review-title">Why this matters</p>
            <p className="body-copy">
              The dashboard is the startup-style home screen that ties AI parsing, human review, and accounting output into one product story.
            </p>
          </div>
        </section>
      </section>
    </div>
  );
}
