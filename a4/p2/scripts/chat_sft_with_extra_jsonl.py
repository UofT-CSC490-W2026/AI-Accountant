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
import faulthandler
import os
import shutil
import sys
import threading
import time
from pathlib import Path


def _read_nonempty_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _heartbeat(interval_s: int) -> None:
    while True:
        time.sleep(interval_s)
        print(f"[heartbeat] chat_sft extra-jsonl alive at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)


def _install_load_dataset_retry(retries: int, sleep_s: int) -> None:
    if retries <= 1:
        return

    import datasets

    original_load_dataset = datasets.load_dataset

    def load_dataset_with_retry(*args, **kwargs):
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return original_load_dataset(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt == retries:
                    break
                print(
                    f"[a4p2] load_dataset retry {attempt}/{retries} failed: {exc!r}; "
                    f"sleeping {sleep_s}s before retry",
                    flush=True,
                )
                time.sleep(sleep_s)
        raise last_exc

    datasets.load_dataset = load_dataset_with_retry


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--extra-conversations-jsonl", required=True)
    parser.add_argument("--extra-conversations-repeats", type=int, default=1)
    parser.add_argument("--debug-dump-seconds", type=int, default=0)
    parser.add_argument("--debug-heartbeat-seconds", type=int, default=60)
    parser.add_argument("--dataset-load-retries", type=int, default=5)
    parser.add_argument("--dataset-load-retry-sleep", type=int, default=15)
    parser.add_argument("--render-max-tokens", type=int, default=513)
    parser.add_argument("--attention-impl", type=str, default="fa3")
    parser.add_argument("--debug-trace-every", type=int, default=0)
    parser.add_argument("--debug-trace-first-steps", type=int, default=0)
    parser.add_argument("--debug-trace-file", type=str, default="")
    args, remaining = parser.parse_known_args()

    base_dir = os.environ.get("NANOCHAT_BASE_DIR")
    if not base_dir:
        raise RuntimeError("NANOCHAT_BASE_DIR is not set")

    os.environ.setdefault("PYTHONFAULTHANDLER", "1")
    os.environ.setdefault("CUDA_LAUNCH_BLOCKING", "1")
    os.environ.setdefault("TORCH_SHOW_CPP_STACKTRACES", "1")
    os.environ.setdefault("TORCH_CPP_LOG_LEVEL", "INFO")
    if args.attention_impl == "auto":
        os.environ.pop("NANOCHAT_FLASH_IMPL", None)
    else:
        os.environ["NANOCHAT_FLASH_IMPL"] = args.attention_impl
    os.environ.setdefault("NANOCHAT_FUSED_OPTIM", "0")
    faulthandler.enable(all_threads=True)
    _install_load_dataset_retry(args.dataset_load_retries, args.dataset_load_retry_sleep)
    if args.debug_dump_seconds > 0:
        faulthandler.dump_traceback_later(args.debug_dump_seconds, repeat=True)
    if args.debug_heartbeat_seconds > 0:
        thread = threading.Thread(
            target=_heartbeat,
            args=(args.debug_heartbeat_seconds,),
            daemon=True,
        )
        thread.start()

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

        print(
            f"[a4p2] extra-jsonl wrapper active "
            f"(dump_every={args.debug_dump_seconds}s, heartbeat_every={args.debug_heartbeat_seconds}s, "
            f"dataset_load_retries={args.dataset_load_retries}, dataset_load_retry_sleep={args.dataset_load_retry_sleep}s, "
            f"render_max_tokens={args.render_max_tokens}, attention_impl={args.attention_impl}, "
            f"fused_optim={os.environ['NANOCHAT_FUSED_OPTIM']})",
            flush=True,
        )

        forwarded = list(remaining)
        if args.debug_trace_every > 0:
            forwarded.append(f"--debug-trace-every={args.debug_trace_every}")
        if args.debug_trace_first_steps > 0:
            forwarded.append(f"--debug-trace-first-steps={args.debug_trace_first_steps}")
        if args.debug_trace_file:
            forwarded.append(f"--debug-trace-file={args.debug_trace_file}")

        sys.argv = [sys.argv[0], *forwarded]
        __import__("scripts.chat_sft")
    finally:
        if backup_path.exists():
            shutil.move(str(backup_path), str(identity_path))
        elif identity_path.exists():
            identity_path.unlink()
        print(f"[a4p2] Restored {identity_path}")


if __name__ == "__main__":
    main()
