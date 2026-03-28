"""Shared utilities for GSM8K reward functions."""

import re

GSM_RE = re.compile(r"#### (\-?[0-9\.\,]+)")

def extract_answer(completion):
    """
    Extract the numerical answer after #### marker.
    Follows official code for normalization.
    """
    match = GSM_RE.search(completion)
    if match:
        match_str = match.group(1).strip()
        match_str = match_str.replace(",", "")
        return match_str
    return None
