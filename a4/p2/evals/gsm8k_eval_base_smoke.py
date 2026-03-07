#!/usr/bin/env python3
"""Fast/cheap GSM8K+BPB smoke eval for base checkpoints."""

import os
from contextlib import nullcontext

import torch

SMOKE_MAX_PROBLEMS = 8
SMOKE_BPB_DEVICE_BATCH_SIZE = 8
SMOKE_BPB_SPLIT_TOKENS = 16384


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
    from scripts.chat_eval import run_chat_eval

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

    with autocast_ctx:
        accuracy = run_chat_eval(
            task_name="GSM8K",
            model=model,
            tokenizer=tokenizer,
            engine=engine,
            batch_size=8,
            num_samples=1,
            max_new_tokens=128,
            temperature=0.0,
            top_k=50,
            max_problems=SMOKE_MAX_PROBLEMS,
        )

    return {
        "smoke": True,
        "task": "GSM8K",
        "source": "base",
        "model_tag": model_tag,
        "step": step,
        "train_bpb": bpb_results["train"],
        "val_bpb": bpb_results["val"],
        "bpb_steps": steps,
        "bpb_split_tokens": split_tokens,
        "max_problems": SMOKE_MAX_PROBLEMS,
        "accuracy": float(accuracy),
    }
