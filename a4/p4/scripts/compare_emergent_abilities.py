"""
Compare three base-model checkpoints on the same question set:
- pico baseline
- nano baseline
- nano swiglu

Usage example:
python a3/p4/scripts/compare_emergent_abilities.py ^
  --pico_checkpoint pico-baseline@1433 ^
  --nano_baseline_checkpoint nano-baseline-fp8-full@4357 ^
  --nano_swiglu_checkpoint nano-swiglu-fp8-full@4357 ^
  --base_dir C:\\path\\to\\checkpoints

Checkpoint format:
- "<model_tag>@<step>" (recommended)
- "<model_tag>" (uses latest step in that tag directory)
"""

from __future__ import annotations

import argparse
import gc
import os
import re
import sys
from contextlib import nullcontext
from pathlib import Path

import torch


def _add_local_nanochat_repo_to_path() -> None:
    """Allow running from AI-Accountant by importing sibling ../nanochat."""
    here = Path(__file__).resolve()
    repo_root = here.parents[3]  # AI-Accountant/
    sibling_nanochat = repo_root.parent / "nanochat"
    if sibling_nanochat.exists():
        sys.path.insert(0, str(sibling_nanochat))


_add_local_nanochat_repo_to_path()

from nanochat.checkpoint_manager import load_model_from_dir  # noqa: E402
from nanochat.common import autodetect_device_type, get_base_dir  # noqa: E402
from nanochat.engine import Engine  # noqa: E402


DEFAULT_QUESTIONS = [
    "What is the capital city of Australia?",
    "What is the capital of Japan?",
    "Which country has the city of Barcelona?",
    "Who wrote the novel 1984?",
    "What is the largest ocean on Earth?",
    "What gas do humans breathe in that plants produce during photosynthesis?",
    "Why does the sky appear blue during the day?",
    "Why do objects fall toward the ground on Earth?",
    "What causes day and night on Earth?",
    "What part of a plant performs photosynthesis?",
    "Why do metals feel colder than wood at the same temperature?",
    "What happens to water when it freezes?",
    "If you drop a glass cup on a hard floor, what is more likely to happen: bounce or shatter?",
    "If someone forgets an umbrella during heavy rain, what will probably happen?",
    "If ice is left in the sun, what will happen after some time?",
    "If you put a book in water, what is likely to happen to the pages?",
    "If a person studies every day before an exam, what is likely to happen to their score?",
    "Identify the language: 'Je voudrais un cafe, s'il vous plait.'",
    "Identify the language: 'Hola, como estas?'",
    "Identify the language: 'Guten Morgen, wie geht es dir?'",
    "Identify the language: 'Ciao, come stai?'",
    "Translate to English: 'Bonjour tout le monde.'",
    "Translate to English: 'Gracias por tu ayuda.'",
    "Translate to Spanish: 'The weather is very nice today.'",
    "Translate to French: 'Good morning, how are you?'",
    "If Alice is older than Bob and Bob is older than Carol, who is the oldest?",
    "If all cats are animals and all animals breathe air, do cats breathe air?",
    "If some birds cannot fly, can we conclude that all birds cannot fly? Why or why not?",
    "Complete the sequence: 2, 4, 8, 16, __.",
    "Complete the sequence: Monday, Tuesday, Wednesday, __.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare pico/nano-baseline/nano-swiglu answers side-by-side.")
    parser.add_argument("--pico_checkpoint", required=True, help="Checkpoint spec: <tag>@<step> or <tag>")
    parser.add_argument("--nano_baseline_checkpoint", required=True, help="Checkpoint spec: <tag>@<step> or <tag>")
    parser.add_argument("--nano_swiglu_checkpoint", required=True, help="Checkpoint spec: <tag>@<step> or <tag>")
    parser.add_argument(
        "--base_dir",
        default="",
        help="Base checkpoint directory root (contains base_checkpoints). "
        "Default uses NANOCHAT_BASE_DIR/ ~/.cache/nanochat",
    )
    parser.add_argument(
        "--output_file",
        default="emergent_abilities_results.txt",
        help="Output text file path.",
    )
    parser.add_argument("--max_new_tokens", type=int, default=192, help="Max generated tokens per answer.")
    parser.add_argument(
        "--max_answer_chars",
        type=int,
        default=1600,
        help="Post-processed answer character cap to keep outputs readable.",
    )
    parser.add_argument(
        "--device_type",
        type=str,
        default="",
        choices=["", "cuda", "cpu", "mps"],
        help="Device type. Empty means autodetect.",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="bfloat16",
        choices=["float32", "bfloat16"],
        help="Autocast dtype on CUDA.",
    )
    return parser.parse_args()


def parse_checkpoint_spec(spec: str) -> tuple[str, int | None]:
    spec = spec.strip()
    if "@" in spec:
        tag, step_str = spec.rsplit("@", 1)
        tag = tag.strip()
        if not tag:
            raise ValueError(f"Invalid checkpoint spec '{spec}': empty model tag.")
        try:
            step = int(step_str)
        except ValueError as e:
            raise ValueError(f"Invalid checkpoint step in '{spec}'. Use <tag>@<step>.") from e
        return tag, step
    if not spec:
        raise ValueError("Checkpoint spec cannot be empty.")
    return spec, None


def sanitize_text(text: str) -> str:
    # Remove any generated special-token markup to keep output readable.
    text = re.sub(r"<\|[^|]+?\|>", "", text)
    return text.strip()


