"""Orchestrator — dispatches training stages and evals. Runs on Modal (no GPU)."""

from shared.infra import app, image, setup, volume
from shared.helpers import partition_stages, resolve_eval_inputs
from runners.train import train
from runners.evaluate import evaluate


@app.function(image=image, timeout=4 * 3600)
def remote(cfg: dict) -> dict:
    """Run the full training + eval pipeline remotely.

    Dispatches setup, training stages, and evals. Returns all results.
    Runs on Modal (no GPU) so the pipeline survives local client disconnects.
    """
    nanochat_ref = cfg["nanochat_ref"]
    experiment_name = cfg.get("experiment_name", "experiment")

    print(f"\n{'='*60}")
    print(f"  {experiment_name}")
    print(f"  nanochat ref: {nanochat_ref}")
    print(f"{'='*60}")

    # --- Setup (idempotent) ---
    print("\n[pipeline] Ensuring tokenizer + data exist on volume...")
    setup.remote(nanochat_ref)

    # --- Training stages ---
    stage_results = {}
    independent, dependent = partition_stages(cfg["stages"])

    # Wave 1: independent stages — run in parallel via .spawn()
    if independent:
        names = [s["name"] for s in independent]
        print(f"\n[pipeline] Spawning {len(independent)} independent stages: {names}")
        handles = {}
        for stage in independent:
            handles[stage["name"]] = (stage, train.spawn(nanochat_ref, dict(stage["args"])))

        for name, (stage, handle) in handles.items():
            result = handle.get()
            stage_results[name] = result
            print(f"[pipeline] [{name}] Done: final_step={result['final_step']}")

    # Wave 2: dependent stages (sequential — each resolves from prior results)
    for stage in dependent:
        stage_name = stage["name"]
        dep_name = stage["depends_on"]
        if dep_name not in stage_results:
            raise ValueError(
                f"Stage '{stage_name}' depends on '{dep_name}', "
                f"which hasn't run yet. Check stage ordering in config."
            )

        args = dict(stage["args"])
        dep_final_step = stage_results[dep_name]["final_step"]
        args["resume_from_step"] = dep_final_step
        args["num_iterations"] = dep_final_step + stage["extra_iterations"]

        print(f"\n[pipeline] [{stage_name}] Resuming from '{dep_name}' step {dep_final_step}")
        print(f"[pipeline] [{stage_name}] num_iterations={args['num_iterations']}")

        result = train.remote(nanochat_ref, args)
        stage_results[stage_name] = result
        print(f"[pipeline] [{stage_name}] Done: final_step={result['final_step']}")

    # --- Evaluation (parallel dispatch with error isolation, M5) ---
    eval_entries = cfg.get("eval", [])
    eval_inputs = resolve_eval_inputs(eval_entries, stage_results, nanochat_ref)

    eval_results = []
    if eval_inputs:
        print(f"\n[pipeline] Spawning {len(eval_inputs)} evals in parallel...")
        for inp in eval_inputs:
            print(f"[pipeline] [eval] Queued: {inp[1]} @ step {inp[2]} ({inp[3]})")

        # Spawn all evals
        handles = []
        for inp in eval_inputs:
            handles.append((inp, evaluate.spawn(*inp)))

        # Collect results, isolating failures
        for inp, handle in handles:
            try:
                result = handle.get()
                eval_results.append(result)
                tag = result.get("checkpoint_tag", "?")
                s = result.get("step", "?")
                val_bpb = result.get("val_bpb", "N/A")
                core = result.get("core_metric", "N/A")
                print(f"[pipeline]   {tag}@{s}: BPB={val_bpb}, CORE={core}")
                if "custom_eval" in result:
                    ppl = result["custom_eval"].get("aggregate_perplexity")
                    print(f"[pipeline]   Positional PPL: {ppl:.2f}" if ppl else "[pipeline]   Positional PPL: N/A")
            except Exception as e:
                tag, step = inp[1], inp[2]
                print(f"[pipeline] [eval] FAILED: {tag}@{step}: {e}")
                eval_results.append({"checkpoint_tag": tag, "step": step, "error": str(e)})

    # --- Summary ---
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

    return {
        "experiment_name": experiment_name,
        "stage_results": stage_results,
        "eval_results": eval_results,
    }
