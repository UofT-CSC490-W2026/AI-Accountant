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

    # ── Disambiguator (Agent 0) ────────────────────────────────────────────
    enriched_text: str | None

    # ── Tuple classification ───────────────────────────────────────────────
    initial_debit_tuple: tuple[int, ...]
    initial_credit_tuple: tuple[int, ...]
    refined_debit_tuple: tuple[int, ...]
    refined_credit_tuple: tuple[int, ...]

    # ── Journal entry (Agent 5) ────────────────────────────────────────────
    journal_entry: dict | None  # {date, description, rationale, lines}

    # ── Evaluator ──────────────────────────────────────────────────────────
    approval: dict | None       # {approved, confidence, reason}
    diagnosis: dict | None      # {decision, fix_plans}

    # ── Fix loop ───────────────────────────────────────────────────────────
    iteration: int

    # ── RAG cache — one field per agent (separate keys = no parallel write conflict)
    rag_cache_disambiguator: list
    rag_cache_debit_classifier: list
    rag_cache_credit_classifier: list
    rag_cache_debit_corrector: list
    rag_cache_credit_corrector: list
    rag_cache_entry_builder: list
    rag_cache_approver: list
    rag_cache_diagnostician: list

    # ── Agent outputs — one field per agent (separate keys = no parallel write conflict)
    output_disambiguator: str | None
    output_debit_classifier: str | None
    output_credit_classifier: str | None
    output_debit_corrector: str | None
    output_credit_corrector: str | None
    output_entry_builder: str | None
    output_approver: str | None
    output_diagnostician: str | None

    # ── Agent status — dirty propagation for fix loop (0=NOT_RUN, 1=COMPLETE, 2=RERUN)
    status_disambiguator: int
    status_debit_classifier: int
    status_credit_classifier: int
    status_debit_corrector: int
    status_credit_corrector: int
    status_entry_builder: int
    status_approver: int
    status_diagnostician: int

    # ── Embedding cache — computed once, reused by all agents
    embedding_transaction: list[float] | None   # embed(transaction_text), used by agents 0-6
    embedding_error: list[float] | None         # embed(fix_plans[].error), fix loop only
    embedding_rejection: list[float] | None     # embed(approval.reason), rejection only



