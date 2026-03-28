from typing import TypedDict

# ── Agent name constants (single source of truth) ─────────────────────────
DISAMBIGUATOR = "disambiguator"
DEBIT_CLASSIFIER = "debit_classifier"
CREDIT_CLASSIFIER = "credit_classifier"
DEBIT_CORRECTOR = "debit_corrector"
CREDIT_CORRECTOR = "credit_corrector"
ENTRY_BUILDER = "entry_builder"
APPROVER = "approver"
DIAGNOSTICIAN = "diagnostician"

AGENT_NAMES = [
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    APPROVER, DIAGNOSTICIAN,
]

# ── Agent status constants ────────────────────────────────────────────────
NOT_RUN = 0
COMPLETE = 1
RERUN = 2


class PipelineState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    transaction_text: str
    user_context: dict          # business_type, province, ownership
    ml_enrichment: dict | None  # intent_label, entities (optional, ablation)

    # ── Fix loop ───────────────────────────────────────────────────────────
    # iteration is the index into output_* and fix_context_* lists.
    # Incremented by the scheduler ONLY (never by individual nodes).
    # Nodes read state["iteration"] to know which index to write to.
    # LangGraph dependency order guarantees upstream output_*[i] exists
    # before downstream reads it in the same iteration.
    iteration: int

    # ── Agent outputs — typed, indexed by iteration (output_*[i] = iteration i)
    output_disambiguator: list        # [str]            enriched text
    output_debit_classifier: list     # [tuple[int,...]]  debit 6-tuple
    output_credit_classifier: list    # [tuple[int,...]]  credit 6-tuple
    output_debit_corrector: list      # [tuple[int,...]]  refined debit 6-tuple
    output_credit_corrector: list     # [tuple[int,...]]  refined credit 6-tuple
    output_entry_builder: list        # [dict]            journal entry
    output_approver: list             # [dict]            {approved, confidence, reason}
    output_diagnostician: list        # [dict]            {decision, fix_plans}

    # ── Agent status — dirty propagation for fix loop (0=NOT_RUN, 1=COMPLETE, 2=RERUN)
    status_disambiguator: int
    status_debit_classifier: int
    status_credit_classifier: int
    status_debit_corrector: int
    status_credit_corrector: int
    status_entry_builder: int
    status_approver: int
    status_diagnostician: int

    # ── Fix context per agent — diagnostician guidance history, indexed by fix iteration
    fix_context_disambiguator: list       # [str]
    fix_context_debit_classifier: list    # [str]
    fix_context_credit_classifier: list   # [str]
    fix_context_debit_corrector: list     # [str]
    fix_context_credit_corrector: list    # [str]
    fix_context_entry_builder: list       # [str]
    fix_context_approver: list            # [str]
    fix_context_diagnostician: list       # [str]

    # ── RAG cache — one field per agent (separate keys = no parallel write conflict)
    rag_cache_disambiguator: list
    rag_cache_debit_classifier: list
    rag_cache_credit_classifier: list
    rag_cache_debit_corrector: list
    rag_cache_credit_corrector: list
    rag_cache_entry_builder: list
    rag_cache_approver: list
    rag_cache_diagnostician: list

    # ── Validation error — set by validation node, checked by graph routing
    validation_error: list | None  # None = valid, list of error strings = invalid

    # ── Pipeline decision — terminal output of the agent system
    # Set by disambiguator (INCOMPLETE_INFORMATION), drafter (any), approver (CONFIDENT/STUCK),
    # or diagnostician (STUCK). Whichever agent owns the decision in the active variant.
    decision: str | None                      # "APPROVED" | "INCOMPLETE_INFORMATION" | "STUCK" | None
    clarification_questions: list | None      # set when decision = INCOMPLETE_INFORMATION
    stuck_reason: str | None                  # set when decision = STUCK

    # ── Embedding cache — computed once, reused by all agents
    embedding_transaction: list[float] | None   # embed(transaction_text), used by agents 0-6
    embedding_error: list[float] | None         # embed(fix_plans[].error), fix loop only
    embedding_rejection: list[float] | None     # embed(approval.reason), rejection only
