from __future__ import annotations

from db.models.organization import Organization
from db.models.document import CorporateDocument
from db.models.reconciliation import ReconciliationRecord
from db.models.tax import TaxObligation
from db.models.integration import IntegrationConnection
from db.models.shareholder_loan import ShareholderLoanLedger
from db.models.account import ChartOfAccounts
from db.models.journal import JournalEntry, JournalLine
from db.models.asset import Asset
from db.models.schedule import ScheduledEntry


def test_model_organization():
    assert Organization.__tablename__ == "organizations"
    assert hasattr(Organization, "name")
    assert hasattr(Organization, "jurisdiction")


def test_model_document():
    assert CorporateDocument.__tablename__ == "corporate_documents"
    assert hasattr(CorporateDocument, "document_type")
    assert hasattr(CorporateDocument, "description")


def test_model_reconciliation():
    assert ReconciliationRecord.__tablename__ == "reconciliation_records"
    assert hasattr(ReconciliationRecord, "status")


def test_model_tax():
    assert TaxObligation.__tablename__ == "tax_obligations"
    assert hasattr(TaxObligation, "tax_type")
    assert hasattr(TaxObligation, "status")


def test_model_integration():
    assert IntegrationConnection.__tablename__ == "integration_connections"
    assert hasattr(IntegrationConnection, "platform")
    assert hasattr(IntegrationConnection, "status")


def test_model_shareholder_loan():
    assert ShareholderLoanLedger.__tablename__ == "shareholder_loan_ledger"
    assert hasattr(ShareholderLoanLedger, "shareholder_name")
    assert hasattr(ShareholderLoanLedger, "amount")


def test_model_account():
    assert ChartOfAccounts.__tablename__ == "chart_of_accounts"
    assert hasattr(ChartOfAccounts, "account_code")
    assert hasattr(ChartOfAccounts, "account_name")
    assert hasattr(ChartOfAccounts, "account_type")


def test_model_account_properties(db_session):
    from db.dao.users import UserDAO
    from db.dao.chart_of_accounts import ChartOfAccountsDAO
    user = UserDAO.create(db_session, email="prop-test@example.com")
    acct = ChartOfAccountsDAO.get_by_code(db_session, user.id, "1000")
    assert acct.account_number == "1000"
    assert acct.name == "Cash"
    assert acct.org_id == user.id
    acct.account_number = "1001"
    assert acct.account_code == "1001"
    acct.name = "Petty Cash"
    assert acct.account_name == "Petty Cash"


def test_model_journal():
    assert JournalEntry.__tablename__ == "journal_entries"
    assert hasattr(JournalEntry, "description")
    assert JournalLine.__tablename__ == "journal_lines"
    assert hasattr(JournalLine, "account_code")
    assert hasattr(JournalLine, "type")
    assert hasattr(JournalLine, "amount")


def test_model_journal_properties(db_session):
    from datetime import date
    from db.dao.users import UserDAO
    from db.dao.journal_entries import JournalEntryDAO
    user = UserDAO.create(db_session, email="je-prop@example.com")
    entry = JournalEntryDAO.insert_with_lines(
        db_session, user.id,
        {"date": date(2026, 3, 23), "description": "Prop test", "status": "posted"},
        [
            {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 100},
            {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
        ],
    )
    assert entry.entry_date == date(2026, 3, 23)
    entry.entry_date = date(2026, 6, 1)
    assert entry.date == date(2026, 6, 1)
    assert entry.posted_date is not None


def test_model_asset():
    assert Asset.__tablename__ == "assets"
    assert hasattr(Asset, "name")
    assert hasattr(Asset, "acquisition_cost")


def test_model_asset_org_id(db_session):
    from uuid import uuid4
    from db.dao.users import UserDAO
    user = UserDAO.create(db_session, email="asset-org@example.com")
    asset = Asset(user_id=user.id, name="Laptop", acquisition_cost=1000)
    assert asset.org_id == user.id


def test_model_schedule():
    assert ScheduledEntry.__tablename__ == "scheduled_entries"
    assert hasattr(ScheduledEntry, "frequency")
    assert hasattr(ScheduledEntry, "source")


def test_model_schedule_org_id(db_session):
    from uuid import uuid4
    from db.dao.users import UserDAO
    user = UserDAO.create(db_session, email="sched-org@example.com")
    s = ScheduledEntry(user_id=user.id, amount=100, frequency="monthly")
    assert s.org_id == user.id
