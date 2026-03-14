"""Wrapper around nanochat's base_train that overrides the parquet data directory."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", required=True)
    args, remaining = parser.parse_known_args()

    import nanochat.dataset as dataset

    dataset.DATA_DIR = args.data_dir
    os.makedirs(dataset.DATA_DIR, exist_ok=True)
    print(f"[a4p2] Using base-train data dir: {dataset.DATA_DIR}")

    sys.argv = [sys.argv[0], *remaining]
    __import__("scripts.base_train")


if __name__ == "__main__":
    main()
