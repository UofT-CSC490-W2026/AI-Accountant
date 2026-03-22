import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { parseTransaction, uploadTransactionFile } from "../api/parse";
import { subscribeToRealtimeUpdates } from "../api/realtime";
import type { RealtimeEvent } from "../api/types";
import { FreshnessStatus } from "../components/FreshnessStatus";
import { TransactionForm } from "../components/TransactionForm";

const sampleTransactions = [
  "Bought a laptop for $2400",
  "Transferred money",
  "Paid contractor 600 for website work",
];

export function TransactionPage() {
  const navigate = useNavigate();
  const [input, setInput] = useState("Bought a laptop for $2400");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [resolvedEvent, setResolvedEvent] = useState<RealtimeEvent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const isMockMode = import.meta.env.VITE_USE_MOCK_API !== "false";

  function handleInputChange(value: string) {
    setInput(value);
    setProcessingId(null);
    setResolvedEvent(null);
    setError(null);
    setUploadNotice(null);
    setLastUpdatedAt(null);
  }

  function applyExample(value: string) {
    handleInputChange(value);
  }

  function handleFileChange(file: File | null) {
    setSelectedFile(file);
    setProcessingId(null);
    setResolvedEvent(null);
    setError(null);
    setUploadNotice(null);
    setLastUpdatedAt(null);
  }

  async function handleSubmit() {
    try {
      setIsLoading(true);
      setError(null);
      setUploadNotice(null);
      setResolvedEvent(null);
      const response = await parseTransaction({
        input_text: input,
        source: "manual_text",
        currency: "CAD",
      });
      setProcessingId(response.parse_id);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Unable to parse transaction.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleFileUpload() {
    if (!selectedFile) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setResolvedEvent(null);
      const response = await uploadTransactionFile(selectedFile);
      setProcessingId(response.parse_id);
      setUploadNotice(`Submitted ${selectedFile.name} for processing.`);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Unable to process uploaded file.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!processingId) return;
    const unsub = subscribeToRealtimeUpdates((event) => {
      if (
        event.type === "entry.posted" ||
        event.type === "clarification.created" ||
        event.type === "clarification.resolved"
      ) {
        setResolvedEvent(event);
        setProcessingId(null);
        setLastUpdatedAt(new Date());
      }
    });
    return unsub;
  }, [processingId]);

  const isPosted =
    resolvedEvent?.type === "entry.posted" || resolvedEvent?.type === "clarification.resolved";

  function dismissModal() {
    setResolvedEvent(null);
  }

  return (
    <div className="page-grid">
      <section className="panel hero-panel workflow-hero">
        <div className="hero-copy">
          <div>
            <p className="eyebrow">Workflow</p>
            <h2>Translate plain language into ledger-ready journal entries.</h2>
          </div>
          <p className="body-copy">
            Start with a clean purchase or try an ambiguous transfer to exercise the clarification queue.
          </p>
        </div>
        <div className="hero-meta">
          {isMockMode ? (
            <span className="hero-pill">Mock API Active</span>
          ) : (
            <span className="hero-pill">Live API Mode</span>
          )}
          <span className="hero-pill hero-pill-muted">
            Demo user: {import.meta.env.VITE_DEMO_USER_ID}
          </span>
          <FreshnessStatus
            label="Pipeline Updated"
            lastUpdatedAt={lastUpdatedAt}
            variant="hero"
          />
        </div>
      </section>

      <section className="panel compact-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Examples</p>
            <h2>Quick Prompts</h2>
          </div>
        </div>
        <div className="chip-row">
          {sampleTransactions.map((sample) => (
            <button key={sample} className="prompt-chip" onClick={() => applyExample(sample)}>
              {sample}
            </button>
          ))}
        </div>
      </section>

      <TransactionForm
        value={input}
        onChange={handleInputChange}
        selectedFileName={selectedFile?.name ?? null}
        onFileChange={handleFileChange}
        onSubmit={handleSubmit}
        onUploadFile={handleFileUpload}
        isLoading={isLoading}
      />

      {error ? <section className="panel error-panel">{error}</section> : null}
      {uploadNotice ? (
        <section className="panel outcome-panel outcome-success compact-panel">
          <p className="success-copy upload-notice">{uploadNotice}</p>
        </section>
      ) : null}

      {processingId ? (
        <section className="panel outcome-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Status</p>
              <h2>Processing...</h2>
            </div>
          </div>
          <p className="body-copy">
            Transaction accepted (ID: {processingId}). Waiting for the pipeline to complete.
          </p>
        </section>
      ) : null}

      {!processingId && !resolvedEvent && !error ? (
        <section className="panel empty-state-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Ready</p>
              <h2>What to Try First</h2>
            </div>
          </div>
          <div className="empty-state-grid">
            <div className="empty-state-card">
              <strong>Clear purchase</strong>
              <p className="body-copy">
                Use a concrete transaction like a laptop or software subscription to exercise the auto-post path.
              </p>
            </div>
            <div className="empty-state-card">
              <strong>Ambiguous transfer</strong>
              <p className="body-copy">
                Use wording like "Transferred money" to send the item into the clarification queue.
              </p>
            </div>
          </div>
        </section>
      ) : null}

      {resolvedEvent ? (
        <div className="modal-backdrop" onClick={dismissModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <p className="eyebrow">
                {isPosted ? "Entry Posted" : "Human Review Needed"}
              </p>
              <h2>
                {isPosted ? "Entry Posted" : "Clarification Required"}
              </h2>
            </div>

            <div className="event-details">
              {resolvedEvent.journal_entry_id && (
                <div className="detail-row">
                  <span className="detail-label">Journal Entry ID</span>
                  <span className="detail-value">{resolvedEvent.journal_entry_id}</span>
                </div>
              )}
              {resolvedEvent.parse_id && (
                <div className="detail-row">
                  <span className="detail-label">Parse ID</span>
                  <span className="detail-value">{resolvedEvent.parse_id}</span>
                </div>
              )}
              {resolvedEvent.input_text && (
                <div className="detail-row">
                  <span className="detail-label">Input</span>
                  <span className="detail-value">{resolvedEvent.input_text}</span>
                </div>
              )}
              {resolvedEvent.status && (
                <div className="detail-row">
                  <span className="detail-label">Status</span>
                  <span className="detail-value">{resolvedEvent.status}</span>
                </div>
              )}
              {resolvedEvent.confidence && (
                <div className="detail-row">
                  <span className="detail-label">Confidence</span>
                  <span className="detail-value">{resolvedEvent.confidence.overall}</span>
                </div>
              )}
              {resolvedEvent.explanation && (
                <div className="detail-row">
                  <span className="detail-label">Explanation</span>
                  <span className="detail-value">{resolvedEvent.explanation}</span>
                </div>
              )}
              {resolvedEvent.parse_time_ms != null && (
                <div className="detail-row">
                  <span className="detail-label">Parse Time</span>
                  <span className="detail-value">{resolvedEvent.parse_time_ms} ms</span>
                </div>
              )}
              {resolvedEvent.occurred_at && (
                <div className="detail-row">
                  <span className="detail-label">Timestamp</span>
                  <span className="detail-value">{resolvedEvent.occurred_at}</span>
                </div>
              )}
            </div>

            {resolvedEvent.proposed_entry && resolvedEvent.proposed_entry.lines.length > 0 && (
              <table className="proposed-entry-table">
                <thead>
                  <tr>
                    <th>Account</th>
                    <th>Type</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {resolvedEvent.proposed_entry.lines.map((line, i) => (
                    <tr key={i}>
                      <td>{line.account_name}</td>
                      <td>{line.type}</td>
                      <td>${line.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div className="modal-actions">
              <button
                className="primary-button"
                onClick={() => {
                  dismissModal();
                  navigate(isPosted ? "/ledger" : "/clarifications");
                }}
              >
                {isPosted ? "View Ledger" : "Open Clarifications"}
              </button>
              <button className="secondary-button" onClick={dismissModal}>
                Dismiss
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
