"""Process tool: classify, aggregate, and compare per-run eval results.

Usage:
    python -m a4.p4.scripts.process --input-dir a4/p4/results/collected/eval --output a4/p4/results/processed.json
    python -m a4.p4.scripts.process --input-dir a4/p4/results/collected/eval --output a4/p4/results/processed.json --baseline baseline

Input: directory of per-run eval JSONs (from collect tool), each with gsm8k_debug.samples array.
Output: one structured JSON with classifications, aggregations, and comparisons.

Expected eval JSON schema (per run):
    {
        "gsm8k_debug": {
            "n": 1319,
            "sample_count": 8,
            "samples": [
                {
                    "idx": 0,
                    "ref_num": "109",
                    "responses": [
                        {"pred_num": "109", "parseable": true, "correct": true, "completion": "..."},
                        ...
                    ]
                },
                ...
            ]
        }
    }

Also supports legacy single-sample format (from P2 eval):
    {
        "gsm8k_debug": {
            "samples": [
                {"idx": 0, "ref_num": "109", "strict_pred_num": "2", "completion_head": "..."},
                ...
            ]
        }
    }
"""

import argparse
import json
import os
import re

# D9 taxonomy rules — order matters (first match wins)
GSM_RE = re.compile(r"#### (\-?[0-9\.\,]+)")
CALC_OPEN = re.compile(r"<\|python_start\|>")


def classify_mistake(response_text: str, pred_num: str | None, ref_num: str, correct: bool) -> str | None:
    """Classify a single incorrect response using D9 taxonomy.

    Returns None if the response is correct (no mistake to classify).
    Returns one of: 'no_answer', 'format_only', 'no_reasoning', 'arithmetic_error', 'large_error', 'gibberish'
    """
    if correct:
        return None

    # Gibberish: degenerate text matching Reward C's anti-gibberish signals
    stripped = response_text.strip()
    if len(stripped) < 20:
        return "gibberish"
    tokens = stripped.split()
    if len(tokens) >= 3:
        camel_count = sum(
            1 for t in tokens
            if len(re.sub(r'[^a-zA-Z]', '', t)) > 3
            and sum(1 for c in re.sub(r'[^a-zA-Z]', '', t)[1:] if c.isupper()) >= 1
        )
        mega_count = sum(
            1 for t in tokens if len(re.sub(r'[^a-zA-Z]', '', t)) > 15
        )
        if camel_count / len(tokens) > 0.25 or mega_count / len(tokens) > 0.20:
            return "gibberish"

    # No answer: not parseable — no #### <number> marker
    has_format = GSM_RE.search(response_text) is not None
    if not has_format:
        return "no_answer"

    # Format only: has a number in output but not in #### <number> format
    # (This case is handled above — if GSM_RE matches, it IS in #### format.
    #  "Format only" means the response has numbers but not the #### marker.
    #  Since GSM_RE matched, this is not "format only".)
    # Actually, re-reading D9: "Format only" = "Has a number in output but not in #### <number> format"
    # This means GSM_RE did NOT match but there are numbers in the output.
    # Since we already returned 'no_answer' above when has_format is False,
    # we need to distinguish: no_answer = no number at all, format_only = has number but wrong format.
    # Let me re-check: D9 says:
    #   No answer: Not parseable — no #### <number> marker
    #   Format only: Has a number in output but not in #### <number> format
    # These overlap — both lack ####. The distinction is whether there's ANY number.
    # Let me handle this in the no_answer branch above.

    # If we get here, has_format is True (#### <number> exists)

    # No reasoning: jumped to #### <number> with no intermediate steps or calculator use
    has_calc = CALC_OPEN.search(response_text) is not None
    # Count lines with substantive content (not just the answer line)
    lines = [l.strip() for l in response_text.strip().split("\n") if l.strip()]
    non_answer_lines = [l for l in lines if not l.startswith("####")]
    if len(non_answer_lines) < 2 and not has_calc:
        return "no_reasoning"

    # Now we have format + reasoning. Classify based on proximity to gold.
    if pred_num is None:
        return "large_error"

    try:
        pred_val = float(pred_num.replace(",", ""))
        ref_val = float(ref_num.replace(",", ""))
    except (ValueError, TypeError):
        return "large_error"

    # Arithmetic error: calculator used, reasoning present, answer close to gold
    denominator = abs(ref_val) + 1.0
    relative_error = abs(pred_val - ref_val) / denominator
    if relative_error < 0.5:
        return "arithmetic_error"

    # Large error: answer far from gold
    return "large_error"


def _reclassify_no_answer(response_text: str) -> str:
    """Distinguish 'no_answer' from 'format_only' among responses without #### marker."""
    # Check if there are any numbers in the output at all
    if re.search(r"\d+", response_text):
        return "format_only"
    return "no_answer"


