"""Smoke-only wrapper around nanochat's chat_sft with tiny HF dataset slices.

The upstream SFT script always constructs the full original task mixture, which is
too expensive for a quick plumbing smoke in Modal. This wrapper monkey-patches the
task classes before importing `scripts.chat_sft` so that:

- SmolTalk loads only a tiny split slice.
- MMLU/GSM8K load only tiny split slices.
- Everything else in the upstream script remains unchanged.

This validates the real SFT code path without paying the full dataset startup cost.
"""

from __future__ import annotations

import argparse
import sys


def _slice_for(split: str, limit: int) -> str:
    return f"{split}[:{limit}]"


def _clamp_task_bounds(task) -> None:
    """Keep logical slicing within the physically loaded dataset slice."""
    ds_len = len(task.ds)
    if task.stop is None or task.stop > ds_len:
        task.stop = ds_len


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoltalk-train-limit", type=int, default=256)
    parser.add_argument("--smoltalk-test-limit", type=int, default=64)
    parser.add_argument("--mmlu-train-limit", type=int, default=128)
    parser.add_argument("--mmlu-test-limit", type=int, default=64)
    parser.add_argument("--gsm8k-train-limit", type=int, default=64)
    parser.add_argument("--gsm8k-test-limit", type=int, default=32)
    args, remaining = parser.parse_known_args()

    from datasets import load_dataset
    from tasks.common import Task
    import tasks.smoltalk as smoltalk_mod
    import tasks.mmlu as mmlu_mod
    import tasks.gsm8k as gsm8k_mod

    OriginalSmolTalk = smoltalk_mod.SmolTalk
    OriginalMMLU = mmlu_mod.MMLU
    OriginalGSM8K = gsm8k_mod.GSM8K

    class SmokeSmolTalk(OriginalSmolTalk):
        def __init__(self, split, **kwargs):
            Task.__init__(self, **kwargs)
            assert split in ["train", "test"], "SmolTalk split must be train|test"
            limit = args.smoltalk_train_limit if split == "train" else args.smoltalk_test_limit
            self.ds = load_dataset(
                "HuggingFaceTB/smol-smoltalk",
                split=_slice_for(split, limit),
            ).shuffle(seed=42)
            self.length = len(self.ds)
            _clamp_task_bounds(self)

    class SmokeMMLU(OriginalMMLU):
        def __init__(self, subset, split, **kwargs):
            Task.__init__(self, **kwargs)
            assert subset in ["all", "auxiliary_train"], f"subset {subset} must be all|auxiliary_train"
            assert split in ["train", "validation", "dev", "test"], f"split {split} must be train|validation|dev|test"
            if subset == "auxiliary_train":
                assert split == "train", "auxiliary_train must be split into train"
            self.subset = subset
            self.split = split
            limit = args.mmlu_train_limit if split == "train" else args.mmlu_test_limit
            self.ds = load_dataset("cais/mmlu", subset, split=_slice_for(split, limit)).shuffle(seed=42)
            if subset == "auxiliary_train":
                self.ds = self.ds.map(lambda row: row["train"], remove_columns=["train"])
            _clamp_task_bounds(self)

    class SmokeGSM8K(OriginalGSM8K):
        def __init__(self, subset, split, **kwargs):
            Task.__init__(self, **kwargs)
            assert subset in ["main", "socratic"], "GSM8K subset must be main|socratic"
            assert split in ["train", "test"], "GSM8K split must be train|test"
            limit = args.gsm8k_train_limit if split == "train" else args.gsm8k_test_limit
            self.ds = load_dataset("openai/gsm8k", subset, split=_slice_for(split, limit)).shuffle(seed=42)
            _clamp_task_bounds(self)

    smoltalk_mod.SmolTalk = SmokeSmolTalk
    mmlu_mod.MMLU = SmokeMMLU
    gsm8k_mod.GSM8K = SmokeGSM8K

    sys.argv = [sys.argv[0], *remaining]
    __import__("scripts.chat_sft")


if __name__ == "__main__":
    main()
