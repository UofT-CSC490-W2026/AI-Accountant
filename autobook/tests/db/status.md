# tests/db/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | get_db_yields_and_closes | db/connection.py · get_db | get_db yields a session and closes it after use | test_connection.py | passed | |
| 2 | get_db_rollback_on_exception | db/connection.py · get_db | get_db rolls back session on exception | test_connection.py | passed | |
| 3 | set_user_context | db/connection.py · set_current_user_context | set_current_user_context executes set_config SQL with correct user_id | test_connection.py | pending | test with mock session; patch as no-op in tests/db/conftest.py for DAO tests |
| 4 | get_database_url_env_var | db/credentials.py · get_database_url | get_database_url returns DATABASE_URL env var when no secret ARN set | test_credentials.py | passed | |
| 5 | get_database_url_cached | db/credentials.py · get_database_url | get_database_url result is cached across multiple calls | test_credentials.py | passed | |
| 6 | get_database_url_secrets_manager | db/credentials.py · get_database_url | Secrets Manager branch — Lambda Extension at localhost:2773 | n/a | omitted | pragma: no cover — only reachable inside Lambda execution environment |