def process_sample_legacy(sample: dict) -> dict:
    """Process a single-sample legacy format entry."""
    ref_num = sample.get("ref_num", "")
    pred_num = sample.get("strict_pred_num")
    completion = sample.get("completion_head", "")
    parseable = pred_num is not None
    correct = parseable and str(pred_num).replace(",", "") == str(ref_num).replace(",", "")

    return {
        "idx": sample["idx"],
        "ref_num": ref_num,
        "responses": [{
            "pred_num": pred_num,
            "parseable": parseable,
            "correct": correct,
            "completion": completion,
        }],
    }


def process_run(eval_data: dict, run_name: str) -> dict:
    """Process one run's eval data: classify, aggregate.

    Returns structured per-run results.
    """
    debug = eval_data.get("gsm8k_debug", eval_data)
    samples = debug.get("samples", [])
    n_problems = debug.get("n", len(samples))
    sample_count = debug.get("sample_count", 1)

    # Detect format: multi-sample (has "responses") vs legacy (has "strict_pred_num")
    is_legacy = len(samples) > 0 and "strict_pred_num" in samples[0]
    if is_legacy:
        samples = [process_sample_legacy(s) for s in samples]

    # Per-problem aggregation
    problems = []
    pass1_count = 0
    pass8_count = 0
    total_responses = 0
    extraction_failures = 0
    mistake_counts = {
        "no_answer": 0, "format_only": 0, "no_reasoning": 0,
        "arithmetic_error": 0, "large_error": 0, "gibberish": 0,
    }

    for sample in samples:
        idx = sample["idx"]
        ref_num = sample.get("ref_num", "")
        responses = sample.get("responses", [])

        any_correct = False
        first_correct = False
        problem_mistakes = []

        for i, resp in enumerate(responses):
            total_responses += 1
            pred_num = resp.get("pred_num")
            parseable = resp.get("parseable", pred_num is not None)
            correct = resp.get("correct", False)
            completion = resp.get("completion", "")

            if not parseable:
                extraction_failures += 1

            if correct:
                any_correct = True
                if i == 0:
                    first_correct = True
            else:
                # Classify the mistake
                mistake = classify_mistake(completion, pred_num, ref_num, correct)
                if mistake == "no_answer":
                    mistake = _reclassify_no_answer(completion)
                if mistake:
                    problem_mistakes.append(mistake)

        if first_correct or (len(responses) == 1 and responses[0].get("correct", False)):
            pass1_count += 1
        if any_correct:
            pass8_count += 1

        # For per-problem classification, use the most common mistake type
        primary_mistake = None
        if not any_correct and problem_mistakes:
            from collections import Counter
            primary_mistake = Counter(problem_mistakes).most_common(1)[0][0]
            mistake_counts[primary_mistake] += 1

        problems.append({
            "idx": idx,
            "ref_num": ref_num,
            "pass1": first_correct or (len(responses) == 1 and responses[0].get("correct", False)),
            "pass8": any_correct,
            "primary_mistake": primary_mistake,
        })

    # Compute metrics
    pass1 = pass1_count / n_problems if n_problems > 0 else 0.0
    pass8 = pass8_count / n_problems if n_problems > 0 else 0.0
    extr_fail_rate = extraction_failures / total_responses if total_responses > 0 else 0.0
    total_errors = sum(mistake_counts.values())
    mistake_pcts = {
        k: (v / total_errors * 100 if total_errors > 0 else 0.0)
        for k, v in mistake_counts.items()
    }

    return {
        "run_name": run_name,
        "n_problems": n_problems,
        "sample_count": sample_count,
        "metrics": {
            "pass1": pass1,
            "pass1_count": pass1_count,
            "pass8": pass8,
            "pass8_count": pass8_count,
            "pass8_pass1_gap": pass8 - pass1,
            "extraction_failure_rate": extr_fail_rate,
        },
        "mistake_counts": mistake_counts,
        "mistake_pcts": mistake_pcts,
        "total_errors": total_errors,
        "problems": problems,
    }


