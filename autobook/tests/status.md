# tests/ (root) Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | normalize_with_value | local_identity.py · normalize_external_user_id | normalize returns stripped value when present | test_local_identity.py | passed | |
| 2 | normalize_defaults | local_identity.py · normalize_external_user_id | normalize defaults to demo-user-1 for None or empty | test_local_identity.py | passed | |
| 3 | build_email | local_identity.py · build_local_user_email | build_local_user_email slugifies and appends @autobook.local | test_local_identity.py | passed | |
| 4 | resolve_existing | local_identity.py · resolve_local_user | resolve_local_user returns existing user from DB | test_local_identity.py | passed | |
| 5 | resolve_creates_new | local_identity.py · resolve_local_user | resolve_local_user creates new user when not found | test_local_identity.py | passed | |
