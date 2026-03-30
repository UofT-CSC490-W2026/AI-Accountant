"""Precedent matcher v2 — orchestrator.

Implements the full procedure:
  1. Normalize vendor → query precedent DB
  2. Check n_min
  3. Cluster by amount (Ckmeans)
  4. Assign transaction to cluster
  5. Extract labels, find consensus
  6. Check Jeffreys confidence
  7. Bypass or abstain
"""
from __future__ import annotations

import logging

from db.connection import SessionLocal, set_current_user_context
from local_identity import resolve_local_user
from services.precedent_v2.amount_cluster import assign_to_cluster, cluster_amounts
from services.precedent_v2.candidates import N_MIN, filter_candidates
from services.precedent_v2.confidence import THRESHOLD, check_threshold, jeffreys_confidence
from services.precedent_v2.dao import PrecedentDAO
from services.precedent_v2.structure import extract_labels, find_most_common
from services.precedent_v2.vendor import normalize_vendor
from services.precedent_v2.applicator import apply_label

logger = logging.getLogger(__name__)

TIME_WINDOW_DAYS = 365


def _build_abstain_result(message: dict, reason: str) -> dict:
    """Build result for abstain — no match, trigger next tier."""
    confidence = dict(message.get("confidence") or {})
    confidence["precedent"] = None
    return {
        **message,
        "precedent_match": {
            "matched": False,
            "confidence": None,
            "reason": reason,
        },
        "confidence": confidence,
    }


def _build_bypass_result(
    message: dict,
    proposed_entry: dict,
    p: float,
    k: int,
    n: int,
    structure_hash: str,
) -> dict:
    """Build result for bypass — confident match, auto-post."""
    confidence = dict(message.get("confidence") or {})
    confidence["precedent"] = p
    confidence["overall"] = p

    entry = proposed_entry["entry"]
    entry["date"] = message.get("transaction_date")
    entry["description"] = (
        message.get("input_text")
        or message.get("description")
        or message.get("normalized_description")
    )
    entry["transaction_id"] = message.get("transaction_id")
    entry["confidence"] = p

    return {
        **message,
        "precedent_match": {
            "matched": True,
            "confidence": p,
            "k": k,
            "n": n,
            "structure_hash": structure_hash,
            "reason": f"Consensus: {k}/{n} entries agree (p={p:.3f})",
        },
        "confidence": confidence,
        "proposed_entry": proposed_entry,
        "explanation": f"Matched {k}/{n} precedent entries with p={p:.3f} >= {THRESHOLD}.",
        "clarification": {
            "required": False,
            "clarification_id": None,
            "reason": None,
            "status": None,
        },
    }


def execute(message: dict) -> dict:
    """Run the precedent matching procedure.

    Returns enriched message with precedent_match result.
    Either bypass (with proposed_entry) or abstain (no proposed_entry).
    """
    logger.info("Processing: %s", message.get("parse_id"))

    # ── Normalize vendor ─────────────────────────────────────────
    raw_vendor = message.get("counterparty") or message.get("vendor") or ""
    vendor = normalize_vendor(raw_vendor)
    if not vendor:
        return _build_abstain_result(message, "no vendor")

    # ── Query precedent DB ───────────────────────────────────────
    db = SessionLocal()
    try:
        user = resolve_local_user(db, message.get("user_id"))
        set_current_user_context(db, user.id)
        entries = PrecedentDAO.get_by_vendor(
            db, user.id, vendor, time_window_days=TIME_WINDOW_DAYS
        )
    finally:
        db.close()

    # ── Step 1-2: Check minimum count ────────────────────────────
    candidates = filter_candidates(entries)
    if candidates is None:
        return _build_abstain_result(message, f"only {len(entries)} entries for vendor (need {N_MIN})")

    # ── Step 3-4: Cluster by amount ──────────────────────────────
    clusters = cluster_amounts(candidates)
    amount = float(message.get("amount") or 0)
    if amount <= 0:
        return _build_abstain_result(message, "no positive amount")

    cluster = assign_to_cluster(amount, clusters)
    if cluster is None:
        return _build_abstain_result(message, "amount outside all cluster ranges")

    # ── Step 7-8: Extract labels, find consensus ─────────────────
    labels = extract_labels(cluster.entries)
    result = find_most_common(labels)
    if result is None:
        return _build_abstain_result(message, "no labels in cluster")

    winning_label, k, n = result

    # ── Step 9-11: Jeffreys confidence ───────────────────────────
    p = jeffreys_confidence(k, n)
    if not check_threshold(p):
        return _build_abstain_result(
            message,
            f"confidence {p:.3f} < threshold {THRESHOLD} ({k}/{n} agree)",
        )

    # ── Step 12: Bypass — apply winning label ────────────────────
    province = (message.get("user_context") or {}).get("province", "ON")
    proposed_entry = apply_label(winning_label, amount, province)

    return _build_bypass_result(
        message, proposed_entry, p, k, n, winning_label.structure_hash
    )
