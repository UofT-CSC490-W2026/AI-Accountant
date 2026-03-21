# P1 DB/DAO Handoff

## Status

This branch completes the P1 database and DAO foundation for the backend.

It is intended to be the persistence source of truth for the project's core accounting pipeline:

- `users`
- `chart_of_accounts`
- `transactions`
- `journal_entries`
- `journal_lines`
- `clarification_tasks`

It also includes the remaining P1 support tables needed by later backend work:

- `assets`
- `cca_schedule_entries`
- `scheduled_entries`

## What Was Implemented

### Database foundation

The schema is created by Alembic in:

- [backend/alembic/versions/20260321_0001_pipeline_foundation.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/alembic/versions/20260321_0001_pipeline_foundation.py)

That migration creates all core tables and enforces the required DB-level rules:

- posted journal entries are immutable
- journal entries must balance
- user-scoped access is supported through PostgreSQL row-level security
- local development is aligned to Postgres port `5433`

### ORM models

The active persistence models are:

- [backend/app/models/user.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/user.py)
- [backend/app/models/account.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/account.py)
- [backend/app/models/transaction.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/transaction.py)
- [backend/app/models/journal.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/journal.py)
- [backend/app/models/clarification.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/clarification.py)
- [backend/app/models/asset.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/asset.py)
- [backend/app/models/schedule.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/models/schedule.py)

### DAO layer

The DAO contract lives in:

- [backend/app/db/dao/users.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/dao/users.py)
- [backend/app/db/dao/chart_of_accounts.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/dao/chart_of_accounts.py)
- [backend/app/db/dao/transactions.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/dao/transactions.py)
- [backend/app/db/dao/journal_entries.py](c:/Users\rober\OneDrive\Desktop\study_file\Third_year_winter\CSC490\AI-Accountant\project\backend\app\db\dao\journal_entries.py)
- [backend/app/db/dao/clarifications.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/dao/clarifications.py)

Implemented DAO surfaces:

- `UserDAO.create`
- `UserDAO.get_by_id`
- `UserDAO.get_by_email`
- `ChartOfAccountsDAO.list_by_user`
- `ChartOfAccountsDAO.get_by_code`
- `ChartOfAccountsDAO.get_or_create`
- `ChartOfAccountsDAO.seed_defaults`
- `TransactionDAO.insert`
- `TransactionDAO.update_ml_enrichment`
- `TransactionDAO.get_by_id`
- `JournalEntryDAO.insert_with_lines`
- `JournalEntryDAO.list_by_user`
- `JournalEntryDAO.get_by_id`
- `JournalEntryDAO.compute_balances`
- `JournalEntryDAO.compute_summary`
- `ClarificationDAO.insert`
- `ClarificationDAO.list_pending`
- `ClarificationDAO.resolve`
- `ClarificationDAO.count_pending`

## How It Is Implemented

### Stack choice

This branch keeps the repo's existing SQLAlchemy + Alembic approach rather than introducing a second persistence stack.

Core DB/session code:

- [backend/app/db/connection.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/connection.py)
- [backend/app/database.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/database.py)

### User scoping

The persistence layer is now built around `user_id`, not `org_id`.

Important implications:

- all core records belong to a user
- DAO queries are user-scoped
- PostgreSQL session context is used to support row-level access rules

The helper that sets DB session context is in:

- [backend/app/db/connection.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/db/connection.py)

### Default chart of accounts

When a user is created, the default Canadian chart of accounts is seeded automatically through `ChartOfAccountsDAO.seed_defaults`.

### Journal integrity

Two important rules are enforced at the DB level:

1. Posted entries cannot be updated or deleted.
2. Debit and credit totals must balance per journal entry.

This means downstream code should not rely on Python-only validation for accounting integrity.

## What Other Backend Parts Should Know

### Treat the DAO layer as the persistence contract

If another branch needs to store or read accounting pipeline data, it should call the DAO layer rather than writing its own model logic.

Recommended mapping:

- normalization / ingest -> `TransactionDAO`
- enrichment updates -> `TransactionDAO.update_ml_enrichment`
- posting -> `JournalEntryDAO.insert_with_lines`
- ledger queries -> `JournalEntryDAO.list_by_user`, `compute_balances`, `compute_summary`
- clarification flow -> `ClarificationDAO`
- account lookup / auto-create -> `ChartOfAccountsDAO`
- user creation / lookup -> `UserDAO`

### Do not build on the old org-centric persistence path

Older code in the repo still reflects the previous `organization` / `org_id` model. That should not be extended further for the accounting pipeline.

For new backend work, the source of truth is the new user-scoped DB/DAO layer.

### Session usage pattern

Typical usage should be:

1. open a DB session
2. set current user context
3. call DAO methods
4. commit or roll back at the request/service boundary

If code bypasses the DAO layer and queries models directly without setting user context, it may bypass the intended access pattern.

## Active API Surface

A minimal API surface was wired to this persistence layer so downstream branches have an integration point.

Active router entry:

- [backend/app/api/router.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/router.py)

Included by:

- [backend/main.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/main.py)

Active routers:

- [backend/app/api/routers/users.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/users.py)
- [backend/app/api/routers/core_accounts.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/core_accounts.py)
- [backend/app/api/routers/transactions.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/transactions.py)
- [backend/app/api/routers/core_journal_entries.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/core_journal_entries.py)
- [backend/app/api/routers/ledger.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/ledger.py)
- [backend/app/api/routers/clarifications.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/app/api/routers/clarifications.py)

These are intentionally thin and should be treated as adapters over the DAO layer.

## How the Plan Was Achieved

The branch satisfies the P1 DB/DAO plan in the following way:

- the required core schema exists
- DAO interfaces from the plan are implemented
- user-scoped persistence is in place
- default chart of accounts seeding exists
- DB-level balance enforcement exists
- DB-level posted-entry immutability exists
- local migration flow is in place
- integration tests cover the main storage flows

This means the branch is ready to hand off as the persistence foundation for later backend work.

## Testing and Verification

Integration coverage is in:

- [backend/tests/test_pipeline_api.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/tests/test_pipeline_api.py)
- [backend/tests/conftest.py](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/backend/tests/conftest.py)

Verified flows:

- user creation
- default CoA seeding
- transaction creation
- enrichment update
- balanced journal posting
- ledger summary and balances
- clarification creation and resolution
- user isolation
- posted-entry immutability

## Local Dev Notes

Relevant files:

- [compose.yaml](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/compose.yaml)
- [.env.example](c:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/project/.env.example)

Expected local DB port:

- `5433`

Typical setup flow:

```powershell
cd project
docker-compose up -d db
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
pytest
```

## Recommended Next Steps for Other Branches

- use the new DAO layer for all accounting persistence
- migrate service logic away from old org-centric model access
- build statements, agent, and workflow logic on top of `TransactionDAO`, `JournalEntryDAO`, and `ClarificationDAO`
- avoid introducing a second persistence path

## Bottom Line

This branch should be treated as the completed P1 DB/DAO handoff.

Downstream work should build on this layer rather than redefining storage behavior elsewhere.
