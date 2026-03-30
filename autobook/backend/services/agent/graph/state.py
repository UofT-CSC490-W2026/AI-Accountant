from typing import TypedDict

# ── Agent name constants (single source of truth) ─────────────────────────

# Legacy agents
DISAMBIGUATOR = "disambiguator"
DEBIT_CLASSIFIER = "debit_classifier"
CREDIT_CLASSIFIER = "credit_classifier"
DEBIT_CORRECTOR = "debit_corrector"
CREDIT_CORRECTOR = "credit_corrector"
ENTRY_BUILDER = "entry_builder"
APPROVER = "approver"
DIAGNOSTICIAN = "diagnostician"

# V3 agents
AMBIGUITY_DETECTOR = "ambiguity_detector"
COMPLEXITY_DETECTOR = "complexity_detector"
TAX_SPECIALIST = "tax_specialist"
DECISION_MAKER = "decision_maker"
ENTRY_DRAFTER = "entry_drafter"

AGENT_NAMES = [
    AMBIGUITY_DETECTOR, COMPLEXITY_DETECTOR,
    DEBIT_CLASSIFIER, CREDIT_CLASSIFIER, TAX_SPECIALIST,
    DECISION_MAKER, ENTRY_DRAFTER,
    APPROVER, DIAGNOSTICIAN,
    # Legacy
    DISAMBIGUATOR, DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
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
    iteration: int

    # ── V3 agent outputs ──────────────────────────────────────────────────
    output_ambiguity_detector: list       # [dict] ambiguities
    output_complexity_detector: list      # [dict] complexity flags
    output_tax_specialist: list           # [dict] tax treatment
    output_decision_maker: list           # [dict] decision + overrides
    output_entry_drafter: list            # [dict] journal entry

    # ── Legacy agent outputs (kept for corrector/approver variants) ────────
    output_disambiguator: list            # [dict] ambiguities (legacy alias)
    output_debit_classifier: list         # [dict] debit structure
    output_credit_classifier: list        # [dict] credit structure
    output_debit_corrector: list          # [dict] refined debit structure
    output_credit_corrector: list         # [dict] refined credit structure
    output_entry_builder: list            # [dict] journal entry (legacy alias)
    output_approver: list                 # [dict] {decision, confidence, reason}
    output_diagnostician: list            # [dict] {decision, fix_plans}

    # ── Agent status ──────────────────────────────────────────────────────
    status_ambiguity_detector: int
    status_complexity_detector: int
    status_tax_specialist: int
    status_decision_maker: int
    status_entry_drafter: int
    status_disambiguator: int
    status_debit_classifier: int
    status_credit_classifier: int
    status_debit_corrector: int
    status_credit_corrector: int
    status_entry_builder: int
    status_approver: int
    status_diagnostician: int

    # ── Fix context per agent ─────────────────────────────────────────────
    fix_context_disambiguator: list
    fix_context_debit_classifier: list
    fix_context_credit_classifier: list
    fix_context_debit_corrector: list
    fix_context_credit_corrector: list
    fix_context_entry_builder: list
    fix_context_approver: list
    fix_context_diagnostician: list

    # ── RAG cache ─────────────────────────────────────────────────────────
    rag_cache_disambiguator: list
    rag_cache_debit_classifier: list
    rag_cache_credit_classifier: list
    rag_cache_debit_corrector: list
    rag_cache_credit_corrector: list
    rag_cache_entry_builder: list
    rag_cache_approver: list
    rag_cache_diagnostician: list

    # ── Validation error ──────────────────────────────────────────────────
    validation_error: list | None

    # ── Pipeline decision ─────────────────────────────────────────────────
    decision: str | None                      # "APPROVED" | "INCOMPLETE_INFORMATION" | "STUCK" | None
    clarification_questions: list | None
    stuck_reason: str | None

    # ── Embedding cache ───────────────────────────────────────────────────
    embedding_transaction: list[float] | None
    embedding_error: list[float] | None
    embedding_rejection: list[float] | None
