"""Tests for all 8 prompt builders in services/agent/prompts/.

Each build_prompt() returns [SystemMessage, HumanMessage] via to_bedrock_messages().
We mock langchain_core.messages so the test env doesn't need langchain installed.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock langchain_core and langchain_aws before any prompt module is imported
# ---------------------------------------------------------------------------

_mock_lc_core = ModuleType("langchain_core")
_mock_lc_messages = ModuleType("langchain_core.messages")
_mock_lc_runnables = ModuleType("langchain_core.runnables")
_mock_lc_aws = ModuleType("langchain_aws")


class _FakeSystemMessage:
    def __init__(self, content):
        self.content = content
        self.type = "system"


class _FakeHumanMessage:
    def __init__(self, content):
        self.content = content
        self.type = "human"


_mock_lc_messages.SystemMessage = _FakeSystemMessage
_mock_lc_messages.HumanMessage = _FakeHumanMessage
_mock_lc_core.messages = _mock_lc_messages
_mock_lc_runnables.RunnableConfig = dict
_mock_lc_core.runnables = _mock_lc_runnables
_mock_lc_aws.ChatBedrockConverse = MagicMock

sys.modules.setdefault("langchain_core", _mock_lc_core)
sys.modules.setdefault("langchain_core.messages", _mock_lc_messages)
sys.modules.setdefault("langchain_core.runnables", _mock_lc_runnables)
sys.modules.setdefault("langchain_aws", _mock_lc_aws)

# Now import the prompt modules (safe since langchain_core is stubbed)
from services.agent.prompts import (
    disambiguator,
    debit_classifier,
    credit_classifier,
    debit_corrector,
    credit_corrector,
    entry_builder,
    approver,
    diagnostician,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    """Minimal PipelineState dict covering all prompt builders' needs."""
    state = {
        "transaction_text": "Paid monthly rent $2,000",
        "user_context": {
            "business_type": "general",
            "province": "ON",
            "ownership": "corporation",
        },
        "ml_enrichment": None,
        "iteration": 0,
        "output_disambiguator": [{"ambiguities": []}],
        "output_debit_classifier": [{"tuple": [0, 0, 1, 0, 0, 0], "reason": "expense"}],
        "output_credit_classifier": [{"tuple": [0, 0, 0, 1, 0, 0], "reason": "asset decrease"}],
        "output_debit_corrector": [{"tuple": [0, 0, 1, 0, 0, 0], "reason": "no change"}],
        "output_credit_corrector": [{"tuple": [0, 0, 0, 1, 0, 0], "reason": "no change"}],
        "output_entry_builder": [{
            "date": "2026-03-22",
            "description": "Monthly rent payment",
            "rationale": "Rent is operating expense",
            "lines": [
                {"account_name": "Rent Expense", "type": "debit", "amount": 2000.00},
                {"account_name": "Cash", "type": "credit", "amount": 2000.00},
            ],
        }],
        "output_approver": [{
            "decision": "REJECTED",
            "confidence": "VERY_CONFIDENT",
            "reason": "Missing HST lines",
        }],
        "output_diagnostician": [],
    }
    state.update(overrides)
    return state


def _assert_prompt_structure(result):
    """Common assertions for all prompt builders."""
    assert isinstance(result, list), "build_prompt must return a list"
    assert len(result) == 2, "build_prompt must return exactly 2 messages"
    assert result[0].type == "system"
    assert result[1].type == "human"
    # System message content should include text blocks
    assert isinstance(result[0].content, list)
    assert any("text" in block for block in result[0].content if isinstance(block, dict))
    # Human message content should include text blocks
    assert isinstance(result[1].content, list)
    assert any("text" in block for block in result[1].content if isinstance(block, dict))


# ---------------------------------------------------------------------------
# Tests — one per prompt builder
# ---------------------------------------------------------------------------

class TestDisambiguatorPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = disambiguator.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_with_fix_context(self):
        state = _base_state()
        result = disambiguator.build_prompt(
            state, rag_examples=[], fix_context="Fix the ambiguity analysis"
        )
        _assert_prompt_structure(result)
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "fix_context" in human_text.lower() or "Fix" in human_text

    def test_build_prompt_with_rag_examples(self):
        state = _base_state()
        examples = [{"input": "test tx", "output": "test output"}]
        result = disambiguator.build_prompt(state, rag_examples=examples)
        _assert_prompt_structure(result)
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "examples" in human_text.lower()

    def test_system_instruction_contains_preamble(self):
        assert "business context expert" in disambiguator.SYSTEM_INSTRUCTION


class TestDebitClassifierPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = debit_classifier.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_system_instruction_mentions_debit(self):
        assert "DEBIT" in debit_classifier.SYSTEM_INSTRUCTION

    def test_build_prompt_with_rag(self):
        state = _base_state()
        examples = [{"transaction": "test", "debit_tuple": [1, 0, 0, 0, 0, 0]}]
        result = debit_classifier.build_prompt(state, rag_examples=examples)
        _assert_prompt_structure(result)


class TestCreditClassifierPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = credit_classifier.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_system_instruction_mentions_credit(self):
        assert "CREDIT" in credit_classifier.SYSTEM_INSTRUCTION


class TestDebitCorrectorPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = debit_corrector.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_includes_tuples_in_human_message(self):
        state = _base_state()
        result = debit_corrector.build_prompt(state, rag_examples=[])
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "initial_debit_tuple" in human_text

    def test_system_instruction_mentions_review(self):
        assert "Review" in debit_corrector.SYSTEM_INSTRUCTION or "review" in debit_corrector.SYSTEM_INSTRUCTION


class TestCreditCorrectorPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = credit_corrector.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_includes_credit_tuple(self):
        state = _base_state()
        result = credit_corrector.build_prompt(state, rag_examples=[])
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "initial_credit_tuple" in human_text


class TestEntryBuilderPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = entry_builder.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_disambiguator_off(self):
        state = _base_state()
        result = entry_builder.build_prompt(
            state, rag_examples=[], pipeline_config={"disambiguator_active": False}
        )
        _assert_prompt_structure(result)

    def test_build_prompt_evaluation_off_adds_decision(self):
        state = _base_state()
        result = entry_builder.build_prompt(
            state, rag_examples=[], pipeline_config={"evaluation_active": False}
        )
        _assert_prompt_structure(result)
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "APPROVED" in human_text or "STUCK" in human_text

    def test_build_prompt_with_coa_tax_vendor(self):
        state = _base_state()
        coa = [{"account_code": "5000", "account_name": "Rent Expense", "account_type": "expense"}]
        tax = {"rate": 0.13, "taxable": True}
        vendor = [{"account_name": "Rent Expense", "type": "debit", "amount": "2000"}]
        result = entry_builder.build_prompt(
            state, rag_examples=[], coa_results=coa, tax_results=tax, vendor_results=vendor,
        )
        _assert_prompt_structure(result)
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "chart_of_accounts" in human_text
        assert "tax_rules" in human_text
        assert "vendor_history" in human_text


class TestApproverPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = approver.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_includes_journal_entry(self):
        state = _base_state()
        result = approver.build_prompt(state, rag_examples=[])
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "journal_entry" in human_text

    def test_system_instruction_mentions_auditor(self):
        assert "auditor" in approver.SYSTEM_INSTRUCTION


class TestDiagnosticianPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = diagnostician.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_build_prompt_includes_rejection(self):
        state = _base_state()
        result = diagnostician.build_prompt(state, rag_examples=[])
        human_text = " ".join(
            block["text"] for block in result[1].content if isinstance(block, dict) and "text" in block
        )
        assert "rejection" in human_text

    def test_system_instruction_mentions_debugging(self):
        assert "debugging" in diagnostician.SYSTEM_INSTRUCTION or "Debugging" in diagnostician.SYSTEM_INSTRUCTION

    def test_build_prompt_with_fix_context(self):
        state = _base_state()
        result = diagnostician.build_prompt(
            state, rag_examples=[], fix_context="Previous fix failed"
        )
        _assert_prompt_structure(result)
