# tests/services/flywheel/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/flywheel/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_runs | services/flywheel/process.py · process | process runs to completion without error | test_process.py | passed | |
