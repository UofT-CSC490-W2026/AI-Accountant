from __future__ import annotations

import io
import profile
import pstats
from pathlib import Path

import pandas as pd

from common.ids import stable_txn_id
from jobs.normalize_transactions.job import (
    build_canonical_records,
    clean_transactions_dataframe,
    normalize_columns,
    normalize_text,
    run,
)


def sample_dataframe() -> pd.DataFrame:
    rows = []
    for i in range(1000):
        rows.append(
            {
                "Date": f"2026-03-{(i % 28) + 1:02d}",
                "Description": f"  Office supply purchase {i % 15}  ",
                "Amount": f"{(i % 250) + 0.99:.2f}",
            }
        )
    return pd.DataFrame(rows)


def profile_function(name: str, fn) -> str:
    profiler = profile.Profile()
    profiler.runcall(fn)

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(12)
    report = f"=== {name} ===\n{stream.getvalue()}"
    return report


def main() -> None:
    df = sample_dataframe()
    cleaned = clean_transactions_dataframe(df)
    output_dir = Path("a5_artifacts") / "profiling"
    scratch_dir = output_dir / "scratch"
    output_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    csv_path = scratch_dir / "profile_input.csv"
    parquet_path = scratch_dir / "profile_output.parquet"
    df.to_csv(csv_path, index=False)

    targets = {
        "stable_txn_id": lambda: [stable_txn_id("bank_csv", "2026-03-17", "10.00", "Coffee") for _ in range(20000)],
        "normalize_text": lambda: [normalize_text("  Paid   contractor   invoice  ") for _ in range(20000)],
        "normalize_columns": lambda: normalize_columns(df),
        "clean_transactions_dataframe": lambda: clean_transactions_dataframe(df),
        "build_canonical_records": lambda: build_canonical_records(cleaned, "bank_csv", "CAD"),
        "run": lambda: run(str(csv_path), str(parquet_path), "bank_csv", "CAD"),
    }

    for name, fn in targets.items():
        report = profile_function(name, fn)
        report_path = output_dir / f"{name}.txt"
        report_path.write_text(report, encoding="utf-8")
        print(f"[profile] wrote {report_path}")


if __name__ == "__main__":
    main()
