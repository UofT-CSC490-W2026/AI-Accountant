"""Step 7-8: Extract (structure, ratio) labels and find the most common."""
from __future__ import annotations

from collections import Counter

from services.precedent_v2.models import Label, PrecedentEntry, extract_label


def extract_labels(entries: list[PrecedentEntry]) -> list[Label]:
    """Extract the (structure, ratio) label from each entry."""
    return [extract_label(entry) for entry in entries]


def find_most_common(labels: list[Label]) -> tuple[Label, int, int] | None:
    """Find the most common label and return (label, k, n).

    Args:
        labels: List of labels extracted from the amount cluster.

    Returns:
        (winning_label, k, n) where k = count of most common, n = total.
        None if labels is empty.
    """
    if not labels:
        return None

    # Use structure_hash as the grouping key (deterministic, fast)
    counter: Counter[str] = Counter()
    label_by_hash: dict[str, Label] = {}
    for label in labels:
        counter[label.structure_hash] += 1
        label_by_hash[label.structure_hash] = label

    most_common_hash, k = counter.most_common(1)[0]
    n = len(labels)

    return label_by_hash[most_common_hash], k, n
