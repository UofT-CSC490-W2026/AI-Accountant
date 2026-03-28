# tests/services/posting/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | handler_delegates | services/posting/handler.py · handler | handler parses SQS event records and delegates to process | test_handler.py | passed | |
| 2 | process_inserts_entry | services/posting/process.py · process | process inserts journal entry and lines into DB | test_process.py | passed | |
| 3 | process_publishes_event | services/posting/process.py · process | process publishes entry.posted event after posting | test_process.py | passed | |
| 4 | process_forwards_flywheel | services/posting/process.py · process | process forwards message to flywheel queue after posting | test_process.py | passed | |
| 5 | process_normalizes_entry | services/posting/process.py · process | process normalizes proposed_entry structure before inserting | test_process.py | passed | |