def compare_runs(run_results: dict[str, dict], baseline_name: str) -> dict:
    """Compute cross-run comparisons.

    Returns:
        deltas: per-run metric differences vs baseline
        net_problem_deltas: gained/lost problems vs baseline
        synergy: combined vs sum of separates (if applicable)
    """
    if baseline_name not in run_results:
        return {"error": f"baseline '{baseline_name}' not found in run results"}

    baseline = run_results[baseline_name]
    baseline_pass1 = set(p["idx"] for p in baseline["problems"] if p["pass1"])
    baseline_pass8 = set(p["idx"] for p in baseline["problems"] if p["pass8"])

    comparisons = {}
    separate_deltas = {}

    for name, run in run_results.items():
        if name == baseline_name:
            continue

        run_pass1 = set(p["idx"] for p in run["problems"] if p["pass1"])
        run_pass8 = set(p["idx"] for p in run["problems"] if p["pass8"])

        gained = run_pass1 - baseline_pass1
        lost = baseline_pass1 - run_pass1

        # Metric deltas
        delta_pass1 = run["metrics"]["pass1"] - baseline["metrics"]["pass1"]
        delta_pass8 = run["metrics"]["pass8"] - baseline["metrics"]["pass8"]
        delta_gap = run["metrics"]["pass8_pass1_gap"] - baseline["metrics"]["pass8_pass1_gap"]
        delta_extr = run["metrics"]["extraction_failure_rate"] - baseline["metrics"]["extraction_failure_rate"]

        # Error distribution delta (percentage point change per category)
        error_delta = {
            k: run["mistake_pcts"].get(k, 0) - baseline["mistake_pcts"].get(k, 0)
            for k in baseline["mistake_pcts"]
        }

        comp = {
            "delta_pass1": delta_pass1,
            "delta_pass1_pp": delta_pass1 * 100,
            "delta_pass8": delta_pass8,
            "delta_pass8_pp": delta_pass8 * 100,
            "delta_gap": delta_gap,
            "delta_extraction_failure_rate": delta_extr,
            "gained_count": len(gained),
            "lost_count": len(lost),
            "net_delta": len(gained) - len(lost),
            "gained_idxs": sorted(gained),
            "lost_idxs": sorted(lost),
            "error_distribution_delta": error_delta,
        }
        comparisons[name] = comp

        # Track separate runs for synergy analysis
        if name.startswith("separate_"):
            separate_deltas[name] = delta_pass1

    # Synergy analysis (C10): Combined delta vs sum of Separate deltas
    synergy = {}
    if "combined" in comparisons and separate_deltas:
        combined_delta = comparisons["combined"]["delta_pass1"]
        sum_of_separates = sum(separate_deltas.values())

        if combined_delta > sum_of_separates:
            pattern = "synergy"
        elif separate_deltas and combined_delta < min(separate_deltas.values()):
            pattern = "interference"
        else:
            pattern = "additive"

        # Problem overlap analysis (C12)
        combined_gained = set(comparisons["combined"]["gained_idxs"])
        overlap = {}
        for sep_name, sep_comp in comparisons.items():
            if sep_name.startswith("separate_"):
                sep_gained = set(sep_comp["gained_idxs"])
                overlap[sep_name] = {
                    "intersection": len(combined_gained & sep_gained),
                    "combined_only": len(combined_gained - sep_gained),
                    "separate_only": len(sep_gained - combined_gained),
                }

        synergy = {
            "combined_delta_pass1": combined_delta,
            "sum_of_separate_deltas": sum_of_separates,
            "separate_deltas": separate_deltas,
            "pattern": pattern,
            "problem_overlap": overlap,
        }

    return {
        "baseline": baseline_name,
        "comparisons": comparisons,
        "synergy": synergy,
    }


def process_all(input_dir: str, output_path: str, baseline_name: str = "baseline"):
    """Process all per-run eval JSONs and produce structured results."""
    run_results = {}

    # Load all eval JSONs from input directory
    for filename in sorted(os.listdir(input_dir)):
        if not filename.endswith(".json"):
            continue
        run_name = filename.replace(".json", "")
        filepath = os.path.join(input_dir, filename)

        print(f"[process] Loading {run_name} from {filepath}")
        with open(filepath) as f:
            eval_data = json.load(f)

        run_results[run_name] = process_run(eval_data, run_name)
        m = run_results[run_name]["metrics"]
        print(f"[process] {run_name}: Pass@1={m['pass1']:.4f} ({m['pass1_count']}/{run_results[run_name]['n_problems']}), "
              f"Pass@8={m['pass8']:.4f}, ExtrFail={m['extraction_failure_rate']:.4f}")

    # Cross-run comparisons
    print(f"\n[process] Computing comparisons (baseline={baseline_name})")
    comparisons = compare_runs(run_results, baseline_name)

    # Build output
    output = {
        "runs": {name: {k: v for k, v in run.items() if k != "problems"} for name, run in run_results.items()},
        "per_problem": {name: run["problems"] for name, run in run_results.items()},
        "comparisons": comparisons,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[process] Results saved to {output_path}")

    # Print summary
    if comparisons.get("comparisons"):
        print(f"\n[process] Comparison summary vs {baseline_name}:")
        for name, comp in comparisons["comparisons"].items():
            print(f"  {name}: ΔPass@1={comp['delta_pass1_pp']:+.2f}pp, "
                  f"gained={comp['gained_count']}, lost={comp['lost_count']}, net={comp['net_delta']}")

    if comparisons.get("synergy"):
        syn = comparisons["synergy"]
        print(f"\n[process] Synergy: pattern={syn['pattern']}, "
              f"combined_delta={syn['combined_delta_pass1']:.4f}, "
              f"sum_of_separates={syn['sum_of_separate_deltas']:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Process eval results: classify, aggregate, compare")
    parser.add_argument("--input-dir", required=True, help="Directory of per-run eval JSONs")
    parser.add_argument("--output", required=True, help="Path for structured output JSON")
    parser.add_argument("--baseline", default="baseline", help="Name of baseline run (default: baseline)")
    args = parser.parse_args()

    process_all(args.input_dir, args.output, args.baseline)


if __name__ == "__main__":
    main()
