from __future__ import annotations

from services.agent.graph.state import COMPLETE
from services.agent.nodes.non_llm.passthrough import corrector_passthrough_node


def _make_state(
    iteration: int = 0,
    debit_output=None,
    credit_output=None,
    existing_debit_corrector: list | None = None,
    existing_credit_corrector: list | None = None,
) -> dict:
    """Build a minimal state for corrector_passthrough_node."""
    debit_classifier_outputs = [None] * (iteration + 1)
    credit_classifier_outputs = [None] * (iteration + 1)
    debit_classifier_outputs[iteration] = debit_output or {"reason": "test", "tuple": (0, 0, 1, 0, 0, 0)}
    credit_classifier_outputs[iteration] = credit_output or {"reason": "test", "tuple": (0, 0, 0, 1, 0, 0)}

    return {
        "iteration": iteration,
        "output_debit_classifier": debit_classifier_outputs,
        "output_credit_classifier": credit_classifier_outputs,
        "output_debit_corrector": existing_debit_corrector or [],
        "output_credit_corrector": existing_credit_corrector or [],
    }


class TestCorrectorPassthroughNode:
    def test_copies_classifier_to_corrector(self):
        debit = {"reason": "expense", "tuple": (0, 0, 1, 0, 0, 0)}
        credit = {"reason": "asset decrease", "tuple": (0, 0, 0, 1, 0, 0)}
        state = _make_state(debit_output=debit, credit_output=credit)
        result = corrector_passthrough_node(state)
        assert result["output_debit_corrector"] == [debit]
        assert result["output_credit_corrector"] == [credit]

    def test_sets_complete_status(self):
        result = corrector_passthrough_node(_make_state())
        assert result["status_debit_corrector"] == COMPLETE
        assert result["status_credit_corrector"] == COMPLETE

    def test_appends_to_existing_history(self):
        """On iteration 1, appends to the existing corrector outputs from iteration 0."""
        prev_debit = {"reason": "prev", "tuple": (1, 0, 0, 0, 0, 0)}
        prev_credit = {"reason": "prev", "tuple": (0, 1, 0, 0, 0, 0)}
        new_debit = {"reason": "new", "tuple": (0, 0, 1, 0, 0, 0)}
        new_credit = {"reason": "new", "tuple": (0, 0, 0, 1, 0, 0)}

        state = _make_state(
            iteration=1,
            debit_output=new_debit,
            credit_output=new_credit,
            existing_debit_corrector=[prev_debit],
            existing_credit_corrector=[prev_credit],
        )
        result = corrector_passthrough_node(state)
        assert result["output_debit_corrector"] == [prev_debit, new_debit]
        assert result["output_credit_corrector"] == [prev_credit, new_credit]

    def test_returns_dict_with_four_keys(self):
        result = corrector_passthrough_node(_make_state())
        assert set(result.keys()) == {
            "output_debit_corrector",
            "output_credit_corrector",
            "status_debit_corrector",
            "status_credit_corrector",
        }
