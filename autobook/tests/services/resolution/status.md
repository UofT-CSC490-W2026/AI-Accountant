# tests/services/resolution/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/resolution/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_creates_task | services/resolution/process.py · process | process creates clarification task for unresolved entry | test_process.py | passed | |
| 3 | process_routes_resolved | services/resolution/process.py · process | process routes resolved clarification to posting queue | test_process.py | passed | |
| 4 | process_event_created | services/resolution/process.py · process | process publishes clarification.created event for new task | test_process.py | passed | |
| 5 | process_event_resolved | services/resolution/process.py · process | process publishes clarification.resolved event when already resolved | test_process.py | passed | |
| 6 | process_skips_rejected | services/resolution/process.py · process | process skips posting for rejected clarification | test_process.py | passed | |