def _dedupe_adjacent_sentences(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out or p.lower() != out[-1].lower():
            out.append(p)
    return " ".join(out)


def postprocess_answer(text: str, max_answer_chars: int) -> str:
    text = sanitize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*Answer\s*:\s*", "", text, flags=re.IGNORECASE)

    # Stop when model starts another QA turn or repeats "Answer:" blocks.
    stop_patterns = [
        r"\n\s*Question\s*:",
        r"\n\s*Q\s*:",
        r"\n\s*User\s*:",
        r"\n\s*Answer\s*:",
        r"\n\s*###",
    ]
    cut = len(text)
    for pat in stop_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]

    text = re.sub(r"\s+", " ", text).strip()
    text = _dedupe_adjacent_sentences(text)
    if len(text) > max_answer_chars:
        text = text[: max_answer_chars - 3].rsplit(" ", 1)[0] + "..."
    return text if text else "<empty>"


def generate_answer(
    engine: Engine,
    tokenizer,
    question: str,
    max_new_tokens: int,
    max_answer_chars: int,
    autocast_ctx,
) -> str:
    prompt = (
        "Answer the question briefly and directly.\n"
        f"Question: {question}\n"
        "Answer:"
    )
    bos = tokenizer.get_bos_token_id()
    prompt_tokens = tokenizer.encode(prompt, prepend=bos)
    with autocast_ctx:
        seqs, _masks = engine.generate_batch(
            prompt_tokens,
            num_samples=1,
            max_tokens=max_new_tokens,
            temperature=0.0,  # deterministic decoding
            top_k=1,
            seed=42,
        )
    answer_tokens = seqs[0][len(prompt_tokens):]
    answer = tokenizer.decode(answer_tokens) if answer_tokens else ""
    return postprocess_answer(answer, max_answer_chars)


def run_model_on_questions(
    model_label: str,
    checkpoint_spec: str,
    checkpoints_dir: str,
    questions: list[str],
    device: torch.device,
    autocast_ctx,
    max_new_tokens: int,
    max_answer_chars: int,
) -> list[str]:
    tag, step = parse_checkpoint_spec(checkpoint_spec)
    print(f"[load] {model_label}: tag={tag}, step={step if step is not None else 'latest'}")
    model, tokenizer, _meta = load_model_from_dir(
        checkpoints_dir,
        device,
        phase="eval",
        model_tag=tag,
        step=step,
    )
    engine = Engine(model, tokenizer)
    answers = []
    for i, q in enumerate(questions, start=1):
        print(f"[gen] {model_label} Q{i}/{len(questions)}")
        answers.append(generate_answer(engine, tokenizer, q, max_new_tokens, max_answer_chars, autocast_ctx))

    # Free memory before loading the next model.
    del engine
    del model
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return answers


def main() -> None:
    args = parse_args()
    device_type = autodetect_device_type() if args.device_type == "" else args.device_type
    if device_type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available.")
    if device_type == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but not available.")
    device = torch.device(device_type)

    ptdtype = torch.float32 if args.dtype == "float32" else torch.bfloat16
    autocast_ctx = torch.amp.autocast(device_type=device_type, dtype=ptdtype) if device_type == "cuda" else nullcontext()

    base_dir = args.base_dir.strip() or get_base_dir()
    checkpoints_dir = os.path.join(base_dir, "base_checkpoints")
    if not os.path.isdir(checkpoints_dir):
        raise FileNotFoundError(
            f"Checkpoint directory not found: {checkpoints_dir}\n"
            "Pass --base_dir pointing to a directory that contains base_checkpoints/."
        )

    questions = list(DEFAULT_QUESTIONS)
    pico_label = f"Picochat ({args.pico_checkpoint})"
    nano_baseline_label = f"Nanochat baseline ({args.nano_baseline_checkpoint})"
    nano_swiglu_label = f"Nanochat swiglu ({args.nano_swiglu_checkpoint})"
    pico_answers = run_model_on_questions(
        model_label=pico_label,
        checkpoint_spec=args.pico_checkpoint,
        checkpoints_dir=checkpoints_dir,
        questions=questions,
        device=device,
        autocast_ctx=autocast_ctx,
        max_new_tokens=args.max_new_tokens,
        max_answer_chars=args.max_answer_chars,
    )
    nano_baseline_answers = run_model_on_questions(
        model_label=nano_baseline_label,
        checkpoint_spec=args.nano_baseline_checkpoint,
        checkpoints_dir=checkpoints_dir,
        questions=questions,
        device=device,
        autocast_ctx=autocast_ctx,
        max_new_tokens=args.max_new_tokens,
        max_answer_chars=args.max_answer_chars,
    )
    nano_swiglu_answers = run_model_on_questions(
        model_label=nano_swiglu_label,
        checkpoint_spec=args.nano_swiglu_checkpoint,
        checkpoints_dir=checkpoints_dir,
        questions=questions,
        device=device,
        autocast_ctx=autocast_ctx,
        max_new_tokens=args.max_new_tokens,
        max_answer_chars=args.max_answer_chars,
    )

    lines = []
    for q, pico, nano_base, nano_swiglu in zip(
        questions,
        pico_answers,
        nano_baseline_answers,
        nano_swiglu_answers,
    ):
        lines.append(f"Question: {q}\n")
        lines.append(f"{pico_label} answer:\n")
        lines.append(f"{pico}\n\n")
        lines.append(f"{nano_baseline_label} answer:\n")
        lines.append(f"{nano_base}\n\n")
        lines.append(f"{nano_swiglu_label} answer:\n")
        lines.append(f"{nano_swiglu}\n\n")
        lines.append("--------------------------------\n\n")

    output_text = "".join(lines)
    print("\n" + output_text)
    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"[done] Wrote results to {args.output_file}")


if __name__ == "__main__":
    main()
