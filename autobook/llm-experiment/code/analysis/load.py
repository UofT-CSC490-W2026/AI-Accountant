"""Load experiment results from disk.

Supports both flat and timestamped directory structures:
- Flat: results/<experiment>/<variant>/*.json
- Timestamped: results/<experiment>/<variant>/<timestamp>/*.json

Merges evaluation files (entry_accuracy.json, clarification_relevance.json)
into test case dicts if present.
"""
from __future__ import annotations

import json
from pathlib import Path

_SKIP = {"meta.json", "entry_accuracy.json", "clarification_relevance.json"}


def _merge_eval_file(cases: list[dict], run_dir: Path, filename: str,
                     result_key: str, eval_key: str) -> None:
    path = run_dir / filename
    if not path.exists():
        return
    evals = json.loads(path.read_text()).get("results", {})
    tc_by_id = {tc["test_case_id"]: tc for tc in cases}
    for tc_id, result in evals.items():
        if tc_id in tc_by_id:
            tc_by_id[tc_id][result_key] = result.get(eval_key, False)


def _load_cases_from_dir(d: Path) -> list[dict]:
    """Load test case JSONs from a single directory."""
    cases = []
    for f in sorted(d.glob("*.json")):
        if f.name in _SKIP:
            continue
        cases.append(json.loads(f.read_text()))
    return cases


def _merge_evals(cases: list[dict], d: Path) -> None:
    """Merge evaluation files into loaded cases."""
    _merge_eval_file(cases, d, "entry_accuracy.json", "entry_match", "match")
    _merge_eval_file(cases, d, "entry_accuracy.json", "entry_tax_relaxed_match", "tax_relaxed_match")
    _merge_eval_file(cases, d, "clarification_relevance.json", "clarification_correct", "relevant")


def _has_timestamp_subdirs(variant_dir: Path) -> bool:
    """Check if variant dir uses timestamp subdirectories."""
    return any(d.is_dir() for d in variant_dir.iterdir())


def _has_json_files(variant_dir: Path) -> bool:
    """Check if variant dir has JSON files directly (flat structure)."""
    return any(f.suffix == ".json" and f.name not in _SKIP
               for f in variant_dir.iterdir() if f.is_file())


def load_variant(experiment_dir: Path, variant_name: str) -> list[dict]:
    """Load all test cases for a variant. Handles both flat and timestamped layouts."""
    variant_dir = experiment_dir / variant_name
    if not variant_dir.is_dir():
        return []

    # Flat: JSONs directly in variant dir
    if _has_json_files(variant_dir):
        cases = _load_cases_from_dir(variant_dir)
        _merge_evals(cases, variant_dir)
        return cases

    # Timestamped: iterate subdirectories, merge across runs
    all_cases = []
    seen_ids = set()
    for run_dir in sorted(variant_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        cases = _load_cases_from_dir(run_dir)
        _merge_evals(cases, run_dir)
        for tc in cases:
            tc_id = tc["test_case_id"]
            if tc_id not in seen_ids:
                all_cases.append(tc)
                seen_ids.add(tc_id)
    return all_cases


def load_experiment(experiment: str,
                    variants: list[str] | None = None) -> dict[str, list[dict]]:
    """Load all variants for an experiment."""
    experiment_dir = Path("results") / experiment
    if not experiment_dir.is_dir():
        print(f"Warning: {experiment_dir} not found")
        return {}

    if variants is None:
        variants = sorted(d.name for d in experiment_dir.iterdir() if d.is_dir())

    results = {}
    for variant_name in variants:
        cases = load_variant(experiment_dir, variant_name)
        if cases:
            results[variant_name] = cases
    return results


def load_all_multi_runs(experiment: str,
                        variant_names: list[str]) -> dict[str, list[list[dict]]]:
    """Load all runs per variant for multi-run consistency.

    Only works with timestamped layout (each subdir = one run).
    Flat layout returns a single run.
    """
    experiment_dir = Path("results") / experiment
    all_runs = {}
    for variant_name in variant_names:
        variant_dir = experiment_dir / variant_name
        if not variant_dir.is_dir():
            continue

        # Flat: single run
        if _has_json_files(variant_dir):
            cases = _load_cases_from_dir(variant_dir)
            _merge_evals(cases, variant_dir)
            all_runs[variant_name] = [cases] if cases else []
            continue

        # Timestamped: multiple runs
        runs = []
        for run_dir in sorted(variant_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            cases = _load_cases_from_dir(run_dir)
            _merge_evals(cases, run_dir)
            if cases:
                runs.append(cases)
        all_runs[variant_name] = runs
    return all_runs
