# tests/services/agent/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | execute_equipment | services/agent/execute.py · execute | equipment purchase produces Equipment debit and Cash credit lines | test_execute.py | passed | |
| 2 | execute_software | services/agent/execute.py · execute | software subscription produces Software Subscriptions debit and Cash credit lines | test_execute.py | passed | |
| 3 | execute_rent | services/agent/execute.py · execute | rent payment produces Rent Expense debit and Cash credit lines | test_execute.py | passed | |
| 4 | execute_meals | services/agent/execute.py · execute | meals expense produces Meals debit and Cash credit lines | test_execute.py | passed | |
| 5 | execute_professional | services/agent/execute.py · execute | professional services produces Professional Fees debit and Cash credit lines | test_execute.py | passed | |
| 6 | execute_bank_fee | services/agent/execute.py · _stub_classify | bank_fee intent falls to low-confidence default (stub does not handle) | test_execute.py | passed | |
| 7 | process_high_confidence | services/agent/execute.py · process | high confidence transaction routes to posting queue | test_execute.py | passed | |
| 8 | process_low_confidence | services/agent/execute.py · process | low confidence transaction routes to resolution queue | test_execute.py | passed | |
| 9 | process_threshold_boundary | services/agent/execute.py · process | transaction at exactly the threshold routes to posting queue | test_execute.py | passed | |
| 10 | process_publishes_event | services/agent/execute.py · process | process publishes clarification.created event for low confidence | test_execute.py | passed | |
| 11 | execute_unknown_intent | services/agent/execute.py · execute | unknown intent falls back to generic expense journal entry | test_execute.py | passed | |
