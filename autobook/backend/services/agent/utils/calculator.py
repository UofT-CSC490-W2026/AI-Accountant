"""Calculator tool for entry drafter.

Provides a safe math evaluator that the entry drafter can use
for PV calculations, interest, allocations, etc.
"""
import math
from langchain_core.tools import tool


# Safe namespace for eval — only math functions, no builtins
_SAFE_MATH = {
    "abs": abs, "round": round, "sum": sum, "min": min, "max": max,
    "pow": pow, "math": math,
}


def safe_eval(expression: str) -> float:
    """Evaluate a math expression safely."""
    try:
        result = eval(expression, {"__builtins__": {}}, _SAFE_MATH)
        return float(result)
    except Exception as e:
        return float("nan")


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.

    Use Python math syntax. Available: +, -, *, /, **, (), round(), abs(),
    sum(), min(), max(), pow(), math.log(), math.exp(), math.sqrt().

    Examples:
        "3000000 / (1.15 ** 3)" → 1972547.16
        "100000 * 0.15 * 40 / 365" → 1643.84
        "sum([360000 / (1.15 ** i) for i in range(1, 4)])" → 822262.84
        "round(3000000 / 1.15**3 + sum([360000/1.15**i for i in range(1,4)]), 2)" → 2794809.99
    """
    result = safe_eval(expression)
    if math.isnan(result):
        return f"Error: could not evaluate '{expression}'"
    return str(round(result, 2))


CALCULATOR_TOOLS = [calculate]
