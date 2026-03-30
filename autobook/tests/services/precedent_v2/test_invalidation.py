"""Tests for services/precedent_v2/invalidation.py — event-driven invalidation.

Covers:
- on_coa_change delegates to PrecedentDAO.invalidate_by_accounts
- on_tax_change delegates to PrecedentDAO.invalidate_by_accounts
- Both return the count from the DAO
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from services.precedent_v2.invalidation import on_coa_change, on_tax_change

USER_ID = uuid.uuid4()


class TestOnCoaChange:
    def test_delegates_to_dao(self):
        mock_db = MagicMock()
        account_codes = ["5200", "1000"]

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=3,
        ) as mock_invalidate:
            result = on_coa_change(mock_db, USER_ID, account_codes)

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, account_codes)
        assert result == 3

    def test_returns_zero_when_nothing_invalidated(self):
        mock_db = MagicMock()

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=0,
        ) as mock_invalidate:
            result = on_coa_change(mock_db, USER_ID, ["9999"])

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, ["9999"])
        assert result == 0

    def test_passes_empty_list(self):
        mock_db = MagicMock()

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=0,
        ) as mock_invalidate:
            result = on_coa_change(mock_db, USER_ID, [])

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, [])
        assert result == 0


class TestOnTaxChange:
    def test_delegates_to_dao(self):
        mock_db = MagicMock()
        tax_codes = ["HST", "GST"]

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=5,
        ) as mock_invalidate:
            result = on_tax_change(mock_db, USER_ID, tax_codes)

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, tax_codes)
        assert result == 5

    def test_returns_zero_when_nothing_invalidated(self):
        mock_db = MagicMock()

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=0,
        ) as mock_invalidate:
            result = on_tax_change(mock_db, USER_ID, ["NONEXISTENT"])

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, ["NONEXISTENT"])
        assert result == 0

    def test_passes_single_tax_code(self):
        mock_db = MagicMock()

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=2,
        ) as mock_invalidate:
            result = on_tax_change(mock_db, USER_ID, ["HST"])

        mock_invalidate.assert_called_once_with(mock_db, USER_ID, ["HST"])
        assert result == 2


class TestBothFunctionsShareDaoMethod:
    """Verify both on_coa_change and on_tax_change use the same DAO method."""

    def test_same_underlying_call(self):
        mock_db = MagicMock()

        with patch(
            "services.precedent_v2.invalidation.PrecedentDAO.invalidate_by_accounts",
            return_value=1,
        ) as mock_invalidate:
            on_coa_change(mock_db, USER_ID, ["5200"])
            on_tax_change(mock_db, USER_ID, ["HST"])

        assert mock_invalidate.call_count == 2
        # Both calls go through the same DAO method
        calls = mock_invalidate.call_args_list
        assert calls[0].args == (mock_db, USER_ID, ["5200"])
        assert calls[1].args == (mock_db, USER_ID, ["HST"])
