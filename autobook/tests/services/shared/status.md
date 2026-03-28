# tests/services/shared/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | coerce_date_string | services/shared/transaction_persistence.py · coerce_transaction_date | coerce_transaction_date converts date string to date object | test_transaction_persistence.py | passed | |
| 2 | coerce_date_already_date | services/shared/transaction_persistence.py · coerce_transaction_date | coerce_transaction_date handles already-date input without conversion | test_transaction_persistence.py | passed | |
| 3 | ensure_transaction_new | services/shared/transaction_persistence.py · ensure_transaction_for_message | ensure_transaction_for_message creates new transaction when none exists | test_transaction_persistence.py | passed | |
| 4 | ensure_transaction_missing_intent | services/shared/transaction_persistence.py · ensure_transaction_for_message | ensure_transaction_for_message handles message missing intent fields gracefully | test_transaction_persistence.py | passed | |
| 5 | ensure_transaction_updates_existing | services/shared/transaction_persistence.py · ensure_transaction_for_message | ensure_transaction_for_message updates existing transaction when transaction_id is present | test_transaction_persistence.py | passed | |
