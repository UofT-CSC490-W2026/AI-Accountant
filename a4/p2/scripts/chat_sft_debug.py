"""Debug wrapper around nanochat's chat_sft.

Adds:
- periodic heartbeat prints so the process is never silent
- periodic faulthandler traceback dumps so hangs leave evidence

The underlying SFT script and arguments remain unchanged.
"""

from __future__ import annotations

import argparse
import faulthandler
import os
import sys
import threading
import time


def _heartbeat(interval_s: int) -> None:
    while True:
        time.sleep(interval_s)
        print(f"[heartbeat] chat_sft alive at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)


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
                    f"[debug-wrapper] load_dataset retry {attempt}/{retries} failed: {exc!r}; "
                    f"sleeping {sleep_s}s before retry",
                    flush=True,
                )
                time.sleep(sleep_s)
        raise last_exc

    datasets.load_dataset = load_dataset_with_retry


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--debug-dump-seconds", type=int, default=120)
    parser.add_argument("--debug-heartbeat-seconds", type=int, default=60)
    parser.add_argument("--dataset-load-retries", type=int, default=5)
    parser.add_argument("--dataset-load-retry-sleep", type=int, default=15)
    parser.add_argument("--render-max-tokens", type=int, default=513)
    parser.add_argument("--attention-impl", type=str, default="auto")
    parser.add_argument("--debug-trace-every", type=int, default=0)
    parser.add_argument("--debug-trace-first-steps", type=int, default=0)
    parser.add_argument("--debug-trace-file", type=str, default="")
    args, remaining = parser.parse_known_args()

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

    print(
        f"[debug-wrapper] chat_sft debug wrapper active "
        f"(dump_every={args.debug_dump_seconds}s, heartbeat_every={args.debug_heartbeat_seconds}s, "
        f"dataset_load_retries={args.dataset_load_retries}, dataset_load_retry_sleep={args.dataset_load_retry_sleep}s, "
        f"render_max_tokens={args.render_max_tokens}, attention_impl={args.attention_impl}, "
        f"cuda_launch_blocking={os.environ['CUDA_LAUNCH_BLOCKING']}, "
        f"torch_show_cpp_stacktraces={os.environ['TORCH_SHOW_CPP_STACKTRACES']}, "
        f"torch_cpp_log_level={os.environ['TORCH_CPP_LOG_LEVEL']}, "
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


if __name__ == "__main__":
    main()
