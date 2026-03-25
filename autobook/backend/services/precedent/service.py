from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrecedentCandidate:
    pattern_id: str
    normalized_description: str | None
    amount: float | None
    counterparty: str | None
    source: str | None
    lines: list[dict]


@dataclass(frozen=True)
class PrecedentMatch:
    matched: bool
    pattern_id: str | None
    confidence: float | None
    lines: list[dict]
    reasoning: str | None


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_name(value: str | None) -> str:
    return _normalize_text(value)


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens))


def _amount_matches(left, right) -> bool:
    try:
        return left is not None and right is not None and abs(float(left) - float(right)) < 0.005
    except (TypeError, ValueError):
        return False


def _score_candidate(message: dict, candidate: PrecedentCandidate) -> tuple[float, str]:
    message_description = _normalize_text(message.get("normalized_description") or message.get("description"))
    candidate_description = _normalize_text(candidate.normalized_description)
    message_counterparty = _normalize_name(message.get("counterparty"))
    candidate_counterparty = _normalize_name(candidate.counterparty)
    message_source = _normalize_text(message.get("source"))
    candidate_source = _normalize_text(candidate.source)

    score = 0.0
    reasons: list[str] = []

    if message_description and candidate_description:
        if message_description == candidate_description:
            score += 0.7
            reasons.append("exact normalized description match")
        else:
            overlap = _token_overlap_ratio(message_description, candidate_description)
            if overlap >= 0.75:
                score += 0.35
                reasons.append("high token overlap")
            elif overlap >= 0.5:
                score += 0.15
                reasons.append("partial token overlap")

    if _amount_matches(message.get("amount"), candidate.amount):
        score += 0.2
        reasons.append("amount match")

    if message_counterparty and candidate_counterparty and message_counterparty == candidate_counterparty:
        score += 0.1
        reasons.append("counterparty match")

    if message_source and candidate_source and message_source == candidate_source:
        score += 0.05
        reasons.append("source match")

    return min(round(score, 3), 0.99), ", ".join(reasons) if reasons else "no strong precedent signal"


def find_precedent_match(message: dict, candidates: list[PrecedentCandidate]) -> PrecedentMatch:
    best_candidate: PrecedentCandidate | None = None
    best_score = 0.0
    best_reason = ""

    for candidate in candidates:
        score, reason = _score_candidate(message, candidate)
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_reason = reason

    if best_candidate is None or best_score < 0.85:
        return PrecedentMatch(
            matched=False,
            pattern_id=None,
            confidence=None,
            lines=[],
            reasoning=None,
        )

    return PrecedentMatch(
        matched=True,
        pattern_id=best_candidate.pattern_id,
        confidence=best_score,
        lines=list(best_candidate.lines),
        reasoning=best_reason,
    )
