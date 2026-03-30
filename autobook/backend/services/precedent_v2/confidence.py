"""Steps 9-11: Jeffreys prior confidence and threshold check.

Jeffreys prior: Beta(0.5, 0.5) — information-theoretic default.
Posterior mean: p = (k + 0.5) / (n + 1)
"""
from __future__ import annotations

THRESHOLD = 0.95
JEFFREYS_ALPHA = 0.5
JEFFREYS_BETA = 0.5


def jeffreys_confidence(k: int, n: int) -> float:
    """Compute posterior mean confidence using Jeffreys prior.

    Args:
        k: Count of most common label in the group.
        n: Total entries in the group.

    Returns:
        Posterior mean probability.
    """
    return (k + JEFFREYS_ALPHA) / (n + JEFFREYS_ALPHA + JEFFREYS_BETA)


def check_threshold(p: float, threshold: float = THRESHOLD) -> bool:
    """Check if confidence meets the threshold for bypass."""
    return p >= threshold
