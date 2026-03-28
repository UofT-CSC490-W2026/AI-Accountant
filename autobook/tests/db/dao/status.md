# tests/db/dao/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | users_create | db/dao/users.py · create | users: create inserts user with correct fields | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 2 | users_get_by_id_found | db/dao/users.py · get_by_id | users: get_by_id returns user when found | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 3 | users_get_by_id_not_found | db/dao/users.py · get_by_id | users: get_by_id returns None when not found | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 4 | users_get_by_email | db/dao/users.py · get_by_email | users: get_by_email returns user when found | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 5 | users_get_by_cognito_sub | db/dao/users.py · get_by_cognito_sub | users: get_by_cognito_sub returns user when found | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 6 | users_get_or_create_new | db/dao/users.py · get_or_create_from_cognito_claims | users: get_or_create creates new user and seeds chart of accounts | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 7 | users_get_or_create_existing | db/dao/users.py · get_or_create_from_cognito_claims | users: get_or_create returns existing user without reinserting | test_users.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 8 | auth_sessions_create | db/dao/auth_sessions.py · record_token | auth_sessions: record_token creates new session for new fingerprint | test_auth_sessions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 9 | auth_sessions_update_seen | db/dao/auth_sessions.py · record_token | auth_sessions: record_token updates last_seen_at for existing session | test_auth_sessions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 10 | auth_sessions_update_user | db/dao/auth_sessions.py · record_token | auth_sessions: record_token updates user last_authenticated_at | test_auth_sessions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 11 | coa_list_by_user | db/dao/chart_of_accounts.py · list_by_user | chart_of_accounts: list_by_user returns all accounts for user | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 12 | coa_get_by_code_found | db/dao/chart_of_accounts.py · get_by_code | chart_of_accounts: get_by_code returns account when found | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 13 | coa_get_by_code_not_found | db/dao/chart_of_accounts.py · get_by_code | chart_of_accounts: get_by_code returns None when not found | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 14 | coa_get_or_create_existing | db/dao/chart_of_accounts.py · get_or_create | chart_of_accounts: get_or_create returns existing account | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 15 | coa_get_or_create_new | db/dao/chart_of_accounts.py · get_or_create | chart_of_accounts: get_or_create creates new account with auto_created flag | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 16 | coa_seed_defaults | db/dao/chart_of_accounts.py · seed_defaults | chart_of_accounts: seed_defaults creates all 19 default accounts | test_chart_of_accounts.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 17 | transactions_insert | db/dao/transactions.py · insert | transactions: insert creates transaction with normalized fields | test_transactions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 18 | transactions_update_normalized | db/dao/transactions.py · update_normalized_fields | transactions: update_normalized_fields updates description, amount, and mentions | test_transactions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 19 | transactions_update_ml | db/dao/transactions.py · update_ml_enrichment | transactions: update_ml_enrichment updates intent, entities, and bank category | test_transactions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 20 | transactions_get_by_id_found | db/dao/transactions.py · get_by_id | transactions: get_by_id returns transaction when found | test_transactions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 21 | transactions_get_by_id_not_found | db/dao/transactions.py · get_by_id | transactions: get_by_id returns None when not found | test_transactions.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 22 | clarifications_insert | db/dao/clarifications.py · insert | clarifications: insert creates clarification task | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 23 | clarifications_list_pending | db/dao/clarifications.py · list_pending | clarifications: list_pending returns only pending tasks for user | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 24 | clarifications_list_empty | db/dao/clarifications.py · list_pending | clarifications: list_pending returns empty list when none pending | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 25 | clarifications_resolve_approve | db/dao/clarifications.py · resolve | clarifications: resolve with approve creates journal entry and marks resolved | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 26 | clarifications_resolve_reject | db/dao/clarifications.py · resolve | clarifications: resolve with reject marks rejected without journal entry | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 27 | clarifications_count | db/dao/clarifications.py · count_pending | clarifications: count_pending returns correct count | test_clarifications.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 28 | je_insert_with_lines | db/dao/journal_entries.py · insert_with_lines | journal_entries: insert_with_lines creates entry and all lines | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 29 | je_insert_unbalanced | db/dao/journal_entries.py · insert_with_lines | journal_entries: insert_with_lines raises when debits do not equal credits | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 30 | je_list_date_filter | db/dao/journal_entries.py · list_by_user | journal_entries: list_by_user returns entries filtered by date range | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 31 | je_list_account_filter | db/dao/journal_entries.py · list_by_user | journal_entries: list_by_user returns entries filtered by account | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 32 | je_get_by_id | db/dao/journal_entries.py · get_by_id | journal_entries: get_by_id returns entry with lines | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 33 | je_compute_balances | db/dao/journal_entries.py · compute_balances | journal_entries: compute_balances returns correct balance per account type | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
| 34 | je_compute_summary | db/dao/journal_entries.py · compute_summary | journal_entries: compute_summary returns total debits and total credits | test_journal_entries.py | passed | SQLite; set_current_user_context patched as no-op via tests/db/conftest.py |
