#!/usr/bin/env python3
"""Resume GSM8K custom eval for base checkpoints from problem 1120.

One-off recovery script for a4p2-midtrain-orig-swiglu@5357.
Seeds prior counts from logged progress:
  - processed: 1120
  - strict correct: 0
  - relaxed correct: 11
"""

import time
from contextlib import nullcontext

import torch

from gsm8k_eval_base import _extract_last_number, _get_debug_n, _numeric_equal

START_INDEX = 1120
INITIAL_STRICT_PASSED = 0
INITIAL_RELAXED_PASSED = 11


def run_eval(
    checkpoint_dir: str,
    model_tag: str,
    step: int,
) -> dict:
    import os

    os.environ["NANOCHAT_BASE_DIR"] = checkpoint_dir

    from nanochat.checkpoint_manager import load_model
    from nanochat.common import autodetect_device_type
    from nanochat.dataloader import tokenizing_distributed_data_loader_bos_bestfit
    from nanochat.engine import Engine
    from nanochat.loss_eval import evaluate_bpb
    from nanochat.tokenizer import get_token_bytes
    from tasks.gsm8k import GSM8K, extract_answer

    device_type = autodetect_device_type()
    device = torch.device(device_type)
    autocast_ctx = (
        torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16)
        if device_type == "cuda"
        else nullcontext()
    )

    model, tokenizer, meta = load_model(
        source="base",
        device=device,
        phase="eval",
        model_tag=model_tag,
        step=step,
    )
    engine = Engine(model, tokenizer)

    sequence_len = int(meta["model_config"]["sequence_len"])
    device_batch_size = 16
    split_tokens = 4 * 524288
    tokens_per_step = max(1, device_batch_size * sequence_len)
    split_tokens = max(tokens_per_step, (split_tokens // tokens_per_step) * tokens_per_step)
    steps = max(1, split_tokens // tokens_per_step)
    token_bytes = get_token_bytes(device=device)

    bpb_results: dict[str, float] = {}
    for split_name in ("train", "val"):
        loader = tokenizing_distributed_data_loader_bos_bestfit(
            tokenizer, device_batch_size, sequence_len, split_name, device=device
        )
        with autocast_ctx:
            bpb = evaluate_bpb(model, loader, steps, token_bytes)
        bpb_results[split_name] = float(bpb)

    debug_n = _get_debug_n()
    task = GSM8K(subset="main", split="test")
    eval_n = len(task)
    strict_passed = INITIAL_STRICT_PASSED
    relaxed_passed = INITIAL_RELAXED_PASSED
    parseable = INITIAL_STRICT_PASSED
    samples = []
    sample_cap = min(debug_n, max(0, eval_n - START_INDEX)) if debug_n > 0 else 0
    t0 = time.time()

    for i in range(START_INDEX, eval_n):
        conversation = task[i]
        prompt_ids = tokenizer.render_for_completion(conversation)
        with autocast_ctx:
            results, _ = engine.generate_batch(
                prompt_ids,
                num_samples=1,
                max_tokens=512,
                temperature=0.0,
                top_k=50,
            )
        completion = tokenizer.decode(results[0][len(prompt_ids):])
        gold_text = conversation["messages"][-1]["content"][-1]["text"]
        ref_num = extract_answer(gold_text)
        strict_pred = extract_answer(completion)
        relaxed_pred = strict_pred if strict_pred is not None else _extract_last_number(completion)

        parseable += int(strict_pred is not None)
        strict_passed += int(strict_pred == ref_num)
        relaxed_passed += int(_numeric_equal(relaxed_pred, ref_num))

        if len(samples) < sample_cap:
            samples.append(
                {
                    "idx": i,
                    "ref_num": ref_num,
                    "strict_pred_num": strict_pred,
                    "relaxed_pred_num": relaxed_pred,
                    "completion_head": completion[:220],
                }
            )

        done = i + 1
        done_in_this_run = done - START_INDEX
        if done == START_INDEX + 1 or done % 10 == 0 or done == eval_n:
            elapsed = time.time() - t0
            remaining = eval_n - done
            eta = (elapsed / max(1, done_in_this_run)) * remaining
            print(
                f"[gsm8k_eval_resume] {done}/{eval_n} ({100*done/eval_n:.2f}%) | "
                f"strict={strict_passed/done:.4f} | relaxed={relaxed_passed/done:.4f} | "
                f"elapsed={elapsed/60:.1f}m | eta={eta/60:.1f}m",
                flush=True,
            )

    strict_accuracy = strict_passed / eval_n if eval_n else 0.0
    relaxed_accuracy = relaxed_passed / eval_n if eval_n else 0.0
    debug_info = {
        "n": eval_n,
        "resume_start_index": START_INDEX,
        "resume_initial_strict_passed": INITIAL_STRICT_PASSED,
        "resume_initial_relaxed_passed": INITIAL_RELAXED_PASSED,
        "sample_count": len(samples),
        "parseable_rate": parseable / eval_n if eval_n else 0.0,
        "strict_exact_rate": strict_accuracy,
        "numeric_match_rate": relaxed_accuracy,
        "samples": samples,
    }

    return {
        "task": "GSM8K",
        "source": "base",
        "model_tag": model_tag,
        "step": step,
        "train_bpb": bpb_results["train"],
        "val_bpb": bpb_results["val"],
        "bpb_steps": steps,
        "bpb_split_tokens": split_tokens,
        "max_problems": "all-resume-from-1120",
        "accuracy": relaxed_accuracy,
        "accuracy_strict": strict_accuracy,
        "accuracy_relaxed_numeric": relaxed_accuracy,
        "gsm8k_debug": debug_info,
    }
