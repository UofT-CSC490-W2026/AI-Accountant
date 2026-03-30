from __future__ import annotations

from datetime import date

import pytest

from db.dao.clarifications import ClarificationDAO
from db.dao.transactions import TransactionDAO
from db.dao.users import UserDAO


def _setup(db):
    user = UserDAO.create(db, email=f"cl-{id(db)}@example.com")
    tx = TransactionDAO.insert(
        db=db, user_id=user.id, description="Test", normalized_description="test",
        amount=100, currency="CAD", date=date(2026, 3, 23), source="manual", counterparty=None,
    )
    return user, tx


def test_clarifications_insert(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="unclear", explanation="needs review",
        confidence=0.5, proposed_entry=None, verdict="needs_human_review",
    )
    assert task.id is not None
    assert task.status == "pending"


def test_clarifications_insert_allows_metadata_without_proposed_entry(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session,
        user_id=user.id,
        transaction_id=tx.id,
        source_text="unclear",
        explanation="needs review",
        confidence=0.5,
        proposed_entry=None,
        verdict="needs_human_review",
        parse_id="parse_123",
        child_parse_id="parse_123",
        statement_index=0,
        statement_total=1,
    )
    assert task.proposed_entry == {
        "entry": {
            "parse_id": "parse_123",
            "child_parse_id": "parse_123",
            "statement_index": 0,
            "statement_total": 1,
        },
        "lines": [],
    }


def test_clarifications_list_pending(db_session):
    user, tx = _setup(db_session)
    ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="unclear", explanation="review",
        confidence=0.5, proposed_entry=None, verdict="needs_human_review",
    )
    pending = ClarificationDAO.list_pending(db_session, user.id)
    assert len(pending) == 1


def test_clarifications_list_empty(db_session):
    user, _ = _setup(db_session)
    pending = ClarificationDAO.list_pending(db_session, user.id)
    assert pending == []


def test_clarifications_resolve_approve(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="approve test", explanation="review",
        confidence=0.8,
        proposed_entry={
            "entry": {"date": "2026-03-23", "description": "Approved entry"},
            "lines": [
                {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 100},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
            ],
        },
        verdict="needs_human_review",
    )
    resolved_task, journal_entry = ClarificationDAO.resolve(db_session, task.id, "approve")
    assert resolved_task.status == "resolved"
    assert journal_entry is not None
    assert journal_entry.id is not None


def test_clarifications_resolve_reject(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="reject test", explanation="review",
        confidence=0.3, proposed_entry=None, verdict="needs_human_review",
    )
    resolved_task, journal_entry = ClarificationDAO.resolve(db_session, task.id, "reject")
    assert resolved_task.status == "rejected"
    assert journal_entry is None


def test_clarifications_resolve_unsupported_action(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="test", explanation="review",
        confidence=0.5, proposed_entry={"entry": {"date": "2026-03-23", "description": "Test"}, "lines": [
            {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 100},
            {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
        ]}, verdict="needs_human_review",
    )
    with pytest.raises(ValueError, match="unsupported"):
        ClarificationDAO.resolve(db_session, task.id, "invalid_action")


def test_clarifications_resolve_flat_payload(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="flat", explanation="review",
        confidence=0.8,
        proposed_entry={
            "date": "2026-03-23",
            "description": "Flat payload",
            "lines": [
                {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 100},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
            ],
        },
        verdict="needs_human_review",
    )
    resolved_task, je = ClarificationDAO.resolve(db_session, task.id, "approve")
    assert resolved_task.status == "resolved"
    assert je is not None


def test_clarifications_resolve_merges_edited_lines_with_existing_entry_metadata(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="edited", explanation="review",
        confidence=0.8,
        proposed_entry={
            "entry": {"date": "2026-03-23", "description": "Needs account correction"},
            "lines": [
                {"account_code": "9999", "account_name": "Unknown Destination", "type": "debit", "amount": 100},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
            ],
        },
        verdict="needs_human_review",
    )
    resolved_task, je = ClarificationDAO.resolve(
        db_session,
        task.id,
        "approve",
        edited_entry={
            "lines": [
                {"account_code": "1100", "account_name": "Accounts Receivable", "type": "debit", "amount": 100},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
            ],
        },
    )
    assert resolved_task.status == "resolved"
    assert je is not None
    assert je.description == "Needs account correction"
    assert resolved_task.proposed_entry["lines"][0]["account_code"] == "1100"


def test_clarifications_resolve_manual_entry_without_existing_proposed_entry(db_session):
    user, tx = _setup(db_session)
    task = ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="manual review", explanation="Manager created the entry manually.",
        confidence=0.4, proposed_entry=None, verdict="needs_human_review",
    )
    resolved_task, je = ClarificationDAO.resolve(
        db_session,
        task.id,
        "approve",
        edited_entry={
            "lines": [
                {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 100},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
            ],
        },
    )
    assert resolved_task.status == "resolved"
    assert je is not None
    assert je.description == "Test"
    assert str(je.date) == "2026-03-23"
    assert resolved_task.proposed_entry["lines"][0]["account_code"] == "1500"


def test_clarifications_count(db_session):
    user, tx = _setup(db_session)
    assert ClarificationDAO.count_pending(db_session, user.id) == 0
    ClarificationDAO.insert(
        db_session, user_id=user.id, transaction_id=tx.id,
        source_text="count test", explanation="review",
        confidence=0.5, proposed_entry=None, verdict="needs_human_review",
    )
    assert ClarificationDAO.count_pending(db_session, user.id) == 1
