from __future__ import annotations

import io
import profile
import pstats
from pathlib import Path
from time import perf_counter

from services.shared.normalization import NormalizationService


def sample_messages() -> list[dict]:
    vendors = ("Apple", "Pilot Coffee", "Staples", "Slack", "Landlord Inc")
    templates = (
        "Bought {qty} laptops from {vendor} for ${amount} on 2026-03-{day:02d}",
        "Paid {vendor} invoice {invoice} for {amount} on 03/{day:02d}/2026",
        "Transferred {amount} to savings on 2026-03-{day:02d}",
        "Paid rent to {vendor} for ${amount} and noted invoice {invoice}",
        "Bought {qty} desks from {vendor} for {amount} CAD",
    )

    messages: list[dict] = []
    for index in range(3000):
        qty = (index % 4) + 1
        vendor = vendors[index % len(vendors)]
        day = (index % 28) + 1
        amount = f"{((index % 250) + 1) * 19.95:,.2f}"
        invoice = 10_000 + index
        text = templates[index % len(templates)].format(
            qty=qty,
            vendor=vendor,
            amount=amount,
            invoice=invoice,
            day=day,
        )
        messages.append(
            {
                "source": "manual" if index % 2 == 0 else "csv",
                "currency": "CAD",
                "input_text": text,
                "description": text,
            }
        )
    return messages


def profile_function(name: str, fn) -> tuple[str, float]:
    profiler = profile.Profile()
    started = perf_counter()
    profiler.runcall(fn)
    elapsed_ms = (perf_counter() - started) * 1000

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(15)
    report = f"=== {name} ===\nwall_time_ms={elapsed_ms:.2f}\n{stream.getvalue()}"
    return report, elapsed_ms


def main() -> None:
    service = NormalizationService()
    messages = sample_messages()
    texts = [message["input_text"] for message in messages]

    output_dir = Path("a5_artifacts") / "profiling"
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "normalize_text": lambda: [service.normalize_text(text) for text in texts],
        "extract_amount_mentions": lambda: [service.extract_amount_mentions(text) for text in texts],
        "extract_date_mentions": lambda: [service.extract_date_mentions(text) for text in texts],
        "extract_party_mentions": lambda: [service.extract_party_mentions(text) for text in texts],
        "normalize": lambda: [service.normalize(message) for message in messages],
    }

    summary_rows: list[tuple[str, float]] = []
    for name, fn in targets.items():
        report, elapsed_ms = profile_function(name, fn)
        report_path = output_dir / f"{name}.txt"
        report_path.write_text(report, encoding="utf-8")
        summary_rows.append((name, elapsed_ms))
        print(f"[profile] wrote {report_path}")

    summary_rows.sort(key=lambda item: item[1], reverse=True)
    summary_lines = [
        "# A5 Profiling Summary",
        "",
        "Profiled with Python's `profile` module against 3,000 representative transaction messages.",
        "",
        "Optimizations applied before this run:",
        "- precompiled regex patterns for amount, date, party, and quantity extraction",
        "- `normalize_text` switched to split/join whitespace collapsing",
        "- `normalize()` now reuses precomputed date mentions instead of reparsing the description",
        "",
        "Measured wall-clock times:",
    ]
    summary_lines.extend(f"- `{name}`: {elapsed_ms:.2f} ms" for name, elapsed_ms in summary_rows)
    summary_path = output_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"[profile] wrote {summary_path}")


if __name__ == "__main__":
    main()
