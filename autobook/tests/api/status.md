# tests/api/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | get_current_local_user_from_param | api/dependencies.py · get_current_local_user | get_current_local_user returns user from query parameter | test_dependencies.py | passed | |
| 2 | get_current_local_user_default | api/dependencies.py · get_current_local_user | get_current_local_user defaults to demo user when param is absent | test_dependencies.py | passed | |
