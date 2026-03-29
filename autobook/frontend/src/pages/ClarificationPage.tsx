import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClarifications, resolveClarification } from "../api/clarifications";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import type { ClarificationItem, JournalLine } from "../api/types";
import { ClarificationList } from "../components/ClarificationList";
import { FreshnessStatus } from "../components/FreshnessStatus";

const EMPTY_LINE: JournalLine = {
  account_code: "",
  account_name: "",
  type: "debit",
  amount: 0,
};

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
    setDraftLines(
      selectedItem?.proposed_entry
        ? cloneLines(selectedItem.proposed_entry.lines)
        : [createEmptyLine("debit"), createEmptyLine("credit")],
    );
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

    try {
      setIsResolving(true);
      const currentItem = selectedItem;
      const hasDraftChanges = currentItem.proposed_entry
        ? linesHaveChanged(currentItem.proposed_entry.lines, draftLines)
        : linesContainUserInput(draftLines);
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
    } catch (error) {
      setMessage({
        tone: "warning",
        text: error instanceof Error ? error.message : "Unable to resolve clarification.",
      });
    } finally {
      setIsResolving(false);
    }
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
    setDraftLines(
      selectedItem.proposed_entry
        ? cloneLines(selectedItem.proposed_entry.lines)
        : [createEmptyLine("debit"), createEmptyLine("credit")],
    );
  }

  function addDraftLine() {
    setDraftLines((currentLines) => [
      ...currentLines,
      createEmptyLine(currentLines.length % 2 === 0 ? "debit" : "credit"),
    ]);
  }

  function removeDraftLine(index: number) {
    setDraftLines((currentLines) => currentLines.filter((_, lineIndex) => lineIndex !== index));
  }

  const hasDraftChanges = selectedItem?.proposed_entry
    ? linesHaveChanged(selectedItem.proposed_entry.lines, draftLines)
    : linesContainUserInput(draftLines);
  const canApprove = canApproveDraft(draftLines);

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
              {selectedItem.proposed_entry
                ? "Review the proposed journal lines, then edit any incorrect account mapping before posting to the ledger."
                : "No journal entry was generated. Build the debit and credit lines manually, then approve to post it."}
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Account</th>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Actions</th>
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
                      <td>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => removeDraftLine(index)}
                          disabled={isResolving || draftLines.length <= 2}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {!canApprove ? (
              <div className="review-note">
                Enter at least one balanced debit and credit line with valid account codes before posting.
              </div>
            ) : null}

            <div className="panel-actions">
              <button
                className="primary-button"
                onClick={() => void handleResolve("approve")}
                disabled={isResolving || !canApprove}
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
                onClick={addDraftLine}
                disabled={isResolving}
              >
                Add Line
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

function linesContainUserInput(lines: JournalLine[]): boolean {
  return lines.some((line) =>
    line.account_code.trim() ||
    line.account_name.trim() ||
    line.amount > 0,
  );
}

function canApproveDraft(lines: JournalLine[]): boolean {
  if (lines.length < 2) {
    return false;
  }

  let debitTotal = 0;
  let creditTotal = 0;

  for (const line of lines) {
    if (!line.account_code.trim() || !line.account_name.trim() || line.amount <= 0) {
      return false;
    }

    if (line.type === "debit") {
      debitTotal += line.amount;
    } else {
      creditTotal += line.amount;
    }
  }

  return Math.abs(debitTotal - creditTotal) < 0.0001;
}

function createEmptyLine(type: JournalLine["type"]): JournalLine {
  return { ...EMPTY_LINE, type };
}
