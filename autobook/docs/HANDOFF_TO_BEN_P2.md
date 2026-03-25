# P2 Backend Handoff

## Status

As of March 24, 2026, the non-`P2-7` backend pipeline work is implemented and validated locally.

The current pipeline now follows this structure:

`User Input -> Normalizer -> Precedent -> ML -> Reasoning fallback if needed -> Rule Engine -> Posting or Clarification -> Rule Engine-backed final journal entry`

`P2-7` remains out of scope here and should still be handled on Ben's side.

## What Changed

### 1. Canonical transaction and normalization contract

Normalization was aligned to the required transaction shape and source values.

Files:
- `backend/services/normalizer/service.py`
- `tests/test_transaction_lifecycle.py`

Key effects:
- canonical sources like `manual_text`, `csv_upload`, `pdf_upload`, `upload`, `bank_feed`
- normalized description support
- extraction of amount/date/party/quantity mentions
- persisted transaction fields aligned with the expected `Transaction` shape

### 2. ML output contract alignment

ML enrichment now emits the required downstream structure.

Files:
- `backend/services/ml_inference/service.py`
- `tests/test_ml_service.py`

Key effects:
- emits `normalized_text`
- emits canonical `input_type`
- preserves and merges `entities`
- emits `intent_label`, `bank_category`, `cca_class_match`, and `confidence.ml`

Note:
- this is still prototype inference logic, not a real DeBERTa deployment

### 3. Precedent stage is real now

The precedent stage no longer just stamps a placeholder.

Files:
- `backend/services/precedent/process.py`
- `backend/services/precedent/service.py`
- `tests/test_precedent_pipeline.py`

Key effects:
- loads prior posted journal history for the same user
- scores precedent candidates conservatively
- writes `precedent_match`
- routes strong repeats directly toward posting with a precedent-backed proposed entry

### 4. Rule engine now owns journal entry generation

Classification and account mapping were separated so the rule engine always produces the final journal entry proposal.

Files:
- `backend/accounting_engine/rules.py`
- `backend/accounting_engine/__init__.py`
- `backend/services/agent/process.py`
- `tests/test_agent_pipeline.py`

Key effects:
- high-confidence ML routes directly to rule-based posting
- lower confidence routes through structured reasoning fallback
- unresolved ambiguity routes to clarification
- final entry generation stays rule-engine-owned

Handled mappings include:
- asset purchase
- software subscription
- rent expense
- meals and entertainment
- professional fees
- bank fees
- fallback transfer with `9999 / Unknown Destination`

### 5. Posting support updates

Files:
- `backend/db/dao/chart_of_accounts.py`
- `backend/db/dao/journal_entries.py`

Key effects:
- adds `9999 / Unknown Destination`
- ensures default chart accounts are seeded before posting

## Validation

### Automated tests

Current backend result:

- `36 passed`

Coverage includes:
- transaction lifecycle
- ML contract behavior
- agent pipeline behavior
- precedent pipeline behavior
- end-to-end smoke harness

### Smoke validation

File:
- `tests/test_smoke_end_to_end.py`

What the smoke flow validates:
- demo auth
- manual parse flow
- posting to ledger
- repeat transaction precedent behavior
- low-confidence transfer to clarification
- manager clarification approval
- statements rendering after posting

Important limitation:
- Docker-backed infra smoke could not be run because the local Docker daemon was unavailable on March 24, 2026
- the smoke pass that is green is a process-level local harness using the real FastAPI routes and worker flow with in-memory queue and persistence fakes

## Current Situation

From a backend-contract and pipeline perspective, the P2 work is in a good submission state except for `P2-7`.

What is complete:
- canonical payload flow across stages
- precedent integration
- ML output structure
- reasoning fallback routing
- rule-engine-backed journal generation
- clarification path
- posting path
- ledger and statements smoke validation

What is still not "production" quality:
- ML is still deterministic prototype logic, not a real trained DeBERTa service
- reasoning fallback is still structured prototype logic, not a real LLM integration
- flywheel remains unimplemented
- containerized infra validation still needs Docker available

## Ben-Facing Next Steps

1. Finish and merge `P2-7`.
2. Re-run one full integrated UI + backend smoke pass after merge.
3. If Docker is available later, run the container-backed validation once to confirm no environment drift.

## Files Most Relevant For Review

- `backend/services/normalizer/service.py`
- `backend/services/ml_inference/service.py`
- `backend/services/precedent/process.py`
- `backend/services/precedent/service.py`
- `backend/services/agent/process.py`
- `backend/accounting_engine/rules.py`
- `backend/db/dao/chart_of_accounts.py`
- `backend/db/dao/journal_entries.py`
- `tests/test_agent_pipeline.py`
- `tests/test_precedent_pipeline.py`
- `tests/test_smoke_end_to_end.py`
