from __future__ import annotations

from services.agent.utils.prompt.helpers import (
    build_transaction,
    build_user_context,
    build_tuples,
    build_journal,
    build_coa,
    build_fix_context,
    build_rag_examples,
    build_labeled_tuples,
    build_disambiguator_opinions,
    build_tax,
    build_vendor,
    build_rejection,
    build_context_section,
    build_input_section,
)


class TestBuildTransaction:
    def test_returns_list_with_text(self):
        state = {"transaction_text": "Paid $100 for supplies"}
        result = build_transaction(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert "text" in result[0]
        assert "<transaction>Paid $100 for supplies</transaction>" == result[0]["text"]


class TestBuildUserContext:
    def test_returns_context_block(self):
        state = {"user_context": {
            "business_type": "retail",
            "province": "ON",
            "ownership": "sole proprietor",
        }}
        result = build_user_context(state)
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "retail" in text
        assert "ON" in text
        assert "sole proprietor" in text

    def test_missing_user_context_uses_defaults(self):
        state = {}
        result = build_user_context(state)
        text = result[0]["text"]
        assert "unknown" in text


class TestBuildTuples:
    def test_returns_debit_and_credit(self):
        result = build_tuples((1, 0, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0))
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "<debit_tuple>" in text
        assert "<credit_tuple>" in text


class TestBuildLabeledTuples:
    def test_returns_labeled_block(self):
        result = build_labeled_tuples((1, 0, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0))
        text = result[0]["text"]
        assert "<initial_debit_tuple>" in text
        assert "Slots:" in text


class TestBuildJournal:
    def test_returns_json_formatted(self):
        journal = {
            "date": "2026-01-01",
            "lines": [{"account_name": "Cash", "type": "debit", "amount": 100}],
        }
        result = build_journal(journal)
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "<journal_entry>" in text
        assert "Cash" in text


class TestBuildDisambiguatorOpinions:
    def test_with_ambiguities(self):
        state = {
            "output_disambiguator": [
                {"ambiguities": [{"aspect": "tax", "resolved": False}]}
            ],
        }
        result = build_disambiguator_opinions(state)
        assert len(result) == 1
        assert "advisory" in result[0]["text"].lower()

    def test_no_ambiguities_returns_no_ambiguities_message(self):
        state = {"output_disambiguator": [{"ambiguities": []}]}
        result = build_disambiguator_opinions(state)
        assert len(result) == 1
        assert "No ambiguities identified" in result[0]["text"]

    def test_empty_output_returns_empty(self):
        state = {"output_disambiguator": []}
        result = build_disambiguator_opinions(state)
        assert result == []

    def test_missing_key_returns_empty(self):
        state = {}
        result = build_disambiguator_opinions(state)
        assert result == []


class TestBuildCoa:
    def test_with_results(self):
        coa = [
            {"account_code": "1000", "account_name": "Cash", "account_type": "asset"},
            {"account_code": "5000", "account_name": "Supplies", "account_type": "expense"},
        ]
        result = build_coa(coa)
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "<chart_of_accounts>" in text
        assert "1000" in text
        assert "Cash" in text

    def test_empty_returns_empty(self):
        assert build_coa([]) == []

    def test_none_returns_empty(self):
        assert build_coa(None) == []


class TestBuildTax:
    def test_with_results(self):
        result = build_tax({"rate": 0.13, "taxable": True})
        assert len(result) == 1
        assert "rate=0.13" in result[0]["text"]

    def test_none_returns_empty(self):
        assert build_tax(None) == []

    def test_empty_dict_returns_empty(self):
        assert build_tax({}) == []


class TestBuildVendor:
    def test_with_results(self):
        vendor = [{"account_name": "Office Depot", "type": "debit", "amount": 50}]
        result = build_vendor(vendor)
        assert len(result) == 1
        assert "Office Depot" in result[0]["text"]

    def test_none_returns_empty(self):
        assert build_vendor(None) == []

    def test_empty_returns_empty(self):
        assert build_vendor([]) == []


class TestBuildRejection:
    def test_formats_approval(self):
        approval = {"decision": "REJECTED", "reason": "Debits != credits"}
        result = build_rejection(approval)
        assert len(result) == 1
        assert "<rejection>" in result[0]["text"]
        assert "REJECTED" in result[0]["text"]


class TestBuildFixContext:
    def test_with_context(self):
        result = build_fix_context("Reclassify the debit as expense")
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "<fix_context>" in text
        assert "Reclassify" in text

    def test_none_returns_empty(self):
        assert build_fix_context(None) == []

    def test_empty_string_returns_empty(self):
        assert build_fix_context("") == []


class TestBuildRagExamples:
    def test_with_examples(self):
        examples = [
            {"transaction": "Paid rent $1000", "tuple": "(0,0,1,0,0,0)"},
            {"transaction": "Bought supplies", "tuple": "(0,0,1,0,0,0)"},
        ]
        result = build_rag_examples(examples, "similar debit tuples", ["transaction", "tuple"])
        assert isinstance(result, list)
        assert len(result) == 1
        text = result[0]["text"]
        assert "similar debit tuples" in text
        assert "<examples>" in text
        assert "Paid rent $1000" in text

    def test_empty_examples_returns_empty(self):
        assert build_rag_examples([], "label", ["field"]) == []

    def test_missing_field_uses_empty_string(self):
        examples = [{"transaction": "test"}]
        result = build_rag_examples(examples, "label", ["transaction", "nonexistent"])
        text = result[0]["text"]
        assert "nonexistent: \n" in text


class TestBuildContextSection:
    def test_both_fix_and_rag(self):
        fix = [{"text": "fix stuff"}]
        rag = [{"text": "rag stuff"}]
        result = build_context_section(fix, rag)
        assert result[0]["text"] == "## Context"
        assert len(result) == 3

    def test_empty_both_returns_empty(self):
        assert build_context_section([], []) == []


class TestBuildInputSection:
    def test_wraps_blocks(self):
        block1 = [{"text": "txn data"}]
        block2 = [{"text": "tuple data"}]
        result = build_input_section(block1, block2)
        assert result[0]["text"] == "## Input"
        assert len(result) == 3
