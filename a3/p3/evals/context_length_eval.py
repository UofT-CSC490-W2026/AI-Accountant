#!/usr/bin/env python3
"""Positional perplexity eval for context window extension (P3).

Computes per-position cross-entropy loss bucketed into 128-token windows
on PG19 test split documents. Measures whether a model can handle
positions beyond its training length.

Requires: datasets (pip install datasets)

Usage (CLI):
    python context_length_eval.py \
        --checkpoint-dir /path/to/checkpoints \
        --model-tag pico-short \
        --step 929 \
        --output results.json

Usage (Python):
    from context_length_eval import run_eval
    results = run_eval("/path/to/checkpoints", "pico-short", 929)
"""

import argparse
import json
import math
import os

import numpy as np
import torch


def parse_args():
    parser = argparse.ArgumentParser(
        description="Positional perplexity eval for context extension"
    )
    parser.add_argument(
        "--checkpoint-dir", required=True,
        help="Base checkpoint directory (sets NANOCHAT_BASE_DIR)"
    )
    parser.add_argument("--model-tag", required=True, help="Model tag (e.g., pico-short)")
    parser.add_argument("--step", type=int, required=True, help="Checkpoint step number")
    parser.add_argument("--seq-len", type=int, default=2048, help="Sequence length for eval")
    parser.add_argument("--bucket-size", type=int, default=128, help="Bucket size in tokens")
    parser.add_argument("--output", required=True, help="Output JSON path")
    return parser.parse_args()


def load_pg19_test():
    """Load all documents from PG19 test split."""
    from datasets import load_dataset
    ds = load_dataset("deepmind/pg19", split="test")
    return ds["text"]


@torch.no_grad()
def compute_positional_losses(model, tokenizer, documents, seq_len, bucket_size, device):
    """Compute per-position cross-entropy loss across all documents,
    accumulated directly into buckets.

    Returns:
        bucket_sums: sum of losses per bucket
        bucket_sum_sqs: sum of squared losses per bucket (for std)
        bucket_counts: number of tokens per bucket
        doc_count: number of documents processed
    """
    num_buckets = seq_len // bucket_size
    bucket_sums = np.zeros(num_buckets, dtype=np.float64)
    bucket_sum_sqs = np.zeros(num_buckets, dtype=np.float64)
    bucket_counts = np.zeros(num_buckets, dtype=np.int64)
    doc_count = 0
    skipped = 0

    for doc_text in documents:
        tokens = tokenizer(doc_text, prepend="<|bos|>")

        # Need seq_len + 1 tokens: seq_len inputs + 1 shifted target
        if len(tokens) < seq_len + 1:
            skipped += 1
            continue

        tokens = tokens[:seq_len + 1]
        input_ids = torch.tensor([tokens[:-1]], dtype=torch.long, device=device)
        targets = torch.tensor([tokens[1:]], dtype=torch.long, device=device)

        # Per-token loss, shape: (seq_len,)
        loss = model(input_ids, targets=targets, loss_reduction='none')
        loss = loss.float().cpu().numpy()

        # Accumulate into buckets
        for b in range(num_buckets):
            start = b * bucket_size
            end = (b + 1) * bucket_size
            chunk = loss[start:end]
            bucket_sums[b] += chunk.sum()
            bucket_sum_sqs[b] += (chunk ** 2).sum()
            bucket_counts[b] += len(chunk)

        doc_count += 1
        if doc_count % 10 == 0:
            print(f"  Processed {doc_count} documents...")

    if skipped > 0:
        print(f"  Skipped {skipped} documents shorter than {seq_len + 1} tokens")

    return bucket_sums, bucket_sum_sqs, bucket_counts, doc_count


def run_eval(
    checkpoint_dir: str,
    model_tag: str,
    step: int,
    seq_len: int = 2048,
    bucket_size: int = 128,
) -> dict:
    """Run positional perplexity eval and return results dict.

    Args:
        checkpoint_dir: Base checkpoint directory (sets NANOCHAT_BASE_DIR).
        model_tag: Model tag (e.g., "pico-short").
        step: Checkpoint step number.
        seq_len: Sequence length for eval (default 2048).
        bucket_size: Bucket size in tokens (default 128).

    Returns:
        Dict with per-bucket losses, aggregate perplexity, and metadata.
    """
    assert seq_len % bucket_size == 0, (
        f"seq_len ({seq_len}) must be divisible by bucket_size ({bucket_size})"
    )

    # Set checkpoint directory before importing nanochat
    os.environ["NANOCHAT_BASE_DIR"] = checkpoint_dir
    from nanochat.checkpoint_manager import load_model

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    print(f"Loading model: tag={model_tag}, step={step}")
    model, tokenizer, _ = load_model(
        source="base",
        device=device,
        phase="eval",
        model_tag=model_tag,
        step=step,
    )

    print("Loading PG19 test split...")
    documents = load_pg19_test()
    print(f"Loaded {len(documents)} documents")

    num_buckets = seq_len // bucket_size
    print(f"Computing positional losses: seq_len={seq_len}, {num_buckets} buckets of {bucket_size} tokens")

    bucket_sums, bucket_sum_sqs, bucket_counts, doc_count = compute_positional_losses(
        model, tokenizer, documents, seq_len, bucket_size, device
    )

    # Build per-bucket results
    buckets = []
    for b in range(num_buckets):
        n = int(bucket_counts[b])
        if n > 0:
            mean_ce = bucket_sums[b] / n
            std_ce = math.sqrt(max(0, bucket_sum_sqs[b] / n - mean_ce ** 2))
        else:
            mean_ce = None
            std_ce = None
        buckets.append({
            "bucket": b,
            "position_start": b * bucket_size,
            "position_end": (b + 1) * bucket_size,
            "mean_cross_entropy": float(mean_ce) if mean_ce is not None else None,
            "std_cross_entropy": float(std_ce) if std_ce is not None else None,
            "num_tokens": n,
        })

    # Aggregate
    total_tokens = int(bucket_counts.sum())
    if total_tokens > 0:
        aggregate_ce = float(bucket_sums.sum() / total_tokens)
        aggregate_ppl = float(math.exp(aggregate_ce))
    else:
        aggregate_ce = None
        aggregate_ppl = None

    results = {
        "model_tag": model_tag,
        "step": step,
        "seq_len": seq_len,
        "bucket_size": bucket_size,
        "num_buckets": num_buckets,
        "document_count": doc_count,
        "total_tokens": total_tokens,
        "aggregate_cross_entropy": aggregate_ce,
        "aggregate_perplexity": aggregate_ppl,
        "buckets": buckets,
    }

    print(f"\nResults: {doc_count} documents, {total_tokens} tokens")
    if aggregate_ppl is not None:
        print(f"Aggregate perplexity: {aggregate_ppl:.2f}")

    return results


def main():
    args = parse_args()
    results = run_eval(
        checkpoint_dir=args.checkpoint_dir,
        model_tag=args.model_tag,
        step=args.step,
        seq_len=args.seq_len,
        bucket_size=args.bucket_size,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
