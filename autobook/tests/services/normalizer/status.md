# tests/services/normalizer/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/normalizer/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_no_parties | services/normalizer/process.py · process | process handles message with no party mentions | test_process.py | passed | |
| 3 | process_ambiguous_amounts | services/normalizer/process.py · process | process handles message with multiple ambiguous amounts | test_process.py | passed | |
| 4 | normalize_confident_amount | services/normalizer/service.py · normalize | normalize extracts single unambiguous amount as confident | test_service.py | passed | |
| 5 | normalize_party_name | services/normalizer/service.py · normalize | normalize extracts party name from text | test_service.py | passed | |
| 6 | normalize_missing_date | services/normalizer/service.py · normalize | normalize handles missing date gracefully | test_service.py | passed | |
| 7 | process_persists_before_enqueue | services/normalizer/process.py · process | process persists canonical transaction before enqueuing to next queue | test_process.py | passed | |
| 8 | normalize_ambiguous_not_confident | services/normalizer/service.py · normalize | normalize marks amount as not confident when multiple amounts present | test_service.py | passed | |
