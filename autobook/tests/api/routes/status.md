# tests/api/routes/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | health_ok | routes/health.py · GET /health | GET /health returns 200 with status ok | test_health.py | passed | |
| 2 | clarifications_list | routes/clarifications.py · GET /clarifications | GET /clarifications returns list of pending items | test_clarifications.py | passed | |
| 3 | clarifications_empty | routes/clarifications.py · GET /clarifications | GET /clarifications returns empty list when none pending | test_clarifications.py | passed | |
| 4 | clarifications_resolve_approve | routes/clarifications.py · POST /clarifications/{id}/resolve | POST resolve with approve posts entry and returns resolved | test_clarifications.py | passed | |
| 5 | clarifications_resolve_reject | routes/clarifications.py · POST /clarifications/{id}/resolve | POST resolve with reject discards entry and returns rejected | test_clarifications.py | passed | |
| 6 | clarifications_resolve_edit | routes/clarifications.py · POST /clarifications/{id}/resolve | POST resolve with edit saves modified entry | test_clarifications.py | passed | |
| 7 | clarifications_resolve_forbidden | routes/clarifications.py · POST /clarifications/{id}/resolve | POST resolve returns 403 for regular user | test_clarifications.py | passed | |
| 8 | ledger_returns_entries | routes/ledger.py · GET /ledger | GET /ledger returns entries, balances, and summary | test_ledger.py | passed | |
| 9 | ledger_filter_date | routes/ledger.py · GET /ledger | GET /ledger filters entries by date range | test_ledger.py | passed | |
| 10 | ledger_filter_account | routes/ledger.py · GET /ledger | GET /ledger filters entries by account | test_ledger.py | passed | |
| 11 | ledger_balance_totals | routes/ledger.py · GET /ledger | GET /ledger computes correct debit and credit totals per account | test_ledger.py | passed | |
| 12 | statements_balance_sheet | routes/statements.py · GET /statements | GET /statements returns balance sheet | test_statements.py | passed | |
| 13 | statements_income | routes/statements.py · GET /statements | GET /statements returns income statement | test_statements.py | passed | |
| 14 | statements_trial_balance | routes/statements.py · GET /statements | GET /statements returns trial balance | test_statements.py | passed | |
| 15 | auth_login_url | routes/auth.py · GET /auth/login-url | login-url builds Cognito hosted UI URL with client_id, challenge, and state | test_auth.py | passed | |
| 16 | auth_logout_url | routes/auth.py · GET /auth/logout-url | logout-url builds Cognito logout URL | test_auth.py | passed | |
| 17 | auth_token_exchange | routes/auth.py · POST /auth/token | token exchange returns access_token and refresh_token | test_auth.py | passed | |
| 18 | auth_validate | routes/auth.py · GET /auth/validate | validate returns authenticated user context | test_auth.py | passed | |
| 19 | parse_manual | routes/parse.py · POST /parse | parse enqueues manual input with authenticated user_id | test_parse.py | passed | |
| 20 | parse_upload_csv | routes/parse.py · POST /parse/upload | upload enqueues csv file with filename, source, and user_id | test_parse.py | passed | |
| 21 | parse_upload_pdf_infers_source | routes/parse.py · POST /parse/upload | upload infers pdf_upload source when no source metadata provided | test_parse.py | passed | |
| 22 | events_sse_content_type | routes/events.py · GET /api/v1/events | GET /api/v1/events returns SSE stream with correct content-type | test_events.py | omitted | coverage omit: requires live Redis pub/sub, SSE stream not testable in unit tests |
| 23 | ws_connects_receives | routes/ws.py · WebSocket /ws | WebSocket /ws connects and receives entry.posted events | test_ws.py | omitted | coverage omit: requires live WebSocket client + Redis — file excluded from coverage config |
| 24 | ws_filters_by_user | routes/ws.py · WebSocket /ws | WebSocket /ws filters events by user_id | test_ws.py | omitted | coverage omit: requires live WebSocket client + Redis — file excluded from coverage config |
