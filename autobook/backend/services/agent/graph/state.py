from typing import TypedDict


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



