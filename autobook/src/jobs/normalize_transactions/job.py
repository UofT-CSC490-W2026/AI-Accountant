from __future__ import annotations

import argparse
from datetime import datetime
import pandas as pd

from common.ids import stable_txn_id
from common.schemas.transactions import CanonicalTransaction


def normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = " ".join(s.split())  # collapse repeated whitespace
    return s


def run(input_csv: str, output_parquet: str, source_system: str, currency: str) -> None:
    df = pd.read_csv(input_csv)

    # ---- Minimal schema mapping (you will expand per bank export) ----
    # Expected columns (example): date, description, amount
    # If your CSV differs, adapt the mapping here.
    required = {"date", "description", "amount"}
    missing = required - set(c.lower() for c in df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. "
                         f"Expected at least {sorted(required)} (case-insensitive).")

    # Normalize column names to lowercase
    df.columns = [c.lower().strip() for c in df.columns]

    # Cleaning / normalization
    df["description"] = df["description"].astype(str).map(normalize_text)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Drop rows with invalid critical fields
    df = df.dropna(subset=["date", "amount", "description"])

    # Build canonical records
    records = []
    for _, row in df.iterrows():
        raw_desc = row["description"]
        norm_desc = raw_desc.lower()

        txn_id = stable_txn_id(
            source_system,
            str(row["date"]),
            f"{float(row['amount']):.2f}",
            raw_desc,
        )

        tx = CanonicalTransaction(
            transaction_id=txn_id,
            raw_description=raw_desc,
            normalized_description=norm_desc,
            amount=float(row["amount"]),
            currency=currency,
            transaction_date=row["date"],
            counterparty=None,
            source_system=source_system,
        )
        records.append(tx.model_dump())

    out = pd.DataFrame.from_records(records)

    # Deduplicate by stable transaction_id
    out = out.drop_duplicates(subset=["transaction_id"], keep="first")

    # Write Parquet (good for data lake)
    out.to_parquet(output_parquet, index=False)
    print(f"[normalize] wrote {len(out)} records to {output_parquet}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to raw bank CSV")
    p.add_argument("--output", required=True, help="Path to output parquet")
    p.add_argument("--source-system", default="bank_csv")
    p.add_argument("--currency", default="CAD")
    args = p.parse_args()

    run(args.input, args.output, args.source_system, args.currency)


if __name__ == "__main__":
    main()
