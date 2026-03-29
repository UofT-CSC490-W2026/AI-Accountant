import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getParseStatus, parseTransaction, uploadTransactionFile } from "../api/parse";
import { subscribeToRealtimeUpdates, waitForRealtimeConnection } from "../api/realtime";
import type { ParseStatus, RealtimeEvent } from "../api/types";
import { FreshnessStatus } from "../components/FreshnessStatus";
import { PipelineFlow } from "../components/PipelineFlow";
import { TransactionForm } from "../components/TransactionForm";

const sampleTransactions = [
  "Bought a laptop for $2400",
  "Transferred money",
  "Paid contractor 600 for website work",
];
const PENDING_PARSE_ID_KEY = "autobook_pending_parse_id";
const FINAL_PARSE_STATUSES = new Set(["auto_posted", "needs_clarification", "resolved", "rejected"]);

type Branch = "precedent" | "ml" | "llm";

const BRANCHES: { key: Branch; label: string }[] = [
  { key: "precedent", label: "Precedent" },
  { key: "ml", label: "ML" },
  { key: "llm", label: "LLM" },
];

export function TransactionPage() {
  const navigate = useNavigate();
  const [input, setInput] = useState("Bought a laptop for $2400");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const processingIdRef = useRef<string | null>(null);
  const eventBufferRef = useRef<RealtimeEvent[]>([]);
  const [resolvedEvent, setResolvedEvent] = useState<RealtimeEvent | null>(null);
  const [pipelineResult, setPipelineResult] = useState<Record<string, unknown> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [statementCount, setStatementCount] = useState<number>(1);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const isMockMode = import.meta.env.VITE_USE_MOCK_API !== "false";

  const [store, setStore] = useState(true);
  const [stages, setStages] = useState<Record<Branch, boolean>>({ precedent: true, ml: true, llm: true });
  const [post, setPost] = useState<Record<Branch, boolean>>({ precedent: true, ml: true, llm: true });
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const activeStageRef = useRef<string | null>(null);
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [skippedStages, setSkippedStages] = useState<Set<string>>(new Set());
  const [pipelineLocked, setPipelineLocked] = useState(false);

  function advanceStage(next: string | null) {
    const prev = activeStageRef.current;
    if (prev) {
      setCompletedStages((s) => new Set(s).add(prev));
    }
    activeStageRef.current = next;
    setActiveStage(next);
  }

  function clearProgress() {
    activeStageRef.current = null;
    setActiveStage(null);
    setCompletedStages(new Set());
    setSkippedStages(new Set());
  }

  function isPostDisabled(branch: Branch): boolean {
    return !stages[branch] || !store;
  }

  function toggleStore() {
    clearProgress();
    setStore((prev) => {
      if (prev) setPost({ precedent: false, ml: false, llm: false });
      return !prev;
    });
  }

  function toggleStage(branch: Branch) {
    clearProgress();
    setStages((prev) => {
      if (prev[branch]) setPost((p) => ({ ...p, [branch]: false }));
      return { ...prev, [branch]: !prev[branch] };
    });
  }

  function togglePost(branch: Branch) {
    if (isPostDisabled(branch)) return;
    clearProgress();
    setPost((prev) => ({ ...prev, [branch]: !prev[branch] }));
  }

  // Derive backend API fields
  const activeStages = (Object.entries(stages) as [Branch, boolean][])
    .filter(([, v]) => v)
    .map(([k]) => k);
  const activePostStages = (Object.entries(post) as [Branch, boolean][])
    .filter(([, v]) => v)
    .map(([k]) => k);

  useEffect(() => {
    const pendingParseId = sessionStorage.getItem(PENDING_PARSE_ID_KEY);
    if (pendingParseId) {
      setProcessingId(pendingParseId);
    }
  }, []);

  useEffect(() => {
    if (processingId) {
      sessionStorage.setItem(PENDING_PARSE_ID_KEY, processingId);
      return;
    }

    sessionStorage.removeItem(PENDING_PARSE_ID_KEY);
  }, [processingId]);

  function handleInputChange(value: string) {
    setInput(value);
    setStatementCount(1);
    setProcessingId(null);
    setResolvedEvent(null);
    setError(null);
    setUploadNotice(null);
    setLastUpdatedAt(null);
    setPipelineResult(null);
  }

  function applyExample(value: string) {
    handleInputChange(value);
  }

  function handleFileChange(file: File | null) {
    setSelectedFile(file);
    setStatementCount(1);
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
      clearProgress();
      setPipelineLocked(true);
      eventBufferRef.current = [];
      await waitForRealtimeConnection();
      const response = await parseTransaction({
        input_text: input,
        source: "manual_text",
        currency: "CAD",
        stages: activeStages,
        store: store,
        post_stages: activePostStages,
      });
      setStatementCount(response.statement_count ?? 1);
      processingIdRef.current = response.parse_id;
      setProcessingId(response.parse_id);
    } catch (submitError) {
      setPipelineLocked(false);
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
      clearProgress();
      setPipelineLocked(true);
      await waitForRealtimeConnection();
      const response = await uploadTransactionFile(selectedFile, {
        stages: activeStages,
        store: store,
        post_stages: activePostStages,
      });
      setStatementCount(response.statement_count ?? 1);
      setProcessingId(response.parse_id);
      const count = response.statement_count ?? 1;
      setUploadNotice(
        count > 1
          ? `Submitted ${selectedFile.name} with ${count} statements for processing.`
          : `Submitted ${selectedFile.name} for processing.`,
      );
    } catch (submitError) {
      setPipelineLocked(false);
      setError(
        submitError instanceof Error ? submitError.message : "Unable to process uploaded file.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  // Keep ref in sync with state, replay buffered events when ref is set
  useEffect(() => {
    processingIdRef.current = processingId;
    if (processingId && eventBufferRef.current.length > 0) {
      const matching = eventBufferRef.current.filter((e) => e.parse_id === processingId);
      eventBufferRef.current = [];
      for (const e of matching) {
        handleSSEEvent(e);
      }
    }
  }, [processingId]);

  function handleSSEEvent(event: RealtimeEvent) {
    if (event.type === "pipeline.stage_started") {
      advanceStage(event.stage ?? null);
      return;
    }
    if (event.type === "pipeline.stage_skipped") {
      if (event.stage) {
        setSkippedStages((s) => new Set(s).add(event.stage!));
      }
      return;
    }
    if (event.type === "pipeline.result") {
      advanceStage(null);
      setPipelineLocked(false);
      setPipelineResult(event.result ?? {});
      setProcessingId(null);
      setLastUpdatedAt(new Date());
      return;
    }
    if (event.type === "pipeline.error") {
      advanceStage(null);
      setPipelineLocked(false);
      setError(`[${event.stage}] ${event.error}`);
      setProcessingId(null);
      return;
    }
    if (
      event.type === "entry.posted" ||
      event.type === "clarification.created" ||
      event.type === "clarification.resolved"
    ) {
      advanceStage(null);
      setPipelineLocked(false);
      setResolvedEvent(event);
      setProcessingId(null);
      setLastUpdatedAt(new Date());
    }
  }

  // Subscribe once on mount — buffer events if ref not set yet
  useEffect(() => {
    const unsub = subscribeToRealtimeUpdates((event) => {
      if (!processingIdRef.current) {
        // Ref not set yet — buffer the event for replay
        eventBufferRef.current.push(event);
        return;
      }
      if (event.parse_id !== processingIdRef.current) {
        return;
      }
      handleSSEEvent(event);
    });
    return unsub;
  }, []);

  useEffect(() => {
    if (!processingId || isMockMode) {
      return;
    }

    let isActive = true;

    const poll = async () => {
      try {
        const nextStatus = await getParseStatus(processingId);
        if (!isActive) {
          return;
        }

        if (nextStatus.status === "failed") {
          setError(nextStatus.error ?? "Transaction processing failed.");
          setProcessingId(null);
          return;
        }

        if (FINAL_PARSE_STATUSES.has(nextStatus.status)) {
          setResolvedEvent(buildResolvedEvent(nextStatus));
          setProcessingId(null);
          setLastUpdatedAt(new Date());
        }
      } catch {
        // Keep waiting. The status endpoint is a fallback for missed realtime events.
      }
    };

    void poll();
    const intervalId = window.setInterval(() => {
      void poll();
    }, 3000);

    return () => {
      isActive = false;
      window.clearInterval(intervalId);
    };
  }, [isMockMode, processingId]);

  const isPosted =
    resolvedEvent?.type === "entry.posted" || resolvedEvent?.type === "clarification.resolved";
  const batch = resolvedEvent?.batch;
  const isBatchResult = (batch?.total_statements ?? statementCount) > 1;
  const modalHeading = isBatchResult
    ? isPosted
      ? "Batch Posted"
      : "Batch Review Needed"
    : isPosted
      ? "Entry Posted"
      : "Clarification Required";
  const modalEyebrow = isBatchResult
    ? isPosted
      ? "Batch Complete"
      : "Batch Requires Review"
    : isPosted
      ? "Entry Posted"
      : "Human Review Needed";

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
      />

      <section className="panel compact-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Pipeline</p>
            <h2>Run Configuration</h2>
          </div>
        </div>
        <PipelineFlow
          state={{ store, stages, post }}
          activeStage={activeStage}
          completedStages={completedStages}
          skippedStages={skippedStages}
          locked={pipelineLocked}
          onToggleStore={toggleStore}
          onToggleStage={toggleStage}
          onTogglePost={togglePost}
        />
        <div className="panel-actions">
          <button className="primary-button" onClick={handleSubmit} disabled={isLoading || !input.trim()}>
            {isLoading ? "Parsing..." : "Parse Transaction"}
          </button>
          <button
            className="secondary-button"
            onClick={handleFileUpload}
            disabled={isLoading || !selectedFile}
          >
            {isLoading ? "Processing..." : "Upload File"}
          </button>
        </div>
      </section>

      {error ? <section className="panel error-panel">{error}</section> : null}
      {uploadNotice ? (
        <section className="panel outcome-panel outcome-success compact-panel">
          <p className="success-copy upload-notice">{uploadNotice}</p>
        </section>
      ) : null}

      {pipelineResult ? (
        <section className="panel outcome-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Pipeline Result</p>
              <h2>Stage: {activeStages.join(", ") || "normalizer"}</h2>
            </div>
          </div>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem", maxHeight: "400px", overflow: "auto" }}>
            {JSON.stringify(pipelineResult, null, 2)}
          </pre>
          <button className="secondary-button" onClick={() => setPipelineResult(null)} style={{ marginTop: "1rem" }}>
            Dismiss
          </button>
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
                {modalEyebrow}
              </p>
              <h2>
                {modalHeading}
              </h2>
            </div>

            <div className="event-details">
              {batch ? (
                <>
                  <div className="detail-row">
                    <span className="detail-label">Statements</span>
                    <span className="detail-value">
                      {batch.completed_statements}/{batch.total_statements}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Auto Posted</span>
                    <span className="detail-value">{batch.auto_posted_count}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Needs Clarification</span>
                    <span className="detail-value">{batch.needs_clarification_count}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Failed</span>
                    <span className="detail-value">{batch.failed_count}</span>
                  </div>
                </>
              ) : null}
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

function buildResolvedEvent(status: ParseStatus): RealtimeEvent {
  return {
    type:
      status.status === "auto_posted"
        ? "entry.posted"
        : status.status === "needs_clarification"
          ? "clarification.created"
          : "clarification.resolved",
    journal_entry_id: status.journal_entry_id ?? status.proposed_entry?.journal_entry_id ?? undefined,
    parse_id: status.parse_id,
    input_text: status.input_text ?? undefined,
    occurred_at: status.updated_at,
    confidence: status.confidence ?? undefined,
    explanation: status.explanation ?? undefined,
    status: status.status,
    proposed_entry: status.proposed_entry ?? undefined,
    batch: status.batch ?? undefined,
  };
}
