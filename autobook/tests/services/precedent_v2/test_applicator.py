"""Tests for entry construction — apply label with tax recomputation."""
from services.precedent_v2.applicator import apply_label, _round_money
from services.precedent_v2.models import Label, StructureLine, RatioLine

from decimal import Decimal


def _rent_label() -> Label:
    return Label(
        structure=(
            StructureLine("5200", "debit"),
            StructureLine("1000", "credit"),
        ),
        ratio=(
            RatioLine("5200", 1.0),
            RatioLine("1000", 1.0),
        ),
        structure_hash="abc123",
    )


def _rent_with_tax_label() -> Label:
    return Label(
        structure=(
            StructureLine("5200", "debit"),
            StructureLine("2100", "debit"),   # HST Receivable (tax line)
            StructureLine("1000", "credit"),
        ),
        ratio=(
            RatioLine("5200", 1.0),
            RatioLine("2100", 0.13),  # will be ignored — tax recomputed
            RatioLine("1000", 1.13),
        ),
        structure_hash="def456",
    )


def _split_label() -> Label:
    """Equipment purchase: $20K equipment, $5K cash, $15K loan."""
    return Label(
        structure=(
            StructureLine("1500", "debit"),
            StructureLine("1000", "credit"),
            StructureLine("2500", "credit"),
        ),
        ratio=(
            RatioLine("1500", 1.0),
            RatioLine("1000", 0.25),
            RatioLine("2500", 0.75),
        ),
        structure_hash="ghi789",
    )


class TestApplyLabel:
    def test_simple_rent(self):
        result = apply_label(_rent_label(), 2000.0, "ON")
        lines = result["lines"]
        assert len(lines) == 2
        assert lines[0]["account_code"] == "5200"
        assert lines[0]["type"] == "debit"
        assert lines[0]["amount"] == 2000.0
        assert lines[1]["account_code"] == "1000"
        assert lines[1]["type"] == "credit"
        assert lines[1]["amount"] == 2000.0

    def test_origin_tier_is_1(self):
        result = apply_label(_rent_label(), 2000.0)
        assert result["entry"]["origin_tier"] == 1

    def test_rationale_includes_hash(self):
        result = apply_label(_rent_label(), 2000.0)
        assert "abc123" in result["entry"]["rationale"]

    def test_split_amounts(self):
        result = apply_label(_split_label(), 20000.0)
        lines = result["lines"]
        assert len(lines) == 3
        amounts = {l["account_code"]: l["amount"] for l in lines}
        assert amounts["1500"] == 20000.0
        assert amounts["1000"] == 5000.0
        assert amounts["2500"] == 15000.0

    def test_tax_recomputed_ontario(self):
        result = apply_label(_rent_with_tax_label(), 2000.0, "ON")
        lines = result["lines"]
        tax_lines = [l for l in lines if l["account_code"] == "2100"]
        assert len(tax_lines) == 1
        assert tax_lines[0]["amount"] == 260.0  # 2000 * 0.13

    def test_tax_recomputed_alberta(self):
        result = apply_label(_rent_with_tax_label(), 2000.0, "AB")
        lines = result["lines"]
        tax_lines = [l for l in lines if l["account_code"] == "2100"]
        assert len(tax_lines) == 1
        assert tax_lines[0]["amount"] == 100.0  # 2000 * 0.05

    def test_no_tax_when_structure_has_none(self):
        result = apply_label(_rent_label(), 2000.0, "ON")
        tax_lines = [l for l in result["lines"] if l["account_code"] == "2100"]
        assert len(tax_lines) == 0


class TestRoundMoney:
    def test_rounds_to_cents(self):
        assert _round_money(Decimal("100.555")) == 100.56
        assert _round_money(Decimal("100.554")) == 100.55

    def test_exact_value(self):
        assert _round_money(Decimal("100.00")) == 100.0
