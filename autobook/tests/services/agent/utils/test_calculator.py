"""Tests for the calculator safe-eval tool."""
from __future__ import annotations

import math
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ── Stub langchain_core.tools before import ─────────────────────────────

_lc_core = sys.modules.setdefault("langchain_core", ModuleType("langchain_core"))
_lc_tools = sys.modules.setdefault("langchain_core.tools", ModuleType("langchain_core.tools"))
_lc_tools.tool = lambda f: f  # passthrough — `calculate` becomes a plain function

# Force fresh import after stub
_MOD_KEY = "services.agent.utils.calculator"
sys.modules.pop(_MOD_KEY, None)

from services.agent.utils.calculator import safe_eval, calculate, CALCULATOR_TOOLS  # noqa: E402


# ── Tests: basic arithmetic via safe_eval ────────────────────────────────

class TestSafeEvalArithmetic:
    def test_addition(self):
        assert safe_eval("2 + 3") == 5.0

    def test_subtraction(self):
        assert safe_eval("10 - 4") == 6.0

    def test_multiplication(self):
        assert safe_eval("6 * 7") == 42.0

    def test_division(self):
        assert safe_eval("15 / 4") == 3.75

    def test_integer_division(self):
        assert safe_eval("15 // 4") == 3.0

    def test_modulo(self):
        assert safe_eval("10 % 3") == 1.0

    def test_exponentiation(self):
        assert safe_eval("2 ** 10") == 1024.0

    def test_negative_numbers(self):
        assert safe_eval("-5 + 3") == -2.0

    def test_parentheses(self):
        assert safe_eval("(2 + 3) * 4") == 20.0

    def test_nested_parentheses(self):
        assert safe_eval("((2 + 3) * (4 - 1))") == 15.0

    def test_floating_point(self):
        assert abs(safe_eval("0.1 + 0.2") - 0.3) < 1e-10


# ── Tests: available built-in functions ──────────────────────────────────

class TestSafeEvalFunctions:
    def test_round(self):
        assert safe_eval("round(3.14159, 2)") == 3.14

    def test_round_no_decimal(self):
        assert safe_eval("round(3.7)") == 4.0

    def test_abs_positive(self):
        assert safe_eval("abs(-42)") == 42.0

    def test_abs_already_positive(self):
        assert safe_eval("abs(42)") == 42.0

    def test_sum_list(self):
        assert safe_eval("sum([1, 2, 3, 4, 5])") == 15.0

    def test_min(self):
        assert safe_eval("min(3, 1, 4, 1, 5)") == 1.0

    def test_max(self):
        assert safe_eval("max(3, 1, 4, 1, 5)") == 5.0

    def test_pow(self):
        assert safe_eval("pow(2, 8)") == 256.0

    def test_pow_with_mod(self):
        assert safe_eval("pow(2, 8, 100)") == 56.0


# ── Tests: math module functions ─────────────────────────────────────────

class TestSafeEvalMath:
    def test_math_sqrt(self):
        assert safe_eval("math.sqrt(144)") == 12.0

    def test_math_log_natural(self):
        assert abs(safe_eval("math.log(math.e)") - 1.0) < 1e-10

    def test_math_log10(self):
        assert safe_eval("math.log10(1000)") == 3.0

    def test_math_exp(self):
        assert abs(safe_eval("math.exp(0)") - 1.0) < 1e-10

    def test_math_exp_1(self):
        assert abs(safe_eval("math.exp(1)") - math.e) < 1e-10

    def test_math_pi(self):
        assert abs(safe_eval("math.pi") - 3.14159265) < 1e-5

    def test_math_ceil(self):
        assert safe_eval("math.ceil(3.2)") == 4.0

    def test_math_floor(self):
        assert safe_eval("math.floor(3.9)") == 3.0

    def test_math_sin(self):
        assert abs(safe_eval("math.sin(math.pi / 2)") - 1.0) < 1e-10

    def test_math_cos(self):
        assert abs(safe_eval("math.cos(0)") - 1.0) < 1e-10


# ── Tests: dangerous operations blocked ──────────────────────────────────

class TestSafeEvalSecurity:
    def test_import_blocked(self):
        result = safe_eval("__import__('os').system('echo pwned')")
        assert math.isnan(result)

    def test_exec_blocked(self):
        result = safe_eval("exec('print(1)')")
        assert math.isnan(result)

    def test_eval_blocked(self):
        result = safe_eval("eval('1+1')")
        assert math.isnan(result)

    def test_builtins_not_accessible(self):
        result = safe_eval("__builtins__")
        assert math.isnan(result)

    def test_open_blocked(self):
        result = safe_eval("open('/etc/passwd')")
        assert math.isnan(result)

    def test_getattr_on_object_blocked(self):
        result = safe_eval("().__class__.__bases__[0].__subclasses__()")
        assert math.isnan(result)

    def test_os_module_not_available(self):
        result = safe_eval("os.system('echo pwned')")
        assert math.isnan(result)

    def test_dunder_access_via_string(self):
        result = safe_eval("''.__class__.__mro__")
        assert math.isnan(result)


# ── Tests: edge cases ────────────────────────────────────────────────────

