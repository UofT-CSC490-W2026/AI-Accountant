"""Metric dataclasses and per-node usage callback for experiment tracking.

3 levels: per-agent, per-test-case, per-variant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


# ── Per-agent metrics ─────────────────────────────────────────────────────

@dataclass
class AgentMetrics:
    """Metrics for a single agent in a single test case."""
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    output: dict | None = None
    reason: str | None = None


# ── Common result (standardized for cross-variant comparison) ─────────────

@dataclass
class CommonResult:
    """Standardized output — every variant produces this."""
    debit_tuple: tuple | None = None
    credit_tuple: tuple | None = None
    journal_entry: dict | None = None
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    final_decision: str = "error"   # post / clarify / stuck / error


# ── Per-test-case metrics ─────────────────────────────────────────────────

@dataclass
class TestCaseMetrics:
    """Metrics for a single test case across all agents."""
    test_case_id: str
    variant_name: str
    common: CommonResult = field(default_factory=CommonResult)

    # ── Accuracy (compared against expected)
    debit_tuple_exact_match: bool = False
    credit_tuple_exact_match: bool = False
    debit_tuple_slot_accuracy: float = 0.0
    credit_tuple_slot_accuracy: float = 0.0
    entry_valid: bool = False
    entry_balance_correct: bool = False

    # ── Pipeline
    iteration_count: int = 0
    approver_confidence: float | None = None
    calibrated_confidence: float | None = None

    # ── Fix loop (optional — only when evaluator is active)
    fix_attempted: bool | None = None
    fix_succeeded: bool | None = None
    pre_fix_debit_tuple: tuple | None = None
    post_fix_debit_tuple: tuple | None = None
    pre_fix_credit_tuple: tuple | None = None
    post_fix_credit_tuple: tuple | None = None
    pre_fix_entry_valid: bool | None = None
    post_fix_entry_valid: bool | None = None
    fix_root_cause_agent: list[int] | None = None
    rejection_reason: str | None = None
    diagnostician_decision: str | None = None

    # ── Per-agent breakdown
    agent_metrics: dict[str, AgentMetrics] = field(default_factory=dict)

    # ── Error tracking
    error: str | None = None


# ── Per-variant metrics (aggregated) ──────────────────────────────────────

@dataclass
class VariantMetrics:
    """Aggregated metrics across all test cases for one variant."""
    variant_name: str
    num_test_cases: int = 0
    exact_match_rate: float = 0.0
    mean_slot_accuracy: float = 0.0
    entry_valid_rate: float = 0.0
    total_cost_usd: float = 0.0
    cost_per_correct_entry: float = 0.0
    mean_latency_ms: float = 0.0
    fix_rate: float = 0.0
    fix_success_rate: float = 0.0
    error_rate: float = 0.0


# ── Per-node usage callback ───────────────────────────────────────────────

class PerNodeUsageCallback(BaseCallbackHandler):
    """Tracks usage_metadata per LangGraph node name.

    Pass as callback in RunnableConfig. LangGraph calls on_chain_start
    with the node name before running each node.
    """

    def __init__(self):
        self.usage_by_node: dict[str, dict] = {}
        self._current_node: str | None = None

    def on_chain_start(self, serialized: Any, inputs: Any, *,
                       run_id: Any = None, name: str | None = None,
                       **kwargs) -> None:
        if name:
            self._current_node = name

    def on_llm_end(self, response: Any, **kwargs) -> None:
        if self._current_node and response.generations:
            msg = response.generations[0][0].message
            if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                self.usage_by_node[self._current_node] = dict(msg.usage_metadata)

    def reset(self) -> None:
        self.usage_by_node.clear()
        self._current_node = None
