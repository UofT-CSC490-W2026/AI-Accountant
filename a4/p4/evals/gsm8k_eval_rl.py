"""Custom GSM8K eval for RL checkpoints — P4 per-problem evaluation.

Generates N samples per problem (default N=8 for Pass@8) and records
per-sample features needed by the process tool (D9 classification, D10 metrics).

Runner entrypoint:
    run_eval(checkpoint_dir, model_tag, step) -> dict

Output schema (consumed by collect.py -> process.py):
    {
        "task": "GSM8K",
        "source": "rl",
        "model_tag": "...",
        "step": 123,
        "gsm8k_debug": {
            "n": 1319,
            "sample_count": 8,
            "samples": [
                {
                    "idx": 0,
                    "ref_num": "109",
                    "responses": [
                        {
                            "pred_num": "109" | null,
                            "parseable": true,
                            "correct": true,
                            "completion": "full model response..."
                        },
                        ...  // N responses
                    ]
                },
                ...  // 1319 problems
            ]
        }
    }
"""

import os
import time
from contextlib import nullcontext

import torch


def _get_num_samples() -> int:
    """Number of samples per problem. Default 8 for Pass@8."""
    raw = os.getenv("P4_EVAL_NUM_SAMPLES", "").strip()
    if not raw:
        return 8
    return max(1, int(raw))


def _get_max_problems() -> int | None:
    """Cap on number of problems (for smoke tests). None = all."""
    raw = os.getenv("P4_EVAL_MAX_PROBLEMS", "").strip()
    if not raw:
        return None
    value = int(raw)
    return None if value <= 0 else value


def _get_shard_config() -> tuple[int, int]:
    """Return (shard_idx, num_shards). Defaults to (0, 1) = no sharding."""
    num_shards = int(os.getenv("P4_EVAL_NUM_SHARDS", "1"))
    shard_idx = int(os.getenv("P4_EVAL_SHARD_IDX", "0"))
    return shard_idx, max(1, num_shards)


def run_eval(
    checkpoint_dir: str,
    model_tag: str,
    step: int,
) -> dict:
    os.environ["NANOCHAT_BASE_DIR"] = checkpoint_dir

    from nanochat.checkpoint_manager import load_model
    from nanochat.common import autodetect_device_type
    from nanochat.engine import Engine
    from tasks.gsm8k import GSM8K, extract_answer

    device_type = autodetect_device_type()
    device = torch.device(device_type)
    autocast_ctx = (
        torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)
        if device_type == "cuda"
        else nullcontext()
    )

    model, tokenizer, meta = load_model(
        source="rl",
        device=device,
        phase="eval",
        model_tag=model_tag,
        step=step,
    )
    engine = Engine(model, tokenizer)

    num_samples = _get_num_samples()
    max_problems = _get_max_problems()
    shard_idx, num_shards = _get_shard_config()
    task = GSM8K(subset="main", split="test")
    total_n = len(task) if max_problems is None else min(max_problems, len(task))

    # Build list of problem indices for this shard
    all_indices = list(range(total_n))
    shard_indices = [i for i in all_indices if i % num_shards == shard_idx]
    eval_n = len(shard_indices)

    if num_shards > 1:
        print(f"[gsm8k_eval_rl] Shard {shard_idx}/{num_shards}: {eval_n} problems", flush=True)

    # Batch size for generation — generate all N samples in one call if possible,
    # otherwise loop in chunks to avoid OOM.
    device_batch_size = min(num_samples, int(os.getenv("P4_EVAL_DEVICE_BATCH", "8")))

    samples = []
    t0 = time.time()

    for i in shard_indices:
        conversation = task[i]
        prompt_ids = tokenizer.render_for_completion(conversation)
        prefix_length = len(prompt_ids)

        # Extract gold answer
        gold_text = conversation["messages"][-1]["content"][-1]["text"]
        ref_num = extract_answer(gold_text)

        # Generate N samples (in chunks if needed)
        responses = []
        remaining = num_samples
        chunk_idx = 0
        while remaining > 0:
            batch_n = min(remaining, device_batch_size)
            seed = hash((i, chunk_idx)) & 0x7FFFFFFF
            with autocast_ctx:
                generated_seqs, _ = engine.generate_batch(
                    prompt_ids,
                    num_samples=batch_n,
                    max_tokens=512,
                    temperature=1.0,
                    top_k=50,
                    seed=seed,
                )
            for seq in generated_seqs:
                completion = tokenizer.decode(seq[prefix_length:])
                pred_num = extract_answer(completion)
                parseable = pred_num is not None
                correct = parseable and (pred_num == ref_num)
                responses.append({
                    "pred_num": pred_num,
                    "parseable": parseable,
                    "correct": correct,
                    "completion": completion,
                })
            remaining -= batch_n
            chunk_idx += 1

        samples.append({
            "idx": i,
            "ref_num": ref_num,
            "responses": responses,
        })

        done = len(samples)
        if done == 1 or done % 50 == 0 or done == eval_n:
            elapsed = time.time() - t0
            eta = (elapsed / done) * (eval_n - done) if done else 0.0
            any_correct = any(r["correct"] for r in responses)
            all_parseable = all(r["parseable"] for r in responses)
            pass1_so_far = sum(s["responses"][0]["correct"] for s in samples) / done
            print(
                f"[gsm8k_eval_rl] {done}/{eval_n} "
                f"| pass@1={pass1_so_far:.4f} "
                f"| this: correct={any_correct} parse={all_parseable} "
                f"| elapsed={elapsed/60:.1f}m eta={eta/60:.1f}m",
                flush=True,
            )

    result = {
        "task": "GSM8K",
        "source": "rl",
        "model_tag": model_tag,
        "step": step,
        "max_problems": max_problems if max_problems is not None else "all",
        "num_samples": num_samples,
        "gsm8k_debug": {
            "n": eval_n,
            "sample_count": num_samples,
            "samples": samples,
        },
    }
    if num_shards > 1:
        result["shard_idx"] = shard_idx
        result["num_shards"] = num_shards
        result["total_problems"] = total_n
    return result
