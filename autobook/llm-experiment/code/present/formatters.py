"""LaTeX formatting helpers."""
from __future__ import annotations


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "---"
    return f"{v * 100:.1f}\\%"


def fmt_cost(v: float | None) -> str:
    if v is None:
        return "$\\infty$"
    return f"\\${v:.4f}"


def fmt_tokens(v: int | float | None) -> str:
    if v is None:
        return "$\\infty$"
    return f"{int(v):,}"


def fmt_ms(v: float | None) -> str:
    if v is None:
        return "---"
    return f"{v:.0f}"


def fmt_delta(v: float, unit: str = "\\%") -> str:
    sign = "+" if v > 0 else ""
    if unit == "\\$":
        return f"{sign}\\${v:.4f}"
    if unit == "ms":
        return f"{sign}{v:.0f}ms"
    return f"{sign}{v * 100:.1f}{unit}"


def esc(s: str) -> str:
    """Escape LaTeX special characters."""
    return s.replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")
