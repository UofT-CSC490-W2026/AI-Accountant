from __future__ import annotations

import argparse
import pandas as pd

from common.ids import stable_txn_id
from common.schemas.transactions import CanonicalTransaction

REQUIRED_COLUMNS = {"date", "description", "amount"}

# A5 deep-test rationale for this module:
# - `test_normalize_text_*` covers whitespace normalization and null-like inputs because
#   free-form exports often contain inconsistent spacing or missing descriptions.
# - `test_normalize_columns_*` and `test_validate_required_columns_*` cover header cleanup
#   and schema failure modes because third-party CSV exports vary in casing and spacing.
# - `test_clean_transactions_dataframe_*` covers invalid dates, invalid amounts, and blank
#   descriptions because these are the most common row-level data quality failures.
# - `test_build_canonical_records_*` covers ID determinism and normalized descriptions because
#   downstream deduplication and ledger joins rely on stable IDs and canonical text.
# - `test_run_*` covers end-to-end output writing, deduplication, and metadata propagation
#   because those behaviors define the contract this batch job has with the rest of the system.


def normalize_text(s: str | None) -> str:
    s = (s or "").strip()
    s = " ".join(s.split())  # collapse repeated whitespace
    return s


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(c).lower().strip() for c in normalized.columns]
    return normalized


def validate_required_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. "
                         f"Expected at least {sorted(REQUIRED_COLUMNS)} (case-insensitive).")


def clean_transactions_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = normalize_columns(df)
    validate_required_columns(cleaned)

    # Normalize free-form fields before parsing types so invalid rows can be dropped consistently.
    cleaned["description"] = cleaned["description"].astype(str).map(normalize_text)
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce").dt.date
    cleaned["amount"] = pd.to_numeric(cleaned["amount"], errors="coerce")

    cleaned = cleaned.dropna(subset=["date", "amount"])
    cleaned = cleaned[cleaned["description"] != ""]
    return cleaned.reset_index(drop=True)


def build_canonical_records(
    df: pd.DataFrame,
    source_system: str,
    currency: str,
) -> list[dict]:
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
    return records


def deduplicate_records(records: list[dict]) -> pd.DataFrame:
    out = pd.DataFrame.from_records(records)
    if out.empty:
        return out
    return out.drop_duplicates(subset=["transaction_id"], keep="first").reset_index(drop=True)


def run(input_csv: str, output_parquet: str, source_system: str, currency: str) -> None:
    raw_df = pd.read_csv(input_csv)
    cleaned_df = clean_transactions_dataframe(raw_df)
    records = build_canonical_records(cleaned_df, source_system, currency)
    out = deduplicate_records(records)

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
