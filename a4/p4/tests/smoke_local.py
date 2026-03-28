"""Local smoke test: fake data → process → produce.

Verifies the post-training pipeline works end-to-end without GPU or Modal.

Usage:
    cd /Users/bangun/Documents/Projects/Autobook
    python -m a4.p4.tests.smoke_local
"""

import json
import os
import shutil
import subprocess
import sys

SMOKE_DIR = "/tmp/p4-smoke-local"


def create_fake_eval(run_name: str, pass1_rate: float = 0.5):
    """Create a minimal eval JSON mimicking gsm8k_eval_rl.py output."""
    samples = []
    n_problems = 10
    for i in range(n_problems):
        ref_num = str(10 + i)
        correct = i < int(n_problems * pass1_rate)
        if correct:
            responses = [
                {"pred_num": ref_num, "parseable": True, "correct": True,
                 "completion": f"Let me solve this step by step.\nFirst we compute 5 + {5+i} = {10+i}.\n#### {ref_num}"},
                {"pred_num": str(int(ref_num) + 1), "parseable": True, "correct": False,
                 "completion": f"The answer is {int(ref_num)+1}.\n#### {int(ref_num)+1}"},
            ]
        else:
            responses = [
                {"pred_num": str(int(ref_num) + 5), "parseable": True, "correct": False,
                 "completion": f"I think it's {int(ref_num)+5}.\nSo the answer is {int(ref_num)+5}.\n#### {int(ref_num)+5}"},
                {"pred_num": None, "parseable": False, "correct": False,
                 "completion": "I'm not sure about this one."},
            ]
        samples.append({"idx": i, "ref_num": ref_num, "responses": responses})

    return {
        "task": "GSM8K",
        "source": "rl",
        "model_tag": f"p4-{run_name}",
        "step": 100,
        "gsm8k_debug": {
            "n": n_problems,
            "sample_count": 2,
            "samples": samples,
        },
    }


def create_fake_wandb(run_name: str, n_steps: int = 5):
    """Create a minimal W&B JSON mimicking collect.py output."""
    history = []
    for s in range(n_steps):
        entry = {
            "_step": s,
            "mean_reward": 0.3 + 0.1 * s,
            "mean_seq_length": 100 + 10 * s,
            "reward/correctness": 0.2 + 0.05 * s,
        }
        if run_name != "baseline":
            entry["reward/format_compliance"] = 0.1 + 0.05 * s
        history.append(entry)
    return {"run_id": f"fake-{run_name}", "run_name": run_name, "history": history}


def main():
    # Clean up
    if os.path.exists(SMOKE_DIR):
        shutil.rmtree(SMOKE_DIR)

    eval_dir = os.path.join(SMOKE_DIR, "eval")
    wandb_dir = os.path.join(SMOKE_DIR, "wandb")
    assets_dir = os.path.join(SMOKE_DIR, "assets")
    processed_path = os.path.join(SMOKE_DIR, "processed.json")
    os.makedirs(eval_dir)
    os.makedirs(wandb_dir)

    # Create fake data for 2 runs
    runs = {
        "baseline": {"pass1_rate": 0.4},
        "separate_a": {"pass1_rate": 0.6},
    }
    for name, params in runs.items():
        with open(os.path.join(eval_dir, f"{name}.json"), "w") as f:
            json.dump(create_fake_eval(name, **params), f, indent=2)
        with open(os.path.join(wandb_dir, f"{name}.json"), "w") as f:
            json.dump(create_fake_wandb(name), f, indent=2)

    print(f"Created fake data in {SMOKE_DIR}")

    # Run process
    print("\n--- PROCESS ---")
    ai_root = "/Users/bangun/Documents/Projects/Autobook/AI-Accountant"
    result = subprocess.run(
        [sys.executable, "-m", "a4.p4.scripts.process",
         "--input-dir", eval_dir,
         "--output", processed_path,
         "--baseline", "baseline"],
        cwd=ai_root,
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"PROCESS FAILED:\n{result.stderr}")
        sys.exit(1)

    # Verify processed.json
    with open(processed_path) as f:
        processed = json.load(f)
    assert "runs" in processed, "Missing 'runs' key"
    assert "comparisons" in processed, "Missing 'comparisons' key"
    assert "baseline" in processed["runs"], "Missing baseline run"
    assert "separate_a" in processed["runs"], "Missing separate_a run"
    print("processed.json: OK")

    # Run produce
    print("\n--- PRODUCE ---")
    result = subprocess.run(
        [sys.executable, "-m", "a4.p4.scripts.produce",
         "--processed", processed_path,
         "--wandb-dir", wandb_dir,
         "--output-dir", assets_dir],
        cwd=ai_root,
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"PRODUCE FAILED:\n{result.stderr}")
        sys.exit(1)

    # Check outputs
    print("\n--- OUTPUT CHECK ---")
    expected_files = [
        "t1_summary.tex", "t2_gained_lost.tex",
        "fig_error_distribution.pdf", "fig_error_delta.pdf",
        "fig_reward_curves.pdf", "fig_seq_length.pdf",
    ]
    all_ok = True
    for fname in expected_files:
        path = os.path.join(assets_dir, fname)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        status = f"OK ({size} bytes)" if exists else "MISSING"
        if not exists:
            all_ok = False
        print(f"  {fname}: {status}")

    # T3 and F4 may be skipped (need "combined" run)
    for fname in ["t3_synergy.tex", "fig_component_rewards.pdf"]:
        path = os.path.join(assets_dir, fname)
        exists = os.path.exists(path)
        print(f"  {fname}: {'OK' if exists else 'skipped (expected — no combined run)'}")

    if not all_ok:
        print("\nSome expected files MISSING!")
        sys.exit(1)

    print("\nLocal smoke test PASSED")


if __name__ == "__main__":
    main()
