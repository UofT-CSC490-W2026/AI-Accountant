"""Pricing tables and cost computation functions."""
from __future__ import annotations

PRICING: dict[str, dict[str, float]] = {
    "sonnet": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write_5m": 3.75, "cache_write_1h": 6.00,
    },
    "haiku": {
        "input": 1.00, "output": 5.00,
        "cache_read": 0.10, "cache_write_5m": 1.25, "cache_write_1h": 2.00,
    },
    "opus": {
        "input": 5.00, "output": 25.00,
        "cache_read": 0.50, "cache_write_5m": 6.25, "cache_write_1h": 10.00,
    },
}

DEFAULT_CACHE_TTL = "1h"


def _get_cache_fields(usage: dict) -> tuple[int, int]:
    details = usage.get("input_token_details") or {}
    return details.get("cache_read", 0), details.get("cache_creation", 0)


def compute_actual_cost(usage: dict, pricing: dict,
                        cache_ttl: str = DEFAULT_CACHE_TTL) -> float:
    """Actual billed cost for one LLM call (cache-aware pricing)."""
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cache_read, cache_write = _get_cache_fields(usage)
    write_rate = pricing[f"cache_write_{cache_ttl}"]
    return (
        inp * pricing["input"]
        + cache_read * pricing["cache_read"]
        + cache_write * write_rate
        + out * pricing["output"]
    ) / 1_000_000


def compute_raw_cost(usage: dict, pricing: dict) -> float:
    """Cost as if no caching existed (fair cross-variant comparison)."""
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cache_read, cache_write = _get_cache_fields(usage)
    total_input = inp + cache_read + cache_write
    return (total_input * pricing["input"] + out * pricing["output"]) / 1_000_000


def total_input_tokens(usage: dict) -> int:
    """Total input tokens (non-cached + cache_read + cache_write)."""
    inp = usage.get("input_tokens", 0)
    cache_read, cache_write = _get_cache_fields(usage)
    return inp + cache_read + cache_write
