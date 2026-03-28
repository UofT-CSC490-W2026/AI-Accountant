"""Async runner — execute test cases in parallel with live display."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table

from models import TestCaseMetrics
from pricing import compute_actual_cost, compute_raw_cost
from callback import PerNodeUsageCallback
from state import build_initial_state, extract_common_result, extract_state_snapshot
from extract import extract_test_case_metrics

console = Console()

_CONCURRENCY = asyncio.Semaphore(3)


# ── Accumulator for multi-run stats ─────────────────────────────────────

class RunAccumulator:
    """Tracks cumulative stats across multiple runs per test case."""

    def __init__(self, total_runs: int):
        self.total_runs = total_runs
        self.current_run = 0
        self.completed: dict[str, int] = defaultdict(int)
        self.d_correct: dict[str, int] = defaultdict(int)
        self.d_wrong: dict[str, int] = defaultdict(int)
        self.c_correct: dict[str, int] = defaultdict(int)
        self.c_wrong: dict[str, int] = defaultdict(int)
        self.raw_cost: dict[str, float] = defaultdict(float)
        self.act_cost: dict[str, float] = defaultdict(float)
        self.latency: dict[str, int] = defaultdict(int)
        self.t_in: dict[str, int] = defaultdict(int)
        self.t_out: dict[str, int] = defaultdict(int)
        self.t_cr: dict[str, int] = defaultdict(int)
        self.t_cw: dict[str, int] = defaultdict(int)

    def record(self, tc_id: str, metrics: TestCaseMetrics,
               in_tok: int, out_tok: int, cr_tok: int, cw_tok: int) -> None:
        self.completed[tc_id] += 1
        if metrics.debit_tuple_exact_match:
            self.d_correct[tc_id] += 1
        else:
            self.d_wrong[tc_id] += 1
        if metrics.credit_tuple_exact_match:
            self.c_correct[tc_id] += 1
        else:
            self.c_wrong[tc_id] += 1
        self.raw_cost[tc_id] += metrics.common.raw_cost_usd
        self.act_cost[tc_id] += metrics.common.actual_cost_usd
        self.latency[tc_id] += metrics.common.total_latency_ms
        self.t_in[tc_id] += in_tok
        self.t_out[tc_id] += out_tok
        self.t_cr[tc_id] += cr_tok
        self.t_cw[tc_id] += cw_tok

    def avg(self, tc_id: str) -> dict:
        n = self.completed[tc_id] or 1
        return {
            "raw": self.raw_cost[tc_id] / n,
            "act": self.act_cost[tc_id] / n,
            "lat": self.latency[tc_id] / n,
            "in": self.t_in[tc_id] // n,
            "out": self.t_out[tc_id] // n,
            "cr": self.t_cr[tc_id] // n,
            "cw": self.t_cw[tc_id] // n,
        }


# ── Table builder ────────────────────────────────────────────────────────

def _color_count(val: int, good: bool) -> str:
    if val == 0:
        return "[dim]0[/dim]"
    return f"[green]{val}[/green]" if good else f"[red]{val}[/red]"


def _build_table(variant_name: str, statuses: dict, acc: RunAccumulator) -> Table:
    title = f"Variant: {variant_name}"
    if acc.total_runs > 1:
        title += f" (Run {acc.current_run}/{acc.total_runs})"

    table = Table(title=title, show_lines=False)
    table.add_column("Test Case", style="cyan", width=32)
    table.add_column("Status", width=12)
    table.add_column("#", width=5)
    table.add_column("D✓", justify="right", width=3)
    table.add_column("D✗", justify="right", width=3)
    table.add_column("C✓", justify="right", width=3)
    table.add_column("C✗", justify="right", width=3)
    table.add_column("Raw $", justify="right", width=9)
    table.add_column("Act $", justify="right", width=9)
    table.add_column("Latency", justify="right", width=9)
    table.add_column("In", justify="right", width=7)
    table.add_column("Out", justify="right", width=6)
    table.add_column("CacheR", justify="right", width=7)
    table.add_column("CacheW", justify="right", width=7)

    for tc_id, status in statuses.items():
        k = acc.completed[tc_id]
        n = acc.total_runs
        sched = f"{k}/{n}"

        if k == 0:
            table.add_row(tc_id, status, sched, "", "", "", "",
                          "", "", "", "", "", "", "")
        else:
            a = acc.avg(tc_id)
            table.add_row(
                tc_id, status, sched,
                _color_count(acc.d_correct[tc_id], True),
                _color_count(acc.d_wrong[tc_id], False),
                _color_count(acc.c_correct[tc_id], True),
                _color_count(acc.c_wrong[tc_id], False),
                f"${a['raw']:.4f}", f"${a['act']:.4f}", f"{a['lat']:.0f}ms",
                f"{a['in']:,}", f"{a['out']:,}", f"{a['cr']:,}", f"{a['cw']:,}",
            )
    return table


def _build_summary(acc: RunAccumulator) -> Table:
    """Build real-time summary table from accumulator."""
    total_done = sum(acc.completed.values())
    if total_done == 0:
        t = Table(title="Summary", show_lines=False, show_header=False)
        t.add_column("", width=60)
        t.add_row("[dim]Waiting for results...[/dim]")
        return t

    total_d_ok = sum(acc.d_correct.values())
    total_d_bad = sum(acc.d_wrong.values())
    exact = sum(1 for tc_id in acc.completed
                if acc.d_correct[tc_id] > 0 and acc.d_wrong[tc_id] == 0
                and acc.c_correct[tc_id] > 0 and acc.c_wrong[tc_id] == 0
                and acc.completed[tc_id] == acc.total_runs)

    t_in = sum(acc.t_in.values())
    t_out = sum(acc.t_out.values())
    t_cr = sum(acc.t_cr.values())
    t_cw = sum(acc.t_cw.values())
    raw = sum(acc.raw_cost.values())
    act = sum(acc.act_cost.values())
    lat = sum(acc.latency.values())

    err_style = "green" if total_d_bad == 0 else "red"
    match_pct = (total_d_ok / total_done * 100) if total_done else 0
    match_style = "green" if match_pct >= 80 else "yellow" if match_pct >= 50 else "red"

    summary = Table(title="Summary", show_lines=False)
    summary.add_column("", width=12)
    summary.add_column("Total", justify="right", width=10)
    summary.add_column("In", justify="right", width=10)
    summary.add_column("Out", justify="right", width=8)
    summary.add_column("Cache R", justify="right", width=10)
    summary.add_column("Cache W", justify="right", width=10)

    summary.add_row(
        f"[{match_style}]Match[/{match_style}]",
        f"[{match_style}]{total_d_ok}/{total_done}[/{match_style}]",
        "", "", "", "")
    summary.add_row(
        "Tokens",
        f"{t_in+t_out:,}", f"{t_in:,}", f"{t_out:,}", f"{t_cr:,}", f"{t_cw:,}")
    summary.add_row(
        "Cost", "",
        f"[bold]Raw ${raw:.4f}[/bold]", "",
        f"[dim]Cached ${act:.4f}[/dim]", "")
    summary.add_row(
        "Latency", f"{lat:,}ms", "", "", "", "")

    if total_done > 0:
        summary.add_row("", "", "", "", "", "")
        summary.add_row(
            "[dim]Avg/test[/dim]", "",
            f"{t_in//total_done:,}", f"{t_out//total_done:,}",
            f"{t_cr//total_done:,}", f"{t_cw//total_done:,}")
        summary.add_row(
            "", "",
            f"[bold]Raw ${raw/total_done:.4f}[/bold]", "",
            f"[dim]Cached ${act/total_done:.4f}[/dim]", "")
        summary.add_row(
            "", f"{lat//total_done:,}ms", "", "", "", "")

    return summary


def _build_display(variant_name: str, statuses: dict, acc: RunAccumulator) -> Group:
    """Combine summary + test case table into one live display."""
    return Group(
        _build_summary(acc),
        _build_table(variant_name, statuses, acc),
    )


# ── Single run ───────────────────────────────────────────────────────────

async def _run_one(app, tc, config_dict: dict, variant_name: str,
                   statuses: dict, pricing: dict,
                   acc: RunAccumulator) -> TestCaseMetrics:
    async with _CONCURRENCY:
        statuses[tc.id] = "🔄 running..."
        callback = PerNodeUsageCallback()
        config = {"configurable": config_dict or {}, "callbacks": [callback]}
        initial = build_initial_state(tc)

        start = time.perf_counter()
        final_state = None
        try:
            final_state = await app.ainvoke(initial, config=config)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            common = extract_common_result(final_state, callback, elapsed_ms, pricing)
            metrics = extract_test_case_metrics(final_state, tc, variant_name, common, callback, pricing)
            metrics.pipeline_state = extract_state_snapshot(final_state)
            metrics.pipeline_state["llm_calls"] = callback.llm_calls
            metrics.pipeline_state["stop_reasons"] = callback.stop_reasons

            t_in = sum(x.get("input_tokens", 0) for x in callback.llm_calls)
            t_out = common.total_output_tokens
            t_cr = sum((x.get("input_token_details") or {}).get("cache_read", 0) for x in callback.llm_calls)
            t_cw = sum((x.get("input_token_details") or {}).get("cache_creation", 0) for x in callback.llm_calls)

            acc.record(tc.id, metrics, t_in, t_out, t_cr, t_cw)
            statuses[tc.id] = "✅ done"
            return metrics

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            statuses[tc.id] = "❌ failed"
            metrics = TestCaseMetrics(test_case_id=tc.id, variant_name=variant_name, error=str(e))
            metrics.ambiguous = tc.ambiguous
            metrics.tier = tc.tier
            metrics.common.total_latency_ms = elapsed_ms
            metrics.common.raw_cost_usd = sum(compute_raw_cost(call, pricing) for call in callback.llm_calls)
            metrics.common.actual_cost_usd = sum(compute_actual_cost(call, pricing) for call in callback.llm_calls)
            if final_state:
                metrics.pipeline_state = extract_state_snapshot(final_state)
            metrics.pipeline_state = metrics.pipeline_state or {}
            metrics.pipeline_state["llm_calls"] = callback.llm_calls
            metrics.pipeline_state["stop_reasons"] = callback.stop_reasons
            return metrics


# ── Variant runner ───────────────────────────────────────────────────────

async def run_variant_async(variant_name: str, test_cases: list,
                            pricing: dict,
                            total_runs: int = 1) -> list[list[TestCaseMetrics]]:
    """Run test cases, returns list of result lists (one per run)."""
    if variant_name == "single_agent":
        from variants.single_agent.graph import app
    else:
        from services.agent.graph.graph import app

    from variants.variants import VARIANTS
    config_dict = VARIANTS.get(variant_name)
    if config_dict is None and variant_name != "single_agent":
        raise ValueError(f"Unknown variant: {variant_name}")

    acc = RunAccumulator(total_runs)
    all_results = []

    for run_idx in range(total_runs):
        acc.current_run = run_idx + 1
        statuses: dict = {tc.id: "⏳ pending" for tc in test_cases}

        with Live(_build_display(variant_name, statuses, acc), console=console, refresh_per_second=2) as live:
            tasks = [_run_one(app, tc, config_dict, variant_name, statuses, pricing, acc)
                     for tc in test_cases]
            results = []
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                live.update(_build_display(variant_name, statuses, acc))

        all_results.append(results)

    return all_results
