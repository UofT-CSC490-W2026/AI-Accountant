from __future__ import annotations


def clamp_confidence(value: float | None, *, default: float = 0.0) -> float:
    if value is None:
        return default
    return max(0.0, min(1.0, float(value)))


def average_confidence(*scores: float | None, default: float = 0.6) -> float:
    valid_scores = [clamp_confidence(score) for score in scores if score is not None]
    if not valid_scores:
        return default
    return round(sum(valid_scores) / len(valid_scores), 3)
