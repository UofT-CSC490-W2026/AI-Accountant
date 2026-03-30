"""Tests for V3 agent prompt builders.

Covers: complexity_detector, tax_specialist, decision_maker, entry_drafter, shared.

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
    complexity_detector,
    tax_specialist,
    decision_maker,
    entry_drafter,
    shared,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    """Minimal PipelineState dict covering all V3 prompt builders' needs."""
    state = {
        "transaction_text": "Paid monthly rent $2,000",
        "user_context": {
            "business_type": "general",
            "province": "ON",
            "ownership": "corporation",
        },
        "ml_enrichment": None,
        "iteration": 0,
        # V3 agent outputs
        "output_ambiguity_detector": [{"ambiguities": []}],
        "output_complexity_detector": [{"flags": [{"aspect": "rent", "skeptical": False}]}],
        "output_tax_specialist": [{
            "reasoning": "No tax mentioned",
            "tax_mentioned": False,
            "taxable": True,
            "add_tax_lines": False,
            "tax_rate": None,
            "tax_amount": None,
            "treatment": "not_applicable",
        }],
        "output_decision_maker": None,
        "output_entry_drafter": None,
        # Legacy classifier outputs needed by decision_maker and entry_drafter
        "output_debit_classifier": [{
            "asset_increase": [],
            "dividend_increase": [],
            "expense_increase": [{"reason": "rent expense", "category": "Occupancy expense", "count": 1}],
            "liability_decrease": [],
            "equity_decrease": [],
            "revenue_decrease": [],
        }],
        "output_credit_classifier": [{
            "liability_increase": [],
            "equity_increase": [],
            "revenue_increase": [],
            "asset_decrease": [{"reason": "cash payment", "category": "Cash and cash equivalents", "count": 1}],
            "dividend_decrease": [],
            "expense_decrease": [],
        }],
    }
    state.update(overrides)
    return state


def _assert_prompt_structure(result):
    """Common assertions for all prompt builders."""
    assert isinstance(result, list), "build_prompt must return a list"
    assert len(result) == 2, "build_prompt must return exactly 2 messages"
    assert result[0].type == "system"
    assert result[1].type == "human"
    assert isinstance(result[0].content, list)
    assert any("text" in block for block in result[0].content if isinstance(block, dict))
    assert isinstance(result[1].content, list)
    assert any("text" in block for block in result[1].content if isinstance(block, dict))


def _extract_system_text(result) -> str:
    """Concatenate all text blocks from the system message."""
    return " ".join(
        block["text"] for block in result[0].content
        if isinstance(block, dict) and "text" in block
    )


def _extract_human_text(result) -> str:
    """Concatenate all text blocks from the human message."""
    return " ".join(
        block["text"] for block in result[1].content
        if isinstance(block, dict) and "text" in block
    )


# ---------------------------------------------------------------------------
# Tests — shared.py
# ---------------------------------------------------------------------------

class TestSharedPromptComponents:
    """Tests for shared prompt constants used by all V3 agents."""

    def test_shared_instruction_contains_ifrs(self):
        assert "IFRS" in shared.SHARED_INSTRUCTION

    def test_shared_instruction_contains_double_entry(self):
        assert "double-entry" in shared.SHARED_INSTRUCTION.lower() or "Double-entry" in shared.SHARED_INSTRUCTION

    def test_shared_instruction_contains_debit_credit_rules(self):
        si = shared.SHARED_INSTRUCTION
        assert "Debit increases" in si
        assert "Credit increases" in si

    def test_shared_preamble_mentions_bookkeeping(self):
        assert "bookkeeping" in shared.SHARED_PREAMBLE.lower()

    def test_shared_domain_contains_tax_categories(self):
        assert "Taxable" in shared.SHARED_DOMAIN
        assert "Not taxable" in shared.SHARED_DOMAIN

    def test_shared_domain_contains_conventional_terms(self):
        assert "Conventional terms" in shared.SHARED_DOMAIN

    def test_shared_domain_contains_calculation_conventions(self):
        assert "actual/365" in shared.SHARED_DOMAIN

    def test_shared_domain_contains_ifrs_taxonomy(self):
        assert "IFRS taxonomy categories" in shared.SHARED_DOMAIN

    def test_shared_system_contains_pipeline_architecture(self):
        assert "Pipeline architecture" in shared.SHARED_SYSTEM

    def test_shared_system_contains_slot_definitions(self):
        si = shared.SHARED_SYSTEM
        assert "asset_increase" in si
        assert "liability_increase" in si

    def test_shared_instruction_is_combination_of_parts(self):
        expected = "\n".join([shared.SHARED_PREAMBLE, shared.SHARED_DOMAIN, shared.SHARED_SYSTEM])
        assert shared.SHARED_INSTRUCTION == expected

    def test_shared_domain_contains_source_of_truth(self):
        assert "Source of truth" in shared.SHARED_DOMAIN

    def test_shared_domain_mentions_ias_38(self):
        assert "IAS 38" in shared.SHARED_DOMAIN

    def test_shared_domain_mentions_ias_16(self):
        assert "IAS 16" in shared.SHARED_DOMAIN


