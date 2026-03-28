# Overall Status

## Summary

| Date & Time | Total Stmts | Covered | Missing | Coverage % | Notes |
|---|---|---|---|---|---|
| 2026-03-23 | 2475 | 1305 | 1170 | 49% | baseline |
| 2026-03-23 | 2216 | 2151 | 65 | 96% | 258 tests passing |
| 2026-03-26 | 3090 | 2634 | 456 | 82% | 217 tests passing; fixed stale tests after backend refactor |
| 2026-03-26 | 2903 | 2818 | 85 | 96% | 418 tests passing; filled coverage gaps + adapted to remote changes |

## Per Directory

| Directory | Backend Module(s) | Stmts | Miss | Coverage % |
|---|---|---|---|---|
| tests/ | config.py, local_identity.py | 80 | 0 | 100% |
| tests/api/ | api/main.py, api/dependencies.py | 37 | 0 | 100% |
| tests/api/routes/ | api/routes/*.py (6 measured) | 152 | 12 | 92% |
| tests/auth/ | auth/deps.py, token_service.py, mock_cognito.py, schemas.py | 268 | 12 | 96% |
| tests/cache/ | cache/redis.py | 12 | 0 | 100% |
| tests/db/ | db/connection.py, db/credentials.py | 31 | 0 | 100% |
| tests/db/dao/ | db/dao/*.py (7 files) | 353 | 14 | 96% |
| tests/db/models/ | db/models/*.py (18 files) | 490 | 0 | 100% |
| tests/queues/ | queues/pubsub/client+pub+sub, sqs/client+enqueue+dequeue | 115 | 6 | 95% |
| tests/reporting/ | reporting/statements.py | 90 | 0 | 100% |
| tests/schemas/ | schemas/*.py (8 files) | 114 | 0 | 100% |
| tests/services/agent/ | accounting_engine/rules.py (agent pipeline omitted from coverage) | 53 | 0 | 100% |
| tests/services/flywheel/ | services/flywheel/aws.py, service.py | 12 | 0 | 100% |
| tests/services/ml_inference/ | services/ml_inference/aws.py, service.py, logic.py, heuristic.py | 310 | 12 | 96% |
| tests/services/normalizer/ | services/normalizer/aws.py, service.py, logic.py | 177 | 10 | 94% |
| tests/services/posting/ | services/posting/aws.py, service.py | 76 | 1 | 99% |
| tests/services/precedent/ | services/precedent/aws.py, service.py, logic.py | 126 | 8 | 94% |
| tests/services/resolution/ | services/resolution/aws.py, service.py | 70 | 0 | 100% |
| tests/services/shared/ | services/shared/parse_status.py, routing.py, transaction_persistence.py | 135 | 10 | 93% |

## Omitted from Coverage

| Path | Reason |
|---|---|
| `services/ws_relay/*` | WebSocket relay — while True loop, DynamoDB at module level |
| `services/*/__main__.py` | Lambda entry points |
| `vectordb/*` | Qdrant init scripts |
| `api/routes/ws.py` | Requires live WebSocket client + Redis |
| `api/routes/events.py` | Requires live SSE stream + Redis |
| `services/agent/*` (except service.py, graph/state.py) | LLM agent pipeline — excluded from coverage config |
| `accounting_engine/*` (except rules.py) | Accounting engine stubs — excluded from coverage config |
| `ml_inference/providers/deberta_classifier.py` | Requires trained DeBERTa model artifact |
| `ml_inference/providers/deberta_ner.py` | Requires trained DeBERTa model artifact |
| `ml_inference/providers/base.py` | Abstract base class |
| `queues/__init__.py` | Lazy module loader (`__getattr__`) |

## History

| Date & Time | Coverage % | Notes |
|---|---|---|
| 2026-03-23 | 49% | baseline |
| 2026-03-23 | 96% | 258 tests, all passing |
| 2026-03-26 | 82% | 217 tests; fixed 21 stale test files after backend refactor |
| 2026-03-26 | 96% | 418 tests; filled gaps + adapted to 3 remote commits (ml_inference _persist_transaction_state, _preferred_vendor, parse_status _normalize_confidence) |
