"""Prepare a FineMath-backed parquet corpus for continued pretraining.

The output directory contains parquet files with a single `text` column so it can
be consumed by nanochat's base_train wrapper via --data-dir.

Optional augmentation:
- Mix in sampled documents from an existing base_data directory.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from datasets import load_dataset


def _iter_base_texts(base_dir: Path):
    for parquet_path in sorted(base_dir.glob("*.parquet")):
        pf = pq.ParquetFile(parquet_path)
        for row_group_idx in range(pf.num_row_groups):
            rg = pf.read_row_group(row_group_idx, columns=["text"])
            for text in rg.column("text").to_pylist():
                if isinstance(text, str) and text.strip():
                    yield text.strip()


def _write_parquet_shards(texts: list[str], output_dir: Path, docs_per_file: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    shard_idx = 0
    for start in range(0, len(texts), docs_per_file):
        batch = texts[start : start + docs_per_file]
        table = pa.Table.from_pydict({"text": batch})
        out_path = output_dir / f"shard_{shard_idx:05d}.parquet"
        pq.write_table(table, out_path, compression="zstd", row_group_size=min(1000, len(batch)))
        shard_idx += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare FineMath parquet mixture for midtraining.")
    parser.add_argument("--dataset-name", default="HuggingFaceTB/finemath")
    parser.add_argument(
        "--config-name",
        default="finemath-4plus",
        help="FineMath config/subset name.",
    )
    parser.add_argument("--split", default="train")
    parser.add_argument("--max-docs", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--docs-per-file", type=int, default=10000)
    parser.add_argument(
        "--base-mix-dir",
        default="",
        help="Optional directory of existing base_data parquet files to mix in.",
    )
    parser.add_argument(
        "--base-mix-docs",
        type=int,
        default=50000,
        help="Number of base documents to mix in when --base-mix-dir is set.",
    )
    parser.add_argument(
        "--output-dir",
        default="a4/p2/data/finemath_4plus_mix",
        help="Directory to write parquet shards into.",
    )
    args = parser.parse_args()

    texts: list[str] = []
    ds = load_dataset(args.dataset_name, args.config_name, split=args.split, streaming=True)
    for row in ds:
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
        if len(texts) >= args.max_docs:
            break

    if args.base_mix_dir:
        base_dir = Path(args.base_mix_dir)
        base_docs = 0
        for text in _iter_base_texts(base_dir):
            texts.append(text)
            base_docs += 1
            if base_docs >= args.base_mix_docs:
                break

    rng = random.Random(args.seed)
    rng.shuffle(texts)

    output_dir = Path(args.output_dir)
    _write_parquet_shards(texts, output_dir, docs_per_file=args.docs_per_file)
    print(f"Wrote {len(texts)} documents across parquet shards in {output_dir}")


if __name__ == "__main__":
    main()
