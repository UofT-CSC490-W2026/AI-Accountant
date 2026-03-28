# tests/services/precedent/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/precedent/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_dummy_match | services/precedent/process.py · process | process enriches message with dummy precedent_match false | test_process.py | passed | |
| 3 | process_forwards | services/precedent/process.py · process | process forwards enriched message to ml_inference queue | test_process.py | passed | |
