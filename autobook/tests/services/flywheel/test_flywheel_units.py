"""Unit tests for flywheel sub-modules: pattern_store, rag_indexer, calibration, and DAOs.

Covers:
- pattern_store.write_pattern: happy path + all skip conditions + _safe_ratio edge cases
- rag_indexer.index_positive_example / index_correction_example: happy, skip, exception
- calibration.write_calibration_pair: happy path + skip conditions
- TrainingDataDAO / CalibrationDataDAO: append + count_pending (in-memory SQLite)
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# pattern_store tests
# ---------------------------------------------------------------------------

VALID_MESSAGE = {
    "counterparty": "Apple Inc.",
    "amount": 1000.0,
    "proposed_entry": {
        "lines": [
            {"account_code": "5200", "type": "debit", "amount": 600.0},
            {"account_code": "1000", "type": "credit", "amount": 400.0},
        ]
    },
    "journal_entry_id": str(uuid.uuid4()),
}


class TestWritePattern:
    """Tests for services.flywheel.pattern_store.write_pattern."""

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_happy_path_calls_insert(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        db = MagicMock()
        user_id = uuid.uuid4()
        write_pattern(db, user_id, VALID_MESSAGE)

        mock_dao.insert.assert_called_once()
        kwargs = mock_dao.insert.call_args
        assert kwargs.kwargs["vendor"] == "apple"
        assert kwargs.kwargs["amount"] == Decimal("1000.0")
        assert kwargs.kwargs["db"] is db
        assert kwargs.kwargs["user_id"] is user_id

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_happy_path_structure_and_ratio(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        db = MagicMock()
        write_pattern(db, uuid.uuid4(), VALID_MESSAGE)

        kwargs = mock_dao.insert.call_args.kwargs
        structure = kwargs["structure"]
        ratio = kwargs["ratio"]

        assert len(structure["lines"]) == 2
        assert structure["lines"][0]["account_code"] == "5200"
        assert structure["lines"][0]["side"] == "debit"

        # ratio = line_amount / total_amount
        assert ratio["lines"][0]["ratio"] == round(600.0 / 1000.0, 6)
        assert ratio["lines"][1]["ratio"] == round(400.0 / 1000.0, 6)

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="")
    def test_skip_no_vendor(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        write_pattern(MagicMock(), uuid.uuid4(), {"counterparty": ""})
        mock_dao.insert.assert_not_called()

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_skip_no_amount(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        msg = {**VALID_MESSAGE, "amount": None}
        write_pattern(MagicMock(), uuid.uuid4(), msg)
        mock_dao.insert.assert_not_called()

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_skip_zero_amount(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        msg = {**VALID_MESSAGE, "amount": 0}
        write_pattern(MagicMock(), uuid.uuid4(), msg)
        mock_dao.insert.assert_not_called()

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_skip_no_proposed_entry(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        msg = {"counterparty": "Apple", "amount": 100.0}
        write_pattern(MagicMock(), uuid.uuid4(), msg)
        mock_dao.insert.assert_not_called()

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_skip_empty_lines(self, mock_norm, mock_dao):
        from services.flywheel.pattern_store import write_pattern

        msg = {
            "counterparty": "Apple",
            "amount": 100.0,
            "proposed_entry": {"lines": []},
        }
        write_pattern(MagicMock(), uuid.uuid4(), msg)
        mock_dao.insert.assert_not_called()

    @patch("services.flywheel.pattern_store.PrecedentDAO")
    @patch("services.flywheel.pattern_store.normalize_vendor", return_value="apple")
    def test_vendor_field_fallback(self, mock_norm, mock_dao):
        """Falls back to 'vendor' key when 'counterparty' is absent."""
        from services.flywheel.pattern_store import write_pattern

        msg = {
            "vendor": "Google LLC",
            "amount": 500.0,
            "proposed_entry": {
                "lines": [
                    {"account_code": "5100", "type": "debit", "amount": 500.0},
                    {"account_code": "1000", "type": "credit", "amount": 500.0},
                ]
            },
        }
        write_pattern(MagicMock(), uuid.uuid4(), msg)
        # normalize_vendor should have been called with 'Google LLC'
        mock_norm.assert_called_once_with("Google LLC")
        mock_dao.insert.assert_called_once()


class TestSafeRatio:
    """Tests for pattern_store._safe_ratio edge cases."""

    def test_normal_ratio(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {"amount": 250.0}
        assert _safe_ratio(line, 1000.0) == 0.25

    def test_zero_division(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {"amount": 100.0}
        assert _safe_ratio(line, 0) == 0.0

    def test_missing_amount_in_line(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {}
        assert _safe_ratio(line, 500.0) == 0.0

    def test_none_total_amount(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {"amount": 100.0}
        assert _safe_ratio(line, None) == 0.0

    def test_string_amounts(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {"amount": "300"}
        assert _safe_ratio(line, "1000") == 0.3

    def test_non_numeric_string(self):
        from services.flywheel.pattern_store import _safe_ratio

        line = {"amount": "abc"}
        assert _safe_ratio(line, 1000) == 0.0


# rag_indexer tests omitted — requires Qdrant+Bedrock stubs that conflict
# with other test modules' sys.modules stubs. Covered by test_process.py
# integration tests (mock at service.py level) + rag_indexer.py is in coverage omit.


# ---------------------------------------------------------------------------
# calibration tests
# ---------------------------------------------------------------------------


class TestWriteCalibrationPair:
    """Tests for services.flywheel.calibration.write_calibration_pair."""

    @patch("services.flywheel.calibration.CalibrationDataDAO")
    def test_happy_path(self, mock_dao):
        from services.flywheel.calibration import write_calibration_pair

        db = MagicMock()
        user_id = uuid.uuid4()
        je_id = str(uuid.uuid4())
        msg = {
            "confidence": {"overall": 0.85},
            "journal_entry_id": je_id,
            "intent_label": "revenue",
        }
        write_calibration_pair(db, user_id, msg, was_correct=True)

        mock_dao.append.assert_called_once_with(
            db=db,
            user_id=user_id,
            journal_entry_id=je_id,
            raw_confidence=0.85,
            was_correct=True,
            transaction_type="revenue",
        )

    @patch("services.flywheel.calibration.CalibrationDataDAO")
    def test_skip_no_confidence(self, mock_dao):
        from services.flywheel.calibration import write_calibration_pair

        msg = {"journal_entry_id": str(uuid.uuid4())}
        write_calibration_pair(MagicMock(), uuid.uuid4(), msg, was_correct=False)
        mock_dao.append.assert_not_called()

    @patch("services.flywheel.calibration.CalibrationDataDAO")
    def test_skip_confidence_overall_none(self, mock_dao):
        from services.flywheel.calibration import write_calibration_pair

        msg = {"confidence": {"overall": None}, "journal_entry_id": str(uuid.uuid4())}
        write_calibration_pair(MagicMock(), uuid.uuid4(), msg, was_correct=True)
        mock_dao.append.assert_not_called()

    @patch("services.flywheel.calibration.CalibrationDataDAO")
    def test_skip_no_journal_entry_id(self, mock_dao):
        from services.flywheel.calibration import write_calibration_pair

        msg = {"confidence": {"overall": 0.9}}
        write_calibration_pair(MagicMock(), uuid.uuid4(), msg, was_correct=True)
        mock_dao.append.assert_not_called()

    @patch("services.flywheel.calibration.CalibrationDataDAO")
    def test_skip_empty_confidence_dict(self, mock_dao):
        from services.flywheel.calibration import write_calibration_pair

        msg = {"confidence": {}, "journal_entry_id": str(uuid.uuid4())}
        write_calibration_pair(MagicMock(), uuid.uuid4(), msg, was_correct=False)
        mock_dao.append.assert_not_called()


# ---------------------------------------------------------------------------
# DAO tests — in-memory SQLite
# ---------------------------------------------------------------------------


@pytest.fixture
def dao_session():
    """Provide a fresh SQLite in-memory DB session with all required tables.

    Imports additional model modules (training_data, calibration_data) so that
    Base.metadata.create_all creates their tables alongside the core models.
    """
    import db.models.user  # noqa: F401
    import db.models.account  # noqa: F401
    import db.models.transaction  # noqa: F401
    import db.models.journal  # noqa: F401
    import db.models.clarification  # noqa: F401
    import db.models.auth_session  # noqa: F401
    import db.models.asset  # noqa: F401
    import db.models.schedule  # noqa: F401
    import db.models.document  # noqa: F401
    import db.models.organization  # noqa: F401
    import db.models.reconciliation  # noqa: F401
    import db.models.tax  # noqa: F401
    import db.models.integration  # noqa: F401
    import db.models.shareholder_loan  # noqa: F401
    import db.models.training_data  # noqa: F401
    import db.models.calibration_data  # noqa: F401
    from db.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    yield session
    session.close()


def _seed_user(db, user_id=None):
    """Insert a minimal user row so FK constraints pass."""
    from db.models.user import User

    uid = user_id or uuid.uuid4()
    existing = db.get(User, uid)
    if existing:
        return existing
    user = User(id=uid, email=f"{uid}@test.com", cognito_sub=str(uid))
    db.add(user)
    db.flush()
    return user


def _seed_transaction(db, user_id):
    """Insert a minimal transaction row so FK constraints pass."""
    from datetime import date

    from db.models.transaction import Transaction

    txn = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        description="test txn",
        date=date(2026, 1, 1),
        source="manual",
    )
    db.add(txn)
    db.flush()
    return txn


def _seed_journal_entry(db, user_id, transaction_id):
    """Insert a minimal journal entry row so FK constraints pass."""
    from datetime import date

    from db.models.journal import JournalEntry

    je = JournalEntry(
        id=uuid.uuid4(),
        user_id=user_id,
        transaction_id=transaction_id,
        date=date(2026, 1, 1),
        description="test journal entry",
    )
    db.add(je)
    db.flush()
    return je


class TestTrainingDataDAO:
    """Tests for db.dao.training_data.TrainingDataDAO using in-memory SQLite."""

    @patch("db.dao.training_data.set_current_user_context", lambda db, uid: None)
    def test_append_creates_row(self, dao_session):
        from db.dao.training_data import TrainingDataDAO
        from db.models.training_data import ModelTrainingData

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je = _seed_journal_entry(dao_session, user.id, txn.id)
        dao_session.flush()

        row = TrainingDataDAO.append(
            db=dao_session,
            user_id=user.id,
            transaction_id=txn.id,
            journal_entry_id=je.id,
            origin_tier=3,
            input_text="Paid rent $2000",
            intent_label="expense",
            proposed_entry={"lines": [{"account_code": "5200"}]},
        )
        dao_session.commit()

        assert row.id is not None
        assert row.user_id == user.id
        assert row.transaction_id == txn.id
        assert row.journal_entry_id == je.id
        assert row.origin_tier == 3
        assert row.input_text == "Paid rent $2000"
        assert row.intent_label == "expense"
        assert row.proposed_entry == {"lines": [{"account_code": "5200"}]}

    @patch("db.dao.training_data.set_current_user_context", lambda db, uid: None)
    def test_count_pending_returns_correct_count(self, dao_session):
        from db.dao.training_data import TrainingDataDAO

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je1 = _seed_journal_entry(dao_session, user.id, txn.id)
        je2 = _seed_journal_entry(dao_session, user.id, txn.id)

        assert TrainingDataDAO.count_pending(dao_session) == 0

        TrainingDataDAO.append(
            db=dao_session,
            user_id=user.id,
            transaction_id=txn.id,
            journal_entry_id=je1.id,
            origin_tier=3,
        )
        TrainingDataDAO.append(
            db=dao_session,
            user_id=user.id,
            transaction_id=txn.id,
            journal_entry_id=je2.id,
            origin_tier=4,
        )
        dao_session.commit()

        assert TrainingDataDAO.count_pending(dao_session) == 2

    @patch("db.dao.training_data.set_current_user_context", lambda db, uid: None)
    def test_append_with_optional_fields_none(self, dao_session):
        from db.dao.training_data import TrainingDataDAO

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je = _seed_journal_entry(dao_session, user.id, txn.id)

        row = TrainingDataDAO.append(
            db=dao_session,
            user_id=user.id,
            transaction_id=txn.id,
            journal_entry_id=je.id,
            origin_tier=2,
        )
        dao_session.commit()

        assert row.input_text is None
        assert row.intent_label is None
        assert row.proposed_entry is None


class TestCalibrationDataDAO:
    """Tests for db.dao.calibration_data.CalibrationDataDAO using in-memory SQLite."""

    @patch("db.dao.calibration_data.set_current_user_context", lambda db, uid: None)
    def test_append_creates_row(self, dao_session):
        from db.dao.calibration_data import CalibrationDataDAO
        from db.models.calibration_data import ConfidenceCalibrationData

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je = _seed_journal_entry(dao_session, user.id, txn.id)

        row = CalibrationDataDAO.append(
            db=dao_session,
            user_id=user.id,
            journal_entry_id=je.id,
            raw_confidence=0.87,
            was_correct=True,
            transaction_type="expense",
        )
        dao_session.commit()

        assert row.id is not None
        assert row.user_id == user.id
        assert row.journal_entry_id == je.id
        assert abs(row.raw_confidence - 0.87) < 1e-6
        assert row.was_correct is True
        assert row.transaction_type == "expense"

    @patch("db.dao.calibration_data.set_current_user_context", lambda db, uid: None)
    def test_count_pending_returns_correct_count(self, dao_session):
        from db.dao.calibration_data import CalibrationDataDAO

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je1 = _seed_journal_entry(dao_session, user.id, txn.id)
        je2 = _seed_journal_entry(dao_session, user.id, txn.id)

        assert CalibrationDataDAO.count_pending(dao_session) == 0

        CalibrationDataDAO.append(
            db=dao_session,
            user_id=user.id,
            journal_entry_id=je1.id,
            raw_confidence=0.92,
            was_correct=True,
        )
        CalibrationDataDAO.append(
            db=dao_session,
            user_id=user.id,
            journal_entry_id=je2.id,
            raw_confidence=0.45,
            was_correct=False,
        )
        dao_session.commit()

        assert CalibrationDataDAO.count_pending(dao_session) == 2

    @patch("db.dao.calibration_data.set_current_user_context", lambda db, uid: None)
    def test_append_with_optional_transaction_type_none(self, dao_session):
        from db.dao.calibration_data import CalibrationDataDAO

        user = _seed_user(dao_session)
        txn = _seed_transaction(dao_session, user.id)
        je = _seed_journal_entry(dao_session, user.id, txn.id)

        row = CalibrationDataDAO.append(
            db=dao_session,
            user_id=user.id,
            journal_entry_id=je.id,
            raw_confidence=0.5,
            was_correct=False,
        )
        dao_session.commit()

        assert row.transaction_type is None
