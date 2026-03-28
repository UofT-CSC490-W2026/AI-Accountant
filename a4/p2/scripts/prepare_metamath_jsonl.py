"""Prepare a MetaMathQA subset in nanochat CustomJSON conversation format.

Output format is one JSON array per line, because nanochat.tasks.customjson.CustomJSON
expects each JSONL line to be a raw list of alternating user/assistant messages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset


def _pick_text(row: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare MetaMathQA JSONL for nanochat SFT.")
    parser.add_argument(
        "--dataset-name",
        default="meta-math/MetaMathQA",
        help="Hugging Face dataset id.",
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--max-examples", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        default="a4/p2/data/metamathqa_50k.jsonl",
        help="Output JSONL path.",
    )
    args = parser.parse_args()

    ds = load_dataset(args.dataset_name, split=args.split)
    ds = ds.shuffle(seed=args.seed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as f:
        for row in ds:
            question = _pick_text(row, ("query", "question", "problem", "instruction"))
            answer = _pick_text(row, ("response", "answer", "output", "solution"))
            if not question or not answer:
                continue

            messages = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
            f.write(json.dumps(messages, ensure_ascii=False))
            f.write("\n")
            written += 1
            if written >= args.max_examples:
                break

    print(f"Wrote {written} MetaMathQA conversations to {output_path}")


if __name__ == "__main__":
    main()
