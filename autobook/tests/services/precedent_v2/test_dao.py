"""Tests for services/precedent_v2/dao.py — PrecedentDAO data access.

Uses SQLite in-memory DB with the full model set (via conftest db_session fixture).
Covers:
- get_by_vendor: returns matching entries, respects time window, ordering
- insert: creates entry with correct fields and computed structure_hash
- invalidate_by_accounts: deletes entries referencing given account codes
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from services.precedent_v2.dao import PrecedentDAO
from services.precedent_v2.models import PrecedentEntry, compute_structure_hash

RENT_STRUCTURE = {
    "lines": [
        {"account_code": "5200", "side": "debit"},
        {"account_code": "1000", "side": "credit"},
    ]
}
RENT_RATIO = {
    "lines": [
        {"account_code": "5200", "ratio": 1.0},
        {"account_code": "1000", "ratio": 1.0},
    ]
}
EQUIP_STRUCTURE = {
    "lines": [
        {"account_code": "1500", "side": "debit"},
        {"account_code": "1000", "side": "credit"},
    ]
}
EQUIP_RATIO = {
    "lines": [
        {"account_code": "1500", "ratio": 1.0},
        {"account_code": "1000", "ratio": 1.0},
    ]
}

USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def _noop_set_user_context():
    """Replace PostgreSQL set_config with a no-op for SQLite tests."""
    with patch("services.precedent_v2.dao.set_current_user_context", lambda db, uid: None):
        yield


def _seed_user(db, user_id=None):
    """Insert a minimal user row so ForeignKey constraints pass."""
    uid = user_id or USER_ID
    from db.models.user import User

    existing = db.get(User, uid)
    if existing:
        return existing
    user = User(id=uid, email=f"{uid}@test.com", cognito_sub=str(uid))
    db.add(user)
    db.flush()
    return user


def _seed_entry(
    db,
    user_id=None,
    vendor="apple",
    amount=2000.0,
    structure=None,
    ratio=None,
    created_at=None,
):
    """Insert a PrecedentEntry directly for test setup."""
    uid = user_id or USER_ID
    struct = structure or RENT_STRUCTURE
    r = ratio or RENT_RATIO
    entry = PrecedentEntry(
        user_id=uid,
        vendor=vendor,
        amount=Decimal(str(amount)),
        structure_hash=compute_structure_hash(struct),
        structure=struct,
        ratio=r,
    )
    if created_at:
        entry.created_at = created_at
    db.add(entry)
    db.flush()
    return entry


# ── get_by_vendor ────────────────────────────────────────────────────────


class TestGetByVendor:
    def test_returns_matching_entries(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple")
        _seed_entry(db_session, vendor="apple")
        _seed_entry(db_session, vendor="google")  # different vendor
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple")
        assert len(results) == 2
        assert all(e.vendor == "apple" for e in results)

    def test_returns_empty_for_unknown_vendor(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple")
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "unknown")
        assert results == []

    def test_respects_time_window(self, db_session):
        _seed_user(db_session)
        # Recent entry (within 365 days)
        _seed_entry(db_session, vendor="apple")
        # Old entry (outside 365-day window)
        _seed_entry(
            db_session,
            vendor="apple",
            created_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple", time_window_days=365)
        assert len(results) == 1

    def test_custom_time_window(self, db_session):
        _seed_user(db_session)
        _seed_entry(
            db_session,
            vendor="apple",
            created_at=datetime.now(timezone.utc) - timedelta(days=50),
        )
        db_session.commit()

        # 30-day window should exclude 50-day-old entry
        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple", time_window_days=30)
        assert len(results) == 0

        # 60-day window should include it
        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple", time_window_days=60)
        assert len(results) == 1

    def test_ordered_by_created_at_desc(self, db_session):
        _seed_user(db_session)
        old = _seed_entry(
            db_session,
            vendor="apple",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        new = _seed_entry(
            db_session,
            vendor="apple",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple")
        assert results[0].id == new.id
        assert results[1].id == old.id

    def test_scoped_to_user(self, db_session):
        _seed_user(db_session, USER_ID)
        _seed_user(db_session, OTHER_USER_ID)
        _seed_entry(db_session, user_id=USER_ID, vendor="apple")
        _seed_entry(db_session, user_id=OTHER_USER_ID, vendor="apple")
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple")
        assert len(results) == 1
        assert results[0].user_id == USER_ID


# ── insert ───────────────────────────────────────────────────────────────


class TestInsert:
    def test_inserts_entry_with_correct_fields(self, db_session):
        _seed_user(db_session)
        entry = PrecedentDAO.insert(
            db_session,
            user_id=USER_ID,
            vendor="apple",
            amount=Decimal("2000.00"),
            structure=RENT_STRUCTURE,
            ratio=RENT_RATIO,
        )
        db_session.commit()

        assert entry.id is not None
        assert entry.user_id == USER_ID
        assert entry.vendor == "apple"
        assert entry.amount == Decimal("2000.00")
        assert entry.structure == RENT_STRUCTURE
        assert entry.ratio == RENT_RATIO
        assert entry.source_journal_entry_id is None

    def test_computes_structure_hash(self, db_session):
        _seed_user(db_session)
        entry = PrecedentDAO.insert(
            db_session,
            user_id=USER_ID,
            vendor="apple",
            amount=Decimal("100.00"),
            structure=RENT_STRUCTURE,
            ratio=RENT_RATIO,
        )
        db_session.commit()

        expected_hash = compute_structure_hash(RENT_STRUCTURE)
        assert entry.structure_hash == expected_hash

    def test_insert_with_source_journal_entry_id(self, db_session):
        _seed_user(db_session)
        je_id = uuid.uuid4()
        entry = PrecedentDAO.insert(
            db_session,
            user_id=USER_ID,
            vendor="apple",
            amount=Decimal("500.00"),
            structure=RENT_STRUCTURE,
            ratio=RENT_RATIO,
            source_journal_entry_id=je_id,
        )
        db_session.commit()

        assert entry.source_journal_entry_id == je_id

    def test_insert_is_queryable(self, db_session):
        _seed_user(db_session)
        PrecedentDAO.insert(
            db_session,
            user_id=USER_ID,
            vendor="apple",
            amount=Decimal("2000.00"),
            structure=RENT_STRUCTURE,
            ratio=RENT_RATIO,
        )
        db_session.commit()

        results = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple")
        assert len(results) == 1
        assert results[0].vendor == "apple"


# ── invalidate_by_accounts ───────────────────────────────────────────────


class TestInvalidateByAccounts:
    def test_deletes_entries_with_matching_account_codes(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple", structure=RENT_STRUCTURE)  # has 5200, 1000
        _seed_entry(db_session, vendor="google", structure=EQUIP_STRUCTURE)  # has 1500, 1000
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, ["5200"]
        )
        db_session.commit()

        assert deleted == 1
        remaining = PrecedentDAO.get_by_vendor(db_session, USER_ID, "apple")
        assert len(remaining) == 0
        remaining_equip = PrecedentDAO.get_by_vendor(db_session, USER_ID, "google")
        assert len(remaining_equip) == 1

    def test_deletes_entries_matching_shared_account_code(self, db_session):
        """Account 1000 appears in both RENT and EQUIP structures."""
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple", structure=RENT_STRUCTURE)
        _seed_entry(db_session, vendor="google", structure=EQUIP_STRUCTURE)
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, ["1000"]
        )
        db_session.commit()

        assert deleted == 2

    def test_returns_zero_when_no_match(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple", structure=RENT_STRUCTURE)
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, ["9999"]
        )
        assert deleted == 0

    def test_scoped_to_user(self, db_session):
        _seed_user(db_session, USER_ID)
        _seed_user(db_session, OTHER_USER_ID)
        _seed_entry(db_session, user_id=USER_ID, vendor="apple", structure=RENT_STRUCTURE)
        _seed_entry(db_session, user_id=OTHER_USER_ID, vendor="apple", structure=RENT_STRUCTURE)
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, ["5200"]
        )
        db_session.commit()

        assert deleted == 1
        # Other user's entry still exists
        other_entries = PrecedentDAO.get_by_vendor(db_session, OTHER_USER_ID, "apple")
        assert len(other_entries) == 1

    def test_handles_empty_account_codes_list(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple", structure=RENT_STRUCTURE)
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, []
        )
        assert deleted == 0

    def test_multiple_account_codes(self, db_session):
        _seed_user(db_session)
        _seed_entry(db_session, vendor="apple", structure=RENT_STRUCTURE)  # 5200, 1000
        _seed_entry(db_session, vendor="google", structure=EQUIP_STRUCTURE)  # 1500, 1000
        db_session.commit()

        deleted = PrecedentDAO.invalidate_by_accounts(
            db_session, USER_ID, ["5200", "1500"]
        )
        db_session.commit()

        assert deleted == 2
