#!/usr/bin/env python3
"""Fast/cheap GSM8K+BPB smoke eval for SFT checkpoints."""

import os
import re
import time
from contextlib import nullcontext

import torch

SMOKE_MAX_PROBLEMS = 32
SMOKE_BPB_DEVICE_BATCH_SIZE = 8
SMOKE_BPB_SPLIT_TOKENS = 16384


def _numeric_equal(a: str | None, b: str | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except ValueError:
        return False


_LAST_NUM_RE = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def _extract_last_number(text: str) -> str | None:
    matches = _LAST_NUM_RE.findall(text)
    if not matches:
        return None
    return matches[-1].replace(",", "").strip()


def run_eval(
    checkpoint_dir: str,
    model_tag: str,
    step: int,
) -> dict:
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
        source="sft",
        device=device,
        phase="eval",
        model_tag=model_tag,
        step=step,
    )
    engine = Engine(model, tokenizer)

    sequence_len = int(meta["model_config"]["sequence_len"])
    tokens_per_step = max(1, SMOKE_BPB_DEVICE_BATCH_SIZE * sequence_len)
    split_tokens = max(
        tokens_per_step,
        (SMOKE_BPB_SPLIT_TOKENS // tokens_per_step) * tokens_per_step,
    )
    steps = max(1, split_tokens // tokens_per_step)
    token_bytes = get_token_bytes(device=device)

    bpb_results: dict[str, float] = {}
    for split_name in ("train", "val"):
        loader = tokenizing_distributed_data_loader_bos_bestfit(
            tokenizer, SMOKE_BPB_DEVICE_BATCH_SIZE, sequence_len, split_name, device=device
        )
        with autocast_ctx:
            bpb = evaluate_bpb(model, loader, steps, token_bytes)
        bpb_results[split_name] = float(bpb)

    task = GSM8K(subset="main", split="test")
    n = min(SMOKE_MAX_PROBLEMS, len(task))
    parseable = 0
    exact = 0
    numeric = 0
    samples = []
    t0 = time.time()

    for i in range(n):
        conversation = task[i]
        prompt_ids = tokenizer.render_for_completion(conversation)
        with autocast_ctx:
            results, _ = engine.generate_batch(
                prompt_ids,
                num_samples=1,
                max_tokens=128,
                temperature=0.0,
                top_k=50,
            )
        completion = tokenizer.decode(results[0][len(prompt_ids):])
        gold_text = conversation["messages"][-1]["content"][-1]["text"]
        ref_num = extract_answer(gold_text)
        pred_num = extract_answer(completion)
        parseable += int(pred_num is not None)
        exact += int(pred_num == ref_num)
        relaxed_pred = pred_num if pred_num is not None else _extract_last_number(completion)
        numeric += int(_numeric_equal(relaxed_pred, ref_num))
        samples.append(
            {
                "idx": i,
                "ref_num": ref_num,
                "strict_pred_num": pred_num,
                "relaxed_pred_num": relaxed_pred,
                "strict_completion": completion,
            }
        )
        done = i + 1
        if done == 1 or done % 10 == 0 or done == n:
            elapsed = time.time() - t0
            eta = (elapsed / done) * (n - done) if done else 0.0
            print(
                f"[gsm8k_eval] {done}/{n} ({100*done/n:.2f}%) | "
                f"strict={exact/done:.4f} | relaxed={numeric/done:.4f} | "
                f"elapsed={elapsed/60:.1f}m | eta={eta/60:.1f}m",
                flush=True,
            )

    strict_accuracy = exact / n if n else 0.0
    relaxed_accuracy = numeric / n if n else 0.0

    return {
        "smoke": True,
        "task": "GSM8K",
        "source": "sft",
        "model_tag": model_tag,
        "step": step,
        "train_bpb": bpb_results["train"],
        "val_bpb": bpb_results["val"],
        "bpb_steps": steps,
        "bpb_split_tokens": split_tokens,
        "max_problems": SMOKE_MAX_PROBLEMS,
        "accuracy": relaxed_accuracy,
        "accuracy_strict": strict_accuracy,
        "accuracy_relaxed_numeric": relaxed_accuracy,
        "gsm8k_debug": {
            "n": n,
            "parseable_rate": parseable / n if n else 0.0,
            "strict_exact_rate": strict_accuracy,
            "numeric_match_rate": relaxed_accuracy,
            "samples": samples,
        },
    }
