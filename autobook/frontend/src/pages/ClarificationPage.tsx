import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClarifications, resolveClarification } from "../api/clarifications";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import type { ClarificationItem } from "../api/types";
import { ClarificationList } from "../components/ClarificationList";

export function ClarificationPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ClarificationItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<ClarificationItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "warning"; text: string } | null>(null);

  useEffect(() => {
    void loadClarifications();
    const unsub = subscribeToRealtimeUpdates((event) => {
      if (event.type === "clarification.created" || event.type === "clarification.resolved") {
        void loadClarifications();
      }
    });
    return unsub;
  }, []);

  async function loadClarifications() {
    setIsLoading(true);
    const response = await getClarifications();
    setItems(response.items);
    setSelectedItem(response.items[0] ?? null);
    setIsLoading(false);
  }

  async function handleResolve(action: "approve" | "reject") {
    if (!selectedItem) {
      return;
    }

    setIsResolving(true);
    const currentItem = selectedItem;
    const response = await resolveClarification(selectedItem.clarification_id, { action });
    await loadClarifications();
    setMessage({
      tone: response.status === "resolved" ? "success" : "warning",
      text:
        response.status === "resolved"
          ? `Clarification for "${currentItem.source_text}" was approved and posted.`
          : `Clarification for "${currentItem.source_text}" was rejected and removed from the queue.`,
    });
    setIsResolving(false);
  }

  function handleSelect(item: ClarificationItem) {
    setSelectedItem(item);
    setMessage(null);
  }

  return (
    <div className="two-column-grid">
      <section className="panel">
        <div className="panel-header panel-header-spread">
          <div>
            <p className="eyebrow">Queue</p>
            <h2>Clarifications</h2>
          </div>
          <span className="count-pill">{items.length} pending</span>
        </div>
        <p className="body-copy queue-intro">
          Review low-confidence transactions before they touch the ledger. This is the human-in-the-loop control point.
        </p>
        {isLoading ? (
          <p className="body-copy">Loading clarification tasks...</p>
        ) : (
          <ClarificationList
            items={items}
            selectedId={selectedItem?.clarification_id ?? null}
            onSelect={handleSelect}
          />
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Review</p>
            <h2>Selected Item</h2>
          </div>
        </div>

        {!selectedItem ? (
          <div className="empty-review-state">
            <p className="review-title">No pending clarifications.</p>
            <p className="body-copy">
              The queue is clear. You can generate another ambiguous transaction from the transaction page.
            </p>
            <div className="panel-actions">
              <button className="primary-button" onClick={() => navigate("/")}>
                Back to Transaction Page
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="review-meta-row">
              <span className="review-pill">ID {selectedItem.clarification_id}</span>
              <span className="review-pill review-pill-accent">
                Confidence {selectedItem.confidence.overall.toFixed(2)}
              </span>
            </div>
            <p className="review-title">{selectedItem.source_text}</p>
            <p className="body-copy">{selectedItem.explanation}</p>
            <div className="review-note">
              Confirm whether the proposed debit side reflects the real business intent before approving.
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
                  {selectedItem.proposed_entry.lines.map((line) => (
                    <tr key={`${selectedItem.clarification_id}-${line.account_code}-${line.type}`}>
                      <td>{line.account_name}</td>
                      <td className="type-cell">{line.type}</td>
                      <td>${line.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel-actions">
              <button
                className="primary-button"
                onClick={() => void handleResolve("approve")}
                disabled={isResolving}
              >
                {isResolving ? "Saving..." : "Approve"}
              </button>
              <button
                className="secondary-button"
                onClick={() => void handleResolve("reject")}
                disabled={isResolving}
              >
                Reject
              </button>
            </div>
          </>
        )}

        {message ? (
          <p className={message.tone === "success" ? "success-copy" : "warning-copy"}>
            {message.text}
          </p>
        ) : null}
      </section>
    </div>
  );
}
