"""Metric dataclasses — per-agent, per-test-case, per-variant."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentMetrics:
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_input_tokens: int = 0
    llm_calls: int = 0
    actual_cost_usd: float = 0.0
    raw_cost_usd: float = 0.0
    output: dict | None = None
    reason: str | None = None


@dataclass
class CommonResult:
    debit_tuple: tuple | None = None
    credit_tuple: tuple | None = None
    journal_entry: dict | None = None
    actual_cost_usd: float = 0.0
    raw_cost_usd: float = 0.0
    total_latency_ms: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0
    final_decision: str = "error"


@dataclass
class TestCaseMetrics:
    test_case_id: str
    variant_name: str
    common: CommonResult = field(default_factory=CommonResult)

    debit_tuple_exact_match: bool = False
    credit_tuple_exact_match: bool = False
    debit_tuple_slot_accuracy: float = 0.0
    credit_tuple_slot_accuracy: float = 0.0
    entry_valid: bool = False
    entry_balance_correct: bool = False

    iteration_count: int = 0
    approver_confidence: float | None = None
    calibrated_confidence: float | None = None

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

    decision_correct: bool = False
    entry_match: bool = False
    clarification_correct: bool | None = None  # None for non-ambiguous
    clarification_questions: list[str] | None = None  # extracted from wherever they exist
    tier: str = "basic"
    ambiguous: bool = False

    agent_metrics: dict[str, AgentMetrics] = field(default_factory=dict)
    error: str | None = None
    pipeline_state: dict | None = None


@dataclass
class VariantMetrics:
    variant_name: str
    num_test_cases: int = 0
    exact_match_rate: float = 0.0
    mean_slot_accuracy: float = 0.0
    entry_valid_rate: float = 0.0
    total_cost_usd: float = 0.0
    cost_per_correct_entry: float = 0.0
    mean_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    fix_rate: float = 0.0
    fix_success_rate: float = 0.0
    error_rate: float = 0.0
    decision_accuracy: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    cache_hit_rate: float = 0.0
    token_efficiency_ratio: float = 0.0
    tokens_per_correct_entry: float = 0.0
