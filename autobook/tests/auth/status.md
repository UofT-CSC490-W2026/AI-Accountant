# tests/auth/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | decode_valid_token | auth/token_service.py · decode_access_token | decode_access_token accepts valid token with correct claims | test_token_service.py | passed | |
| 2 | decode_expired_token | auth/token_service.py · decode_access_token | decode_access_token rejects expired token | test_token_service.py | passed | |
| 3 | decode_wrong_issuer | auth/token_service.py · decode_access_token | decode_access_token rejects wrong issuer | test_token_service.py | passed | |
| 4 | decode_wrong_client_id | auth/token_service.py · decode_access_token | decode_access_token rejects wrong client_id | test_token_service.py | passed | |
| 5 | decode_wrong_token_use | auth/token_service.py · decode_access_token | decode_access_token rejects wrong token_use | test_token_service.py | passed | |
| 6 | decode_caches_jwks | auth/token_service.py · decode_access_token | decode_access_token caches JWKS keys after first fetch | test_token_service.py | passed | |
| 7 | clear_caches | auth/token_service.py · clear_caches | clear_caches resets all cached keys | test_token_service.py | passed | |
| 8 | issue_token_groups | auth/mock_cognito.py · issue_token | issue_token with groups claim produces correct role | test_mock_cognito.py | passed | |
| 9 | issue_token_custom_role | auth/mock_cognito.py · issue_token | issue_token with custom_role produces correct fallback role | test_mock_cognito.py | passed | |
| 10 | sample_tokens | auth/mock_cognito.py · sample_tokens | sample_tokens generates regular, manager, and superuser tokens | test_mock_cognito.py | passed | |
| 11 | deps_accepts_valid_token | auth/deps.py · get_current_user | GET /auth/me with valid Cognito token returns user and claims | test_deps.py | passed | |
| 12 | deps_rejects_missing_token | auth/deps.py · get_current_user | private route returns 401 when bearer token is absent | test_deps.py | passed | |
| 13 | deps_binds_authenticated_user_id | auth/deps.py · get_current_user | parse route uses authenticated user_id, ignores attacker-supplied user_id | test_deps.py | passed | |
| 14 | deps_rejects_expired_token | auth/deps.py · get_current_user | GET /auth/me with expired token returns 401 | test_deps.py | passed | |
| 15 | deps_rejects_wrong_client_id | auth/deps.py · get_current_user | GET /auth/me with wrong client_id returns 401 | test_deps.py | passed | |
| 16 | deps_manager_can_resolve | auth/deps.py · require_role | manager role allows clarification resolution | test_deps.py | passed | |
| 17 | deps_regular_blocked | auth/deps.py · require_role | regular role blocked from resolution with 403 | test_deps.py | passed | |
| 18 | deps_custom_role_fallback | auth/deps.py · get_current_user | custom:role claim used as fallback when cognito:groups absent | test_deps.py | passed | |
