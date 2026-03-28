# tests/reporting/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | balance_sheet_sections | reporting/statements.py · build_balance_sheet | build_balance_sheet groups assets, liabilities, and equity into correct sections | test_statements.py | passed | |
| 2 | balance_sheet_net_income | reporting/statements.py · build_balance_sheet | build_balance_sheet computes net income from revenue minus expenses | test_statements.py | passed | |
| 3 | balance_sheet_totals | reporting/statements.py · build_balance_sheet | build_balance_sheet returns correct grand totals | test_statements.py | passed | |
| 4 | balance_sheet_empty | reporting/statements.py · build_balance_sheet | build_balance_sheet returns empty sections when no accounts exist | test_statements.py | passed | |
| 5 | income_statement_sections | reporting/statements.py · build_income_statement | build_income_statement separates revenue from expense accounts correctly | test_statements.py | passed | |
| 6 | income_statement_net_income | reporting/statements.py · build_income_statement | build_income_statement computes net income correctly | test_statements.py | passed | |
| 7 | income_statement_empty | reporting/statements.py · build_income_statement | build_income_statement handles period with no transactions | test_statements.py | passed | |
| 8 | trial_balance_columns | reporting/statements.py · build_trial_balance | build_trial_balance lists all accounts with debit and credit columns | test_statements.py | passed | |
| 9 | trial_balance_balanced | reporting/statements.py · build_trial_balance | build_trial_balance total debits equal total credits | test_statements.py | passed | |
