import re


def parse_tuple(raw: str) -> tuple[int, ...] | None:
    """Parse an LLM output string into a 6-tuple of non-negative integers.

    Accepts formats like "(1,0,1,0,0,0)", "1,0,1,0,0,0", or with spaces.
    Returns None on any parse failure.

    Args:
        raw: Raw LLM output string.

    Returns:
        6-tuple of non-negative ints, or None if parsing fails.
    """
    try:
        cleaned = raw.strip().strip("()")
        parts = [p.strip() for p in cleaned.split(",")]

        if len(parts) != 6:
            return None

        values = tuple(int(p) for p in parts)

        if any(v < 0 for v in values):
            return None

        return values
    except (ValueError, AttributeError):
        return None
