from __future__ import annotations

from services.agent.nodes.non_llm.validation import validation_node


def _make_state(entry: dict | None, **overrides) -> dict:
    """Build a minimal state for validation_node."""
    state = {
        "iteration": 0,
        "output_entry_builder": [entry],
        "user_context": {"province": "ON"},
    }
    state.update(overrides)
    return state


class TestValidationNodeValid:
    """Entries that should pass validation (validation_error is None)."""

    def test_balanced_entry(self):
        entry = {
            "date": "2026-01-01",
            "description": "Office supplies",
            "lines": [
                {"account_name": "Office Supplies", "type": "debit", "amount": 100.0},
                {"account_name": "Cash", "type": "credit", "amount": 100.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is None

    def test_multi_line_balanced_entry(self):
        entry = {
            "lines": [
                {"account_name": "Rent", "type": "debit", "amount": 1000.0},
                {"account_name": "HST Receivable", "type": "debit", "amount": 130.0},
                {"account_name": "Cash", "type": "credit", "amount": 1130.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is None


class TestValidationNodeInvalid:
    """Entries that should fail validation."""

    def test_unbalanced_entry(self):
        entry = {
            "lines": [
                {"account_name": "Supplies", "type": "debit", "amount": 100.0},
                {"account_name": "Cash", "type": "credit", "amount": 50.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is not None
        assert len(result["validation_error"]) > 0
        assert any("Debits" in e and "Credits" in e for e in result["validation_error"])

    def test_missing_amount_field(self):
        entry = {
            "lines": [
                {"account_name": "Supplies", "type": "debit"},
                {"account_name": "Cash", "type": "credit", "amount": 100.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is not None

    def test_negative_amount(self):
        entry = {
            "lines": [
                {"account_name": "Supplies", "type": "debit", "amount": -100.0},
                {"account_name": "Cash", "type": "credit", "amount": -100.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is not None

    def test_invalid_line_type(self):
        entry = {
            "lines": [
                {"account_name": "Supplies", "type": "DEBIT", "amount": 100.0},
                {"account_name": "Cash", "type": "credit", "amount": 100.0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is not None

    def test_empty_lines_list(self):
        entry = {"lines": []}
        result = validation_node(_make_state(entry))
        # empty lines are caught by validate_journal_entry
        # But validation_node skips validation when lines is empty
        # (no-entry case), returning None
        # Actually: "not entry.get('lines')" is True for empty list
        assert result["validation_error"] is None


class TestValidationNodeSkip:
    """Cases where validation is skipped entirely."""

    def test_none_entry_skips(self):
        result = validation_node(_make_state(None))
        assert result["validation_error"] is None

    def test_all_zero_amounts_skips(self):
        entry = {
            "lines": [
                {"account_name": "Placeholder", "type": "debit", "amount": 0},
                {"account_name": "Placeholder", "type": "credit", "amount": 0},
            ],
        }
        result = validation_node(_make_state(entry))
        assert result["validation_error"] is None

    def test_reads_correct_iteration(self):
        """Validation reads from output_entry_builder[iteration]."""
        entry_0 = {
            "lines": [
                {"account_name": "A", "type": "debit", "amount": 100.0},
                {"account_name": "B", "type": "credit", "amount": 50.0},  # unbalanced
            ],
        }
        entry_1 = {
            "lines": [
                {"account_name": "A", "type": "debit", "amount": 100.0},
                {"account_name": "B", "type": "credit", "amount": 100.0},  # balanced
            ],
        }
        state = {
            "iteration": 1,
            "output_entry_builder": [entry_0, entry_1],
            "user_context": {"province": "ON"},
        }
        result = validation_node(state)
        assert result["validation_error"] is None
