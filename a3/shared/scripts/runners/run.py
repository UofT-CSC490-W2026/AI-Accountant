"""Orchestrator — dispatches training stages and evals. Runs on Modal (no GPU)."""

from shared.infra import app, image, setup, volume
from shared.helpers import partition_stages, resolve_eval_inputs
from runners.train import Train
from runners.evaluate import Evaluate


@app.function(image=image, timeout=24 * 3600)
def run(cfg: dict) -> dict:
    """
    1. Read config and set up tokenizer + data on the volume.
    2. Run independent training stages in parallel.
    3. Run dependent stages sequentially, resuming from prior results.
    4. Evaluate all checkpoints in parallel.
    5. Print summary and return results.
    """

    # [1] Config: read experiment settings from the YAML config
    nanochat_ref = cfg["nanochat_ref"]
    experiment_name = cfg.get("experiment_name", "experiment")
    gpu = cfg.get("gpu", "A100-80GB")
    timeout = cfg.get("timeout_hours", 3) * 3600
    data_shards = int(cfg.get("data_shards", 8))
    data_workers = int(cfg.get("data_workers", 4))
    _print_header(experiment_name, nanochat_ref)

    # [2] Setup: download tokenizer and data shards to the volume if missing
    setup.remote(nanochat_ref, data_shards, data_workers)

    # [3] Training: split stages and run them
    stage_results = {}
    independent, dependent = partition_stages(cfg.get("train", []))

    # [3.1] Independent stages: run in parallel since they don't depend on each other
    if independent:
        # [3.1.1] Log which stages are being spawned
        _log_stages_spawned(independent)

        # [3.1.2] Spawn: kick off each stage on its own GPU container
        handles = {}
        for stage in independent:
            stage_gpu = stage.get("gpu", gpu)
            handles[stage["name"]] = (
                stage,
                Train.with_options(gpu=stage_gpu, timeout=timeout)().run.spawn(
                    nanochat_ref, dict(stage["args"])
                ),
            )

        # [3.1.3] Collect: wait for each stage to finish and store its result
        for name, (stage, handle) in handles.items():
            result = handle.get()
            stage_results[name] = result
            print(f"[pipeline] [{name}] Done: final_step={result['final_step']}")

    # [3.2] Dependent stages: run sequentially, each resuming from a prior stage
    for stage in dependent:
        # [3.2.1] Validate: ensure the dependency has already completed
        stage_name = stage["name"]
        dep_name = stage["depends_on"]
        if dep_name not in stage_results:
            raise ValueError(
                f"Stage '{stage_name}' depends on '{dep_name}', "
                f"which hasn't run yet. Check stage ordering in config."
            )

        # [3.2.2] Resume args: compute resume_from_step and num_iterations from the prior stage
        args = dict(stage["args"])
        dep_final_step = stage_results[dep_name]["final_step"]
        args["resume_from_step"] = dep_final_step
        args["num_iterations"] = dep_final_step + stage["extra_iterations"]

        # [3.2.3] Log the resume point
        _log_stage_resume(stage_name, dep_name, dep_final_step, args["num_iterations"])

        # [3.2.4] Run: train this stage and store its result
        stage_gpu = stage.get("gpu", gpu)
        result = Train.with_options(gpu=stage_gpu, timeout=timeout)().run.remote(nanochat_ref, args)
        stage_results[stage_name] = result
        print(f"[pipeline] [{stage_name}] Done: final_step={result['final_step']}")

    # [4] Evaluation: build eval inputs from config and stage results
    eval_entries = cfg.get("eval", [])
    eval_inputs = resolve_eval_inputs(eval_entries, stage_results, nanochat_ref)

    # [4.1] Dispatch: spawn all evals in parallel and collect results
    eval_results = []
    if eval_inputs:
        # [4.1.1] Log which evals are queued
        _log_eval_queue(eval_inputs)

        # [4.1.2] Spawn: kick off each eval on its own GPU container
        handles = []
        for inp in eval_inputs:
            handles.append((inp, Evaluate.with_options(gpu=gpu, timeout=timeout)().run.spawn(*inp)))

        # [4.1.3] Collect: wait for each eval, isolating failures so one crash doesn't kill the rest
        for inp, handle in handles:
            try:
                result = handle.get()
                eval_results.append(result)
                _log_eval_result(result)
            except Exception as e:
                tag, step = inp[1], inp[2]
                print(f"[pipeline] [eval] FAILED: {tag}@{step}: {e}")
                eval_results.append({"checkpoint_tag": tag, "step": step, "error": str(e)})

    # [5] Summary: print final results
    _print_summary(experiment_name, stage_results, eval_results)

    return {
        "experiment_name": experiment_name,
        "stage_results": stage_results,
        "eval_results": eval_results,
    }


# ---------------------------------------------------------------------------
# Formatting helpers - not important
# ---------------------------------------------------------------------------

def _print_header(experiment_name: str, nanochat_ref: str):
    print(f"\n{'='*60}")
    print(f"  {experiment_name}")
    print(f"  nanochat ref: {nanochat_ref}")
    print(f"{'='*60}")
    print("\n[pipeline] Ensuring tokenizer + data exist on volume...")


def _log_stages_spawned(stages: list):
    names = [s["name"] for s in stages]
    print(f"\n[pipeline] Spawning {len(stages)} independent stages: {names}")


def _log_stage_resume(stage_name: str, dep_name: str, dep_step: int, num_iterations: int):
    print(f"\n[pipeline] [{stage_name}] Resuming from '{dep_name}' step {dep_step}")
    print(f"[pipeline] [{stage_name}] num_iterations={num_iterations}")


def _log_eval_queue(eval_inputs: list):
    print(f"\n[pipeline] Spawning {len(eval_inputs)} evals in parallel...")
    for inp in eval_inputs:
        max_per_task = inp[5] if len(inp) > 5 else -1
        suffix = f", max_per_task={max_per_task}" if max_per_task > 0 else ""
        print(f"[pipeline] [eval] Queued: {inp[1]} @ step {inp[2]} ({inp[3]}{suffix})")


def _log_eval_result(result: dict):
    tag = result.get("checkpoint_tag", "?")
    s = result.get("step", "?")
    val_bpb = result.get("val_bpb", "N/A")
    core = result.get("core_metric", "N/A")
    print(f"[pipeline]   {tag}@{s}: BPB={val_bpb}, CORE={core}")
    if "custom_eval" in result:
        ppl = result["custom_eval"].get("aggregate_perplexity")
        print(f"[pipeline]   Positional PPL: {ppl:.2f}" if ppl else "[pipeline]   Positional PPL: N/A")


def _print_summary(experiment_name: str, stage_results: dict, eval_results: list):
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {experiment_name}")
    print(f"{'='*60}")
    for name, res in stage_results.items():
        print(f"  {name}: final_step={res['final_step']}")
    for i, res in enumerate(eval_results):
        tag = res.get("checkpoint_tag", "?")
        s = res.get("step", "?")
        bpb = res.get("val_bpb", "N/A")
        core = res.get("core_metric", "N/A")
        err = res.get("error")
        if err:
            print(f"  eval[{i}] {tag}@{s}: FAILED — {err}")
        else:
            print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")
