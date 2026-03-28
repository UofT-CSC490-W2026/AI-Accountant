"""Extract per-test-case and per-agent metrics from pipeline state."""
from __future__ import annotations

from collections import defaultdict

from accounting_engine.validators import validate_journal_entry
from pricing import compute_actual_cost, compute_raw_cost
from models import AgentMetrics, CommonResult, TestCaseMetrics
from callback import PerNodeUsageCallback


def _extract_clarification_questions(state: dict) -> list[str] | None:
    """Extract clarification questions from wherever they exist in the pipeline state.

    Checks (in order):
    1. state.clarification_questions (top-level)
    2. entry_builder output.clarification_questions
    3. disambiguator ambiguities[].clarification_question
    4. Fallback: debit_classifier reason (single_agent puts reasoning here)
    """
    ps = state

    # 1. Top-level
    cq = ps.get("clarification_questions")
    if cq:
        return cq

    # 2. Entry builder output
    eb = ps.get("output_entry_builder", [])
    if eb:
        latest = eb[-1] if eb else None
        if isinstance(latest, dict) and latest.get("clarification_questions"):
            return latest["clarification_questions"]

    # 3. Disambiguator ambiguities
    disam = ps.get("output_disambiguator", [])
    if disam:
        latest = disam[-1] if disam else None
        if isinstance(latest, dict):
            questions = [
                a["clarification_question"]
                for a in latest.get("ambiguities", [])
                if a.get("clarification_question")
            ]
            if questions:
                return questions

    # 4. Fallback: reason field (single_agent puts reasoning here)
    dc = ps.get("output_debit_classifier", [])
    if dc:
        latest = dc[-1] if dc else None
        if isinstance(latest, dict) and latest.get("reason"):
            return [latest["reason"]]

    return None


def _compute_slot_accuracy(actual: tuple | None, expected: tuple) -> float:
    if actual is None:
        return 0.0
    return sum(1 for a, e in zip(actual, expected) if a == e) / 6




def _build_agent_metrics(callback: PerNodeUsageCallback, state: dict,
                         pricing: dict) -> dict[str, AgentMetrics]:
    """Build per-agent metrics by grouping llm_calls by resolved node name."""
    i = state["iteration"]
    calls_by_node: dict[str, list[dict]] = defaultdict(list)
    for call in callback.llm_calls:
        calls_by_node[call["node"]].append(call)

    agent_metrics: dict[str, AgentMetrics] = {}
    for node_name, calls in calls_by_node.items():
        inp = sum(c.get("input_tokens", 0) for c in calls)
        out = sum(c.get("output_tokens", 0) for c in calls)
        cr = sum((c.get("input_token_details") or {}).get("cache_read", 0) for c in calls)
        cw = sum((c.get("input_token_details") or {}).get("cache_creation", 0) for c in calls)
        actual = sum(compute_actual_cost(c, pricing) for c in calls)
        raw = sum(compute_raw_cost(c, pricing) for c in calls)
        agent_out = state.get(f"output_{node_name}", [])
        latest = agent_out[i] if i < len(agent_out) else None

        agent_metrics[node_name] = AgentMetrics(
            agent_name=node_name, input_tokens=inp, output_tokens=out,
            cache_read_tokens=cr, cache_write_tokens=cw,
            total_input_tokens=inp + cr + cw, llm_calls=len(calls),
            actual_cost_usd=actual, raw_cost_usd=raw,
            output=latest,
            reason=latest.get("reason") if isinstance(latest, dict) else None,
        )
    return agent_metrics


def extract_test_case_metrics(state: dict, test_case, variant_name: str,
                              common: CommonResult, callback: PerNodeUsageCallback,
                              pricing: dict) -> TestCaseMetrics:
    """Extract full test case metrics from final state."""
    i = state["iteration"]
    m = TestCaseMetrics(test_case_id=test_case.id, variant_name=variant_name, common=common)
    m.ambiguous = test_case.ambiguous
    m.tier = test_case.tier
    m.decision_correct = common.final_decision == test_case.expected_decision

    if test_case.ambiguous:
        # Ambiguous: extract clarification questions from wherever they exist
        m.clarification_questions = _extract_clarification_questions(state)
        m.clarification_correct = None  # evaluated post-hoc by Claude
    else:
        # Non-ambiguous: tuple match automated, entry match evaluated post-hoc by Claude
        m.debit_tuple_exact_match = common.debit_tuple == test_case.expected_debit_tuple
        m.credit_tuple_exact_match = common.credit_tuple == test_case.expected_credit_tuple
        m.debit_tuple_slot_accuracy = _compute_slot_accuracy(common.debit_tuple, test_case.expected_debit_tuple)
        m.credit_tuple_slot_accuracy = _compute_slot_accuracy(common.credit_tuple, test_case.expected_credit_tuple)
        m.entry_match = None  # evaluated post-hoc by Claude

    if common.journal_entry:
        validation = validate_journal_entry(common.journal_entry)
        m.entry_valid = validation["valid"]
        m.entry_balance_correct = validation["valid"]
    else:
        m.entry_valid = test_case.expected_entry is None

    m.iteration_count = i + 1
    approver_out = state.get("output_approver", [])
    if approver_out and i < len(approver_out):
        m.approver_confidence = approver_out[i].get("confidence")

    if i > 0:
        m.fix_attempted = True
        m.fix_succeeded = approver_out[i].get("approved", False) if i < len(approver_out) else False
        debit_out = state.get("output_debit_corrector", [])
        credit_out = state.get("output_credit_corrector", [])
        if len(debit_out) > 1:
            m.pre_fix_debit_tuple = tuple(debit_out[0]["tuple"]) if debit_out[0] else None
            m.post_fix_debit_tuple = tuple(debit_out[1]["tuple"]) if debit_out[1] else None
        if len(credit_out) > 1:
            m.pre_fix_credit_tuple = tuple(credit_out[0]["tuple"]) if credit_out[0] else None
            m.post_fix_credit_tuple = tuple(credit_out[1]["tuple"]) if credit_out[1] else None
        diag_out = state.get("output_diagnostician", [])
        if diag_out:
            diag = diag_out[0]
            m.diagnostician_decision = diag.get("decision")
            m.fix_root_cause_agent = [p["agent"] for p in diag.get("fix_plans", [])]
            m.rejection_reason = approver_out[0].get("reason") if approver_out else None

    m.agent_metrics = _build_agent_metrics(callback, state, pricing)
    return m
