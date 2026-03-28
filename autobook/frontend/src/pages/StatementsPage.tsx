import { useEffect, useState } from "react";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import { getStatements } from "../api/statements";
import type { StatementsResponse } from "../api/types";
import { FreshnessStatus } from "../components/FreshnessStatus";
import { downloadStatementsCsv, exportStatementsPdf } from "../utils/statementsExport";

export function StatementsPage() {
  const [statements, setStatements] = useState<StatementsResponse | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadStatements() {
      const response = await getStatements();
      if (isMounted) {
        setStatements(response);
        setLastUpdatedAt(new Date());
      }
    }

    void loadStatements();
    const unsubscribe = subscribeToRealtimeUpdates(() => {
      void loadStatements();
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-header panel-header-spread">
          <div>
            <p className="eyebrow">Financial Output</p>
            <h2>Statements</h2>
          </div>
          <div className="panel-meta-cluster">
            <FreshnessStatus label="Statements Synced" lastUpdatedAt={lastUpdatedAt} />
            <div className="panel-actions panel-actions-tight">
              <button
                className="secondary-button"
                onClick={() => statements && downloadStatementsCsv(statements)}
                disabled={!statements}
              >
                Export CSV
              </button>
              <button
                className="secondary-button"
                onClick={() => exportStatementsPdf()}
                disabled={!statements}
              >
                Export PDF
              </button>
            </div>
          </div>
        </div>

        {!statements ? (
          <p className="body-copy">Loading statements...</p>
        ) : (
          <div className="statement-stack">
            <div className="review-meta-row">
              <span className="review-pill">
                Statement {statements.statement_type.replace(/_/g, " ")}
              </span>
              <span className="review-pill review-pill-accent">
                As of {statements.period.as_of ?? "Current Period"}
              </span>
            </div>
            <p className="body-copy">
              This page isolates the financial statement view so the demo can move from ledger mechanics to business reporting cleanly.
            </p>
            <p className="field-help">
              Export the current statement package as CSV for handoff, or use PDF export for a presentation-friendly artifact.
            </p>

            {statements.sections.map((section) => (
              <section key={section.title} className="statement-section">
                <div className="section-subheader">
                  <h3>{section.title}</h3>
                  <span className="section-subcopy">{section.rows.length} line items</span>
                </div>
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Line Item</th>
                        <th>Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {section.rows.map((row) => (
                        <tr key={row.label}>
                          <td>{row.label}</td>
                          <td>${row.amount.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}

            {Object.keys(statements.totals).length > 0 ? (
              <section className="statement-totals">
                <div className="section-subheader">
                  <h3>Statement Totals</h3>
                  <span className="section-subcopy">Summary numbers for executive review</span>
                </div>
                <div className="balance-grid">
                  {Object.entries(statements.totals).map(([label, amount]) => (
                    <div key={label} className="balance-card">
                      <span className="metric-label">{label.replace(/_/g, " ")}</span>
                      <strong>${amount.toFixed(2)}</strong>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
