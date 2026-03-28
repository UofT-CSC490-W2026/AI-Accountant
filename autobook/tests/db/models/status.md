# tests/db/models/ Status

<!-- Status values -->
<!-- pending  = not yet written -->
<!-- written  = written, not yet run -->
<!-- failed   = run and failing (see workflow.md for triage) -->
<!-- passed   = run and green -->
<!-- omitted  = excluded from coverage (pragma: no cover or config omit) -->
<!-- To update: pending → written → run pytest → passed or failed → see workflow.md -->

| # | Name | Target | Test Description | Test File | Status | Note |
|---|---|---|---|---|---|---|
| 1 | enum_account_type | db/models/enums.py · AccountType | All AccountType enum values are accessible | test_enums.py | passed | |
| 2 | enum_account_subtype | db/models/enums.py · AccountSubType | All AccountSubType enum values are accessible | test_enums.py | passed | |
| 3 | enum_journal_entry_status | db/models/enums.py · JournalEntryStatus | All JournalEntryStatus enum values are accessible | test_enums.py | passed | |
| 4 | enum_asset_status | db/models/enums.py · AssetStatus | All AssetStatus enum values are accessible | test_enums.py | passed | |
| 5 | enum_schedule_frequency | db/models/enums.py · ScheduleFrequency | All ScheduleFrequency enum values are accessible | test_enums.py | passed | |
| 6 | enum_integration_platform | db/models/enums.py · IntegrationPlatform | All IntegrationPlatform enum values are accessible | test_enums.py | passed | |
| 7 | model_organization | db/models/organization.py · Organization | Organization model instantiates with required fields | test_models.py | passed | |
| 8 | model_document | db/models/document.py · CorporateDocument | CorporateDocument model instantiates with required fields | test_models.py | passed | |
| 9 | model_reconciliation | db/models/reconciliation.py · ReconciliationRecord | ReconciliationRecord model instantiates with required fields | test_models.py | passed | |
| 10 | model_tax | db/models/tax.py · TaxObligation | TaxObligation model instantiates with required fields | test_models.py | passed | |
| 11 | model_integration | db/models/integration.py · IntegrationConnection | IntegrationConnection model instantiates with required fields | test_models.py | passed | |
| 12 | model_shareholder_loan | db/models/shareholder_loan.py · ShareholderLoanLedger | ShareholderLoanLedger model instantiates with required fields | test_models.py | passed | |
| 13 | model_account | db/models/account.py · Account | Account model instantiates with required fields | test_models.py | passed | |
| 14 | model_journal | db/models/journal.py · JournalEntry, JournalEntryLine | JournalEntry and JournalEntryLine models instantiate with required fields | test_models.py | passed | |
| 15 | model_asset | db/models/asset.py · Asset | Asset model instantiates with required fields | test_models.py | passed | |
| 16 | model_schedule | db/models/schedule.py · RecurringSchedule | RecurringSchedule model instantiates with required fields | test_models.py | passed | |
