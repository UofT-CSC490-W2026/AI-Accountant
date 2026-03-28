# Strategy

| # | Strategy | Rationale |
|---|---|---|
| 1 | Omit `services/ws_relay/*` and `services/*/__main__.py` from coverage config | Structurally untestable — `while True` loops, DynamoDB at module level, full AWS event loops |
| 2 | Omit `api/routes/ws.py` and `api/routes/events.py` from coverage config | Require live WebSocket client and SSE stream with real Redis — not testable in unit tests |
| 3 | `# pragma: no cover` on Secrets Manager branch in `db/credentials.py` | Calls Lambda Extension at localhost:2773 — only reachable inside a Lambda execution environment |
| 4 | `# pragma: no cover` on Cognito OAuth redirect flows in `api/routes/auth.py` | External Cognito redirect — cannot be unit tested without a live Cognito domain |
| 5 | Add `moto[sqs,secretsmanager]` + `fakeredis` to dev deps | Unlocks SQS, Redis, Secrets Manager testing without real AWS |
| 6 | Add `__init__.py` to all test dirs | Prevents name collision when multiple files share the same filename |
| 7 | Set `DATABASE_URL=sqlite:///:memory:` in `conftest.py` before imports | `db/connection.py` calls `create_engine()` at import time |
| 8 | Patch `set_current_user_context` as a no-op in `tests/db/conftest.py` (autouse) | Every DAO method calls `select set_config(...)` — PostgreSQL-only SQL that fails on SQLite |
| 9 | Tier 1 — Pure business logic (agent/execute, ml_inference/service, normalizer/service, reporting/statements, auth/token_service) | Highest lines × lowest difficulty — pure Python, no infra deps |
| 10 | Tier 2 — API routes (clarifications, ledger, statements) | TestClient pattern already established |
| 11 | Tier 3 — Pipeline workers (posting, resolution, precedent, flywheel process files) | Monkeypatch pattern already established |
| 12 | Tier 4 — Lambda handlers (×6) | 3 lines of logic each, trivially testable |
| 13 | Tier 5 — Infrastructure (SQS, Redis, cache) with moto/fakeredis | Plumbing sanity with mock backends |
| 14 | Tier 6 — DAOs with SQLite in-memory | Most effort, highest line count — brings coverage to 96%+ |
| 15 | `# pragma: no cover` on any remaining module-level side effects | boto3 module-level clients in queues/sqs.py |
