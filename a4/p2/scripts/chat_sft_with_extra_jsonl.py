"""Wrapper around nanochat's chat_sft that augments identity_conversations.jsonl.

This keeps the upstream SFT recipe intact while adding extra supervision through the
existing CustomJSON hook. The wrapper is intentionally minimal:

1. Read the original identity_conversations.jsonl from NANOCHAT_BASE_DIR.
2. Append extra conversation rows from a user-provided JSONL file.
3. Execute upstream scripts.chat_sft with the remaining CLI arguments.
4. Restore the original identity file on exit.

This is safe for sequential runs. Do not overlap multiple SFT runs that depend on
identity_conversations.jsonl in the same Modal volume.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def _read_nonempty_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--extra-conversations-jsonl", required=True)
    parser.add_argument("--extra-conversations-repeats", type=int, default=1)
    args, remaining = parser.parse_known_args()

    base_dir = os.environ.get("NANOCHAT_BASE_DIR")
    if not base_dir:
        raise RuntimeError("NANOCHAT_BASE_DIR is not set")

    identity_path = Path(base_dir) / "identity_conversations.jsonl"
    backup_path = identity_path.with_name(identity_path.name + ".a4p2.bak")
    extra_path = Path(args.extra_conversations_jsonl)
    if not extra_path.exists():
        raise FileNotFoundError(f"Extra conversations file not found: {extra_path}")

    original_exists = identity_path.exists()
    original_lines = _read_nonempty_lines(identity_path) if original_exists else []
    extra_lines = _read_nonempty_lines(extra_path)
    if not extra_lines:
        raise RuntimeError(f"No conversations found in {extra_path}")

    combined_lines = list(original_lines)
    for _ in range(max(1, args.extra_conversations_repeats)):
        combined_lines.extend(extra_lines)

    if original_exists:
        shutil.copy2(identity_path, backup_path)

    try:
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        with identity_path.open("w", encoding="utf-8") as f:
            for line in combined_lines:
                f.write(line)
                f.write("\n")
        print(
            f"[a4p2] Prepared augmented SFT file at {identity_path} "
            f"(original={len(original_lines)}, extra={len(extra_lines)}, "
            f"repeats={max(1, args.extra_conversations_repeats)})"
        )

        sys.argv = [sys.argv[0], *remaining]
        __import__("scripts.chat_sft")
    finally:
        if backup_path.exists():
            shutil.move(str(backup_path), str(identity_path))
        elif identity_path.exists():
            identity_path.unlink()
        print(f"[a4p2] Restored {identity_path}")


if __name__ == "__main__":
    main()
