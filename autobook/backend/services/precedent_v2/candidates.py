"""Step 1-2: Filter precedent entries by vendor and check minimum count."""
from __future__ import annotations

from services.precedent_v2.models import PrecedentEntry

# n_min derived from threshold=0.95 using Jeffreys prior:
# For p = (k+0.5)/(n+1) >= 0.95 with k=n (unanimous), solve n >= 9.
N_MIN = 9


def filter_candidates(
    entries: list[PrecedentEntry],
    n_min: int = N_MIN,
) -> list[PrecedentEntry] | None:
    """Filter entries by minimum count.

    Returns:
        List of entries if len >= n_min, None (abstain) otherwise.
    """
    if len(entries) < n_min:
        return None
    return entries
