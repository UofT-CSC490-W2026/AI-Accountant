import type { ParseResponse } from "../api/types";
import { StatusBadge } from "./StatusBadge";

type ParseResultCardProps = {
  result: ParseResponse;
};

export function ParseResultCard({ result }: ParseResultCardProps) {
  return (
    <section className="panel">
      <div className="panel-header panel-header-spread">
        <div>
          <p className="eyebrow">Result</p>
          <h2>Posting Recommendation</h2>
        </div>
        <StatusBadge status={result.status} />
      </div>

      <p className="body-copy">{result.explanation}</p>

      <div className="metric-row">
        <div className="metric-card">
          <span className="metric-label">Confidence</span>
          <strong>{result.confidence.overall.toFixed(2)}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Threshold</span>
          <strong>{result.confidence.auto_post_threshold?.toFixed(2) ?? "--"}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Parse Time</span>
          <strong>{result.parse_time_ms ?? "--"} ms</strong>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Type</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {result.proposed_entry.lines.map((line) => (
              <tr key={`${line.account_code}-${line.type}`}>
                <td>
                  {line.account_name}
                  <span className="cell-subcopy">{line.account_code}</span>
                </td>
                <td className="type-cell">{line.type}</td>
                <td>${line.amount.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