class TestSafeEvalEdgeCases:
    def test_division_by_zero(self):
        result = safe_eval("1 / 0")
        assert math.isnan(result)

    def test_empty_expression(self):
        result = safe_eval("")
        assert math.isnan(result)

    def test_whitespace_only(self):
        result = safe_eval("   ")
        assert math.isnan(result)

    def test_nonsense_string(self):
        result = safe_eval("hello world")
        assert math.isnan(result)

    def test_syntax_error(self):
        result = safe_eval("2 +")
        assert math.isnan(result)

    def test_very_large_number(self):
        assert safe_eval("10 ** 18") == 1e18

    def test_zero(self):
        assert safe_eval("0") == 0.0


# ── Tests: PV / interest calculation expressions ────────────────────────

class TestPVInterestCalculations:
    """Calculator is designed for PV, interest, and allocation expressions."""

    def test_present_value_single_cash_flow(self):
        """PV = FV / (1 + r)^n — $3M at 15% for 3 years."""
        result = safe_eval("3000000 / (1.15 ** 3)")
        expected = 3000000 / (1.15 ** 3)
        assert abs(result - expected) < 0.01

    def test_simple_interest(self):
        """Interest = Principal * rate * time/365."""
        result = safe_eval("100000 * 0.15 * 40 / 365")
        expected = 100000 * 0.15 * 40 / 365
        assert abs(result - expected) < 0.01

    def test_annuity_pv_with_sum_explicit(self):
        """PV of annuity = sum of discounted cash flows (explicit list, no range)."""
        result = safe_eval("sum([360000/1.15**1, 360000/1.15**2, 360000/1.15**3])")
        expected = sum(360000 / (1.15 ** i) for i in range(1, 4))
        assert abs(result - expected) < 0.01

    def test_annuity_pv_with_range_fails(self):
        """range() is a builtin not in _SAFE_MATH — comprehensions with range return NaN."""
        result = safe_eval("sum([360000 / (1.15 ** i) for i in range(1, 4)])")
        assert math.isnan(result)

    def test_combined_pv_calculation(self):
        """Combined PV: lump sum + annuity, rounded (explicit list, no range)."""
        expr = "round(3000000/1.15**3 + sum([360000/1.15**1, 360000/1.15**2, 360000/1.15**3]), 2)"
        result = safe_eval(expr)
        expected = round(3000000 / 1.15**3 + sum(360000/1.15**i for i in range(1, 4)), 2)
        assert result == expected

    def test_allocation_percentage(self):
        """Allocate $10000 by 60/40 split."""
        assert safe_eval("10000 * 0.6") == 6000.0
        assert safe_eval("10000 * 0.4") == 4000.0

    def test_compound_interest(self):
        """A = P * (1 + r/n)^(n*t)."""
        result = safe_eval("1000 * (1 + 0.05/12) ** (12 * 5)")
        expected = 1000 * (1 + 0.05/12) ** (12 * 5)
        assert abs(result - expected) < 0.01

    def test_depreciation_straight_line(self):
        """Annual depreciation = (cost - salvage) / useful_life."""
        result = safe_eval("(50000 - 5000) / 10")
        assert result == 4500.0

    def test_tax_amount(self):
        """Tax = income * rate."""
        result = safe_eval("250000 * 0.26")
        assert result == 65000.0


# ── Tests: calculate() tool function ────────────────────────────────────

class TestCalculateTool:
    """Test the public calculate() tool that wraps safe_eval."""

    def test_basic_expression(self):
        result = calculate("2 + 3")
        assert result == "5.0"

    def test_rounds_to_two_decimal_places(self):
        result = calculate("10 / 3")
        assert result == "3.33"

    def test_error_on_invalid_expression(self):
        result = calculate("invalid")
        assert result.startswith("Error:")

    def test_error_on_division_by_zero(self):
        result = calculate("1 / 0")
        assert result.startswith("Error:")

    def test_pv_example_from_docstring(self):
        result = calculate("3000000 / (1.15 ** 3)")
        expected = str(round(3000000 / (1.15 ** 3), 2))
        assert result == expected

    def test_interest_example_from_docstring(self):
        result = calculate("100000 * 0.15 * 40 / 365")
        expected = str(round(100000 * 0.15 * 40 / 365, 2))
        assert result == expected

    def test_sum_with_range_returns_error(self):
        """range() is not available in safe_eval (builtins disabled)."""
        result = calculate("sum([360000 / (1.15 ** i) for i in range(1, 4)])")
        assert result.startswith("Error:")

    def test_sum_explicit_list(self):
        """Explicit list works as a workaround for disabled range()."""
        result = calculate("sum([360000/1.15**1, 360000/1.15**2, 360000/1.15**3])")
        expected = str(round(sum(360000 / (1.15 ** i) for i in range(1, 4)), 2))
        assert result == expected

    def test_combined_explicit_list(self):
        result = calculate("round(3000000/1.15**3 + sum([360000/1.15**1, 360000/1.15**2, 360000/1.15**3]), 2)")
        expected = str(round(3000000 / 1.15**3 + sum(360000/1.15**i for i in range(1, 4)), 2))
        assert result == expected

    def test_dangerous_expression_returns_error(self):
        result = calculate("__import__('os').system('ls')")
        assert result.startswith("Error:")


# ── Tests: CALCULATOR_TOOLS export ──────────────────────────────────────

class TestCalculatorToolsExport:
    def test_calculator_tools_is_list(self):
        assert isinstance(CALCULATOR_TOOLS, list)

    def test_calculator_tools_contains_calculate(self):
        assert calculate in CALCULATOR_TOOLS

    def test_calculator_tools_length(self):
        assert len(CALCULATOR_TOOLS) == 1
