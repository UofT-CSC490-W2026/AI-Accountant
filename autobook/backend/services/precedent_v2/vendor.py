"""Deterministic vendor name normalization.

Normalizes vendor names so that "APPLE INC", "Apple Inc.", "apple" all map
to the same key. Used as the first filter in the precedent lookup.
"""
from __future__ import annotations

import re

# Common suffixes to strip (Inc, Ltd, LLC, Corp, etc.)
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|ltd|limited|llc|corp|corporation|co|company)\b\.?",
    re.IGNORECASE,
)

# Non-alphanumeric characters (keep spaces)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")


def normalize_vendor(name: str | None) -> str:
    """Normalize a vendor name to a canonical form.

    Returns empty string if name is None or empty.
    """
    if not name:
        return ""
    result = name.lower().strip()
    result = _SUFFIXES.sub("", result)
    result = _NON_ALNUM.sub("", result)
    result = " ".join(result.split())  # collapse whitespace
    return result