# ---------------------------------------------------------------------------
# Tests — CACHE_POINT (from utils/prompt/helpers.py, imported by all agents)
# ---------------------------------------------------------------------------

class TestCachePoint:
    """Tests for the CACHE_POINT constant used in prompt system blocks."""

    def test_cache_point_has_correct_structure(self):
        from services.agent.utils.prompt import CACHE_POINT
        assert "cachePoint" in CACHE_POINT
        assert "type" in CACHE_POINT["cachePoint"]
        assert CACHE_POINT["cachePoint"]["type"] == "default"

    def test_cache_point_has_ttl(self):
        from services.agent.utils.prompt import CACHE_POINT
        assert "ttl" in CACHE_POINT["cachePoint"]


# ---------------------------------------------------------------------------
# Tests — complexity_detector
# ---------------------------------------------------------------------------

class TestComplexityDetectorPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        _assert_prompt_structure(result)

    def test_build_prompt_with_rag_examples_none(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state, rag_examples=None)
        _assert_prompt_structure(result)

    def test_build_prompt_with_empty_rag_examples(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_system_instruction_contains_complexity_role(self):
        si = complexity_detector.SYSTEM_INSTRUCTION.lower()
        assert "complex" in si

    def test_system_instruction_mentions_ifrs(self):
        assert "IFRS" in complexity_detector.SYSTEM_INSTRUCTION

    def test_system_instruction_mentions_knowledge_gap(self):
        si = complexity_detector.SYSTEM_INSTRUCTION.lower()
        assert "knowledge" in si

    def test_agent_instruction_contains_role(self):
        assert "## Role" in complexity_detector.AGENT_INSTRUCTION

    def test_agent_instruction_contains_procedure(self):
        assert "## Procedure" in complexity_detector.AGENT_INSTRUCTION

    def test_agent_instruction_contains_examples(self):
        assert "## Examples" in complexity_detector.AGENT_INSTRUCTION

    def test_system_instruction_is_shared_plus_agent(self):
        expected = "\n".join([shared.SHARED_INSTRUCTION, complexity_detector.AGENT_INSTRUCTION])
        assert complexity_detector.SYSTEM_INSTRUCTION == expected

    def test_system_blocks_contain_shared_and_agent_instruction(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        sys_text = _extract_system_text(result)
        assert shared.SHARED_PREAMBLE in sys_text
        assert "## Role" in sys_text

    def test_human_message_contains_transaction(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<transaction>" in human_text
        assert "Paid monthly rent $2,000" in human_text

    def test_human_message_contains_user_context(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<context>" in human_text
        assert "general" in human_text

    def test_human_message_contains_task_reminder(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "## Task" in human_text
        assert "complexity" in human_text.lower()

    def test_system_blocks_contain_cache_points(self):
        state = _base_state()
        result = complexity_detector.build_prompt(state)
        cache_points = [
            block for block in result[0].content
            if isinstance(block, dict) and "cachePoint" in block
        ]
        assert len(cache_points) == 2

    def test_role_excludes_entry_building(self):
        assert "Build entries" in complexity_detector._ROLE
        assert "You do NOT" in complexity_detector._ROLE


# ---------------------------------------------------------------------------
# Tests — tax_specialist
# ---------------------------------------------------------------------------

class TestTaxSpecialistPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        _assert_prompt_structure(result)

    def test_build_prompt_with_rag_examples_none(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state, rag_examples=None)
        _assert_prompt_structure(result)

    def test_build_prompt_with_empty_rag_examples(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state, rag_examples=[])
        _assert_prompt_structure(result)

    def test_system_instruction_contains_tax_role(self):
        si = tax_specialist.SYSTEM_INSTRUCTION.lower()
        assert "tax" in si

    def test_system_instruction_mentions_entry_drafter(self):
        si = tax_specialist.SYSTEM_INSTRUCTION.lower()
        assert "entry drafter" in si

    def test_agent_instruction_contains_role(self):
        assert "## Role" in tax_specialist.AGENT_INSTRUCTION

    def test_agent_instruction_contains_procedure(self):
        assert "## Procedure" in tax_specialist.AGENT_INSTRUCTION

    def test_agent_instruction_contains_examples(self):
        assert "## Examples" in tax_specialist.AGENT_INSTRUCTION

    def test_system_instruction_is_shared_plus_agent(self):
        expected = "\n".join([shared.SHARED_INSTRUCTION, tax_specialist.AGENT_INSTRUCTION])
        assert tax_specialist.SYSTEM_INSTRUCTION == expected

    def test_system_blocks_contain_shared_and_agent_instruction(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        sys_text = _extract_system_text(result)
        assert shared.SHARED_PREAMBLE in sys_text
        assert "tax" in sys_text.lower()

    def test_human_message_contains_transaction(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<transaction>" in human_text
        assert "Paid monthly rent $2,000" in human_text

    def test_human_message_contains_user_context(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<context>" in human_text

    def test_human_message_contains_task_reminder(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "## Task" in human_text
        assert "tax" in human_text.lower()

    def test_system_blocks_contain_cache_points(self):
        state = _base_state()
        result = tax_specialist.build_prompt(state)
        cache_points = [
            block for block in result[0].content
            if isinstance(block, dict) and "cachePoint" in block
        ]
        assert len(cache_points) == 2

    def test_procedure_mentions_tax_mentioned_logic(self):
        assert "tax_mentioned" in tax_specialist._PROCEDURE

    def test_procedure_mentions_add_tax_lines_logic(self):
        assert "add_tax_lines" in tax_specialist._PROCEDURE

    def test_procedure_mentions_recoverable(self):
        assert "recoverable" in tax_specialist._PROCEDURE

    def test_examples_include_taxable_and_non_taxable(self):
        examples = tax_specialist._EXAMPLES
        assert "tax_mentioned\": true" in examples
        assert "tax_mentioned\": false" in examples

    def test_role_excludes_journal_entry_building(self):
        assert "Build the journal entry" in tax_specialist._ROLE
        assert "You do NOT" in tax_specialist._ROLE


# ---------------------------------------------------------------------------
# Tests — decision_maker
# ---------------------------------------------------------------------------

class TestDecisionMakerPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        _assert_prompt_structure(result)

    def test_build_prompt_no_rag_parameter(self):
        """decision_maker.build_prompt(state) has no rag_examples parameter."""
        state = _base_state()
        # Should work with just state
        result = decision_maker.build_prompt(state)
        _assert_prompt_structure(result)

    def test_system_instruction_contains_decision_role(self):
        si = decision_maker.SYSTEM_INSTRUCTION.lower()
        assert "decision" in si or "decide" in si

    def test_system_instruction_mentions_proceed(self):
        assert "proceed" in decision_maker.SYSTEM_INSTRUCTION

    def test_system_instruction_mentions_missing_info(self):
        assert "missing_info" in decision_maker.SYSTEM_INSTRUCTION

    def test_system_instruction_mentions_llm_stuck(self):
        assert "llm_stuck" in decision_maker.SYSTEM_INSTRUCTION

    def test_agent_instruction_contains_role(self):
        assert "## Role" in decision_maker.AGENT_INSTRUCTION

    def test_agent_instruction_contains_procedure(self):
        assert "## Procedure" in decision_maker.AGENT_INSTRUCTION

    def test_agent_instruction_contains_examples(self):
        assert "## Examples" in decision_maker.AGENT_INSTRUCTION

    def test_agent_instruction_contains_decision_criteria(self):
        assert "## Decision Criteria" in decision_maker.AGENT_INSTRUCTION

    def test_agent_instruction_contains_input_format(self):
        assert "## Input Format" in decision_maker.AGENT_INSTRUCTION

    def test_system_instruction_is_shared_plus_agent(self):
        expected = "\n".join([shared.SHARED_INSTRUCTION, decision_maker.AGENT_INSTRUCTION])
        assert decision_maker.SYSTEM_INSTRUCTION == expected

    def test_human_message_contains_transaction(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<transaction>" in human_text
        assert "Paid monthly rent $2,000" in human_text

    def test_human_message_contains_user_context(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<context>" in human_text

    def test_human_message_contains_task_reminder(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "## Task" in human_text

    def test_system_blocks_contain_cache_points(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        cache_points = [
            block for block in result[0].content
            if isinstance(block, dict) and "cachePoint" in block
        ]
        assert len(cache_points) == 2

    def test_upstream_ambiguity_included(self):
        state = _base_state(
            output_ambiguity_detector=[{"ambiguities": [{"aspect": "purpose", "resolved": False}]}]
        )
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<ambiguity_detector>" in human_text
        assert "purpose" in human_text

    def test_upstream_complexity_included(self):
        state = _base_state(
            output_complexity_detector=[{"flags": [{"aspect": "bond split", "skeptical": True}]}]
        )
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<complexity_detector>" in human_text
        assert "bond split" in human_text

    def test_upstream_debit_classifier_included(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<debit_classifier>" in human_text

    def test_upstream_credit_classifier_included(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<credit_classifier>" in human_text

    def test_upstream_tax_specialist_included(self):
        state = _base_state()
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<tax_specialist>" in human_text

    def test_no_upstream_when_all_none(self):
        state = _base_state(
            output_ambiguity_detector=[None],
            output_complexity_detector=[None],
            output_debit_classifier=[None],
            output_credit_classifier=[None],
            output_tax_specialist=[None],
        )
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<ambiguity_detector>" not in human_text
        assert "<complexity_detector>" not in human_text
        assert "<debit_classifier>" not in human_text
        assert "<credit_classifier>" not in human_text
        assert "<tax_specialist>" not in human_text

    def test_no_upstream_when_lists_empty(self):
        state = _base_state(
            output_ambiguity_detector=[],
            output_complexity_detector=[],
            output_debit_classifier=[],
            output_credit_classifier=[],
            output_tax_specialist=[],
        )
        # Empty lists: ([] or [None])[-1] would fail on empty, so
        # the code uses (state.get(...) or [None])[-1], and [] is falsy,
        # so it falls back to [None][-1] = None
        result = decision_maker.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<ambiguity_detector>" not in human_text

    def test_role_mentions_override_classifications(self):
        assert "override" in decision_maker._ROLE.lower()

    def test_procedure_reviews_ambiguity_and_complexity(self):
        proc = decision_maker._PROCEDURE
        assert "ambiguity" in proc.lower()
        assert "complexity" in proc.lower()

    def test_examples_cover_all_decisions(self):
        examples = decision_maker._EXAMPLES
        assert "missing_info" in examples
        assert "llm_stuck" in examples
        assert "proceed" in examples


# ---------------------------------------------------------------------------
# Tests — entry_drafter
# ---------------------------------------------------------------------------

class TestEntryDrafterPrompt:
    def test_build_prompt_returns_two_messages(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        _assert_prompt_structure(result)

    def test_build_prompt_with_explicit_tax_output(self):
        state = _base_state()
        tax = {
            "reasoning": "10% on supplies",
            "tax_mentioned": True,
            "taxable": True,
            "add_tax_lines": True,
            "tax_rate": 0.10,
            "tax_amount": 50.0,
            "treatment": "recoverable",
        }
        result = entry_drafter.build_prompt(state, tax_output=tax)
        _assert_prompt_structure(result)
        human_text = _extract_human_text(result)
        assert "<tax_context>" in human_text
        assert "recoverable" in human_text

    def test_build_prompt_with_tax_output_none_falls_back_to_state(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state, tax_output=None)
        _assert_prompt_structure(result)
        human_text = _extract_human_text(result)
        # State has tax output with treatment = not_applicable,
        # so tax_context should appear
        assert "<tax_context>" in human_text

    def test_build_prompt_without_any_tax_output(self):
        state = _base_state(output_tax_specialist=[None])
        result = entry_drafter.build_prompt(state, tax_output=None)
        _assert_prompt_structure(result)
        human_text = _extract_human_text(result)
        assert "<tax_context>" not in human_text

    def test_system_instruction_contains_entry_role(self):
        si = entry_drafter.SYSTEM_INSTRUCTION.lower()
        assert "journal entry" in si

    def test_system_instruction_mentions_double_entry(self):
        si = entry_drafter.SYSTEM_INSTRUCTION.lower()
        assert "double-entry" in si

    def test_agent_instruction_contains_role(self):
        assert "## Role" in entry_drafter.AGENT_INSTRUCTION

    def test_agent_instruction_contains_procedure(self):
        assert "## Procedure" in entry_drafter.AGENT_INSTRUCTION

    def test_agent_instruction_contains_examples(self):
        assert "## Examples" in entry_drafter.AGENT_INSTRUCTION

    def test_agent_instruction_contains_input_format(self):
        assert "## Input Format" in entry_drafter.AGENT_INSTRUCTION

    def test_system_instruction_is_shared_plus_agent(self):
        expected = "\n".join([shared.SHARED_INSTRUCTION, entry_drafter.AGENT_INSTRUCTION])
        assert entry_drafter.SYSTEM_INSTRUCTION == expected

    def test_human_message_contains_transaction(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<transaction>" in human_text
        assert "Paid monthly rent $2,000" in human_text

    def test_human_message_contains_user_context(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<context>" in human_text

    def test_human_message_contains_task_reminder(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "## Task" in human_text
        assert "journal entry" in human_text.lower()

    def test_system_blocks_contain_cache_points(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        cache_points = [
            block for block in result[0].content
            if isinstance(block, dict) and "cachePoint" in block
        ]
        assert len(cache_points) == 2

    def test_human_message_contains_debit_classification(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<debit_classification>" in human_text

    def test_human_message_contains_credit_classification(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "<credit_classification>" in human_text

    def test_classified_lines_extracted_from_state(self):
        state = _base_state()
        result = entry_drafter.build_prompt(state)
        human_text = _extract_human_text(result)
        assert "Occupancy expense" in human_text
        assert "Cash and cash equivalents" in human_text

    def test_role_trusts_upstream(self):
        assert "Trust" in entry_drafter._ROLE
        assert "do not" in entry_drafter._ROLE.lower() or "do NOT" in entry_drafter._ROLE

    def test_procedure_mentions_debits_equal_credits(self):
        assert "debits = total credits" in entry_drafter._PROCEDURE

    def test_procedure_mentions_tax_lines(self):
        assert "tax_lines" in entry_drafter._PROCEDURE or "tax lines" in entry_drafter._PROCEDURE


class TestEntryDrafterExtractClassifiedLines:
    """Tests for _extract_classified_lines helper in entry_drafter."""

    def test_extracts_debit_lines_from_classifier_output(self):
        state = _base_state()
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        assert "expense_increase" in debit_lines
        assert len(debit_lines["expense_increase"]) == 1

    def test_extracts_credit_lines_from_classifier_output(self):
        state = _base_state()
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        assert "asset_decrease" in credit_lines
        assert len(credit_lines["asset_decrease"]) == 1

    def test_empty_slots_default_to_empty_lists(self):
        state = _base_state()
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        assert debit_lines["asset_increase"] == []
        assert debit_lines["dividend_increase"] == []
        assert credit_lines["liability_increase"] == []

    def test_handles_missing_classifier_output(self):
        state = _base_state(
            output_debit_classifier=[None],
            output_credit_classifier=[None],
        )
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        # All slots should be empty lists
        for slot in debit_lines.values():
            assert slot == []
        for slot in credit_lines.values():
            assert slot == []

    def test_decision_maker_override_debit(self):
        state = _base_state(
            output_decision_maker=[{
                "override_debit": [
                    {"reason": "corrected", "category": "Land", "count": 1},
                ],
            }],
        )
        debit_lines, _ = entry_drafter._extract_classified_lines(state)
        # Override replaces all debit lines
        assert len(debit_lines["asset_increase"]) == 1
        assert debit_lines["asset_increase"][0]["category"] == "Land"
        # Original expense_increase should be cleared
        assert debit_lines["expense_increase"] == []

    def test_decision_maker_override_credit(self):
        state = _base_state(
            output_decision_maker=[{
                "override_credit": [
                    {"reason": "corrected", "category": "Trade payables", "count": 1},
                ],
            }],
        )
        _, credit_lines = entry_drafter._extract_classified_lines(state)
        assert len(credit_lines["liability_increase"]) == 1
        assert credit_lines["liability_increase"][0]["category"] == "Trade payables"
        # Original asset_decrease should be cleared
        assert credit_lines["asset_decrease"] == []

    def test_no_decision_maker_override(self):
        state = _base_state(output_decision_maker=[None])
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        # Original lines preserved
        assert len(debit_lines["expense_increase"]) == 1
        assert len(credit_lines["asset_decrease"]) == 1

    def test_decision_maker_without_overrides(self):
        state = _base_state(
            output_decision_maker=[{
                "decision": "proceed",
                # No override_debit or override_credit keys
            }],
        )
        debit_lines, credit_lines = entry_drafter._extract_classified_lines(state)
        # Original lines preserved when overrides are absent
        assert len(debit_lines["expense_increase"]) == 1
        assert len(credit_lines["asset_decrease"]) == 1
