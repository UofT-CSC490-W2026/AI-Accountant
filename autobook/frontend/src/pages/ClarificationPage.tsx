import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClarifications, resolveClarification } from "../api/clarifications";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import type { ClarificationItem, JournalLine } from "../api/types";
import { ClarificationList } from "../components/ClarificationList";
import { FreshnessStatus } from "../components/FreshnessStatus";

export function ClarificationPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ClarificationItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<ClarificationItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "warning"; text: string } | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [draftLines, setDraftLines] = useState<JournalLine[]>([]);

  useEffect(() => {
    let isMounted = true;

    async function syncClarifications() {
      await loadClarifications(isMounted);
    }

    void syncClarifications();
    const unsubscribe = subscribeToRealtimeUpdates(() => {
      void syncClarifications();
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    setDraftLines(selectedItem ? cloneLines(selectedItem.proposed_entry.lines) : []);
  }, [selectedItem]);

  async function loadClarifications(isMounted = true) {
    if (!isMounted) {
      return;
    }

    setIsLoading(true);
    const response = await getClarifications();
    if (!isMounted) {
      return;
    }

    setItems(response.items);
    setSelectedItem((currentItem) => {
      if (!currentItem) {
        return response.items[0] ?? null;
      }

      return (
        response.items.find((item) => item.clarification_id === currentItem.clarification_id) ??
        response.items[0] ??
        null
      );
    });
    setIsLoading(false);
    setLastUpdatedAt(new Date());
  }

  async function handleResolve(action: "approve" | "reject") {
    if (!selectedItem) {
      return;
    }

    setIsResolving(true);
    const currentItem = selectedItem;
    const hasDraftChanges = linesHaveChanged(currentItem.proposed_entry.lines, draftLines);
    const response = await resolveClarification(selectedItem.clarification_id, {
      action: action === "approve" && hasDraftChanges ? "edit" : action,
      edited_entry: action === "approve" && hasDraftChanges ? { lines: cloneLines(draftLines) } : undefined,
    });
    await loadClarifications();
    setMessage({
      tone: response.status === "resolved" ? "success" : "warning",
      text:
        response.status === "resolved"
          ? hasDraftChanges
            ? `Clarification for "${currentItem.source_text}" was updated and posted.`
            : `Clarification for "${currentItem.source_text}" was approved and posted.`
          : `Clarification for "${currentItem.source_text}" was rejected and removed from the queue.`,
    });
    setIsResolving(false);
  }

  function handleSelect(item: ClarificationItem) {
    setSelectedItem(item);
    setMessage(null);
  }

  function updateDraftLine(
    index: number,
    field: keyof JournalLine,
    value: string,
  ) {
    setDraftLines((currentLines) =>
      currentLines.map((line, lineIndex) => {
        if (lineIndex !== index) {
          return line;
        }

        if (field === "amount") {
          const nextAmount = Number.parseFloat(value);
          return {
            ...line,
            amount: Number.isFinite(nextAmount) ? nextAmount : 0,
          };
        }

        if (field === "type") {
          return {
            ...line,
            type: value === "credit" ? "credit" : "debit",
          };
        }

        return {
          ...line,
          [field]: value,
        };
      }),
    );
  }

  function resetDraft() {
    if (!selectedItem) {
      return;
    }
    setDraftLines(cloneLines(selectedItem.proposed_entry.lines));
  }

  const hasDraftChanges = selectedItem
    ? linesHaveChanged(selectedItem.proposed_entry.lines, draftLines)
    : false;

  return (
    <div className="two-column-grid">
      <section className="panel">
        <div className="panel-header panel-header-spread">
          <div>
            <p className="eyebrow">Queue</p>
            <h2>Clarifications</h2>
          </div>
          <div className="panel-meta-cluster">
            <span className="count-pill">{items.length} pending</span>
            <FreshnessStatus label="Queue Synced" lastUpdatedAt={lastUpdatedAt} />
          </div>
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
              Review the proposed journal lines, then edit any incorrect account mapping before posting to the ledger.
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Account</th>
                    <th>Type</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {draftLines.map((line, index) => (
                    <tr key={`${selectedItem.clarification_id}-${index}`}>
                      <td>
                        <input
                          aria-label={`Account code ${index + 1}`}
                          className="text-input"
                          value={line.account_code}
                          onChange={(event) => updateDraftLine(index, "account_code", event.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          aria-label={`Account name ${index + 1}`}
                          className="text-input"
                          value={line.account_name}
                          onChange={(event) => updateDraftLine(index, "account_name", event.target.value)}
                        />
                      </td>
                      <td className="type-cell">
                        <select
                          aria-label={`Line type ${index + 1}`}
                          className="text-input"
                          value={line.type}
                          onChange={(event) => updateDraftLine(index, "type", event.target.value)}
                        >
                          <option value="debit">debit</option>
                          <option value="credit">credit</option>
                        </select>
                      </td>
                      <td>
                        <input
                          aria-label={`Amount ${index + 1}`}
                          className="text-input"
                          min="0"
                          step="0.01"
                          type="number"
                          value={line.amount}
                          onChange={(event) => updateDraftLine(index, "amount", event.target.value)}
                        />
                      </td>
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
                {isResolving ? "Saving..." : hasDraftChanges ? "Save Changes & Post" : "Approve & Post"}
              </button>
              <button
                className="secondary-button"
                onClick={resetDraft}
                disabled={isResolving || !hasDraftChanges}
              >
                Reset Draft
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

function cloneLines(lines: JournalLine[]): JournalLine[] {
  return lines.map((line) => ({ ...line }));
}

function linesHaveChanged(originalLines: JournalLine[], draftLines: JournalLine[]): boolean {
  return JSON.stringify(originalLines) !== JSON.stringify(draftLines);
}
