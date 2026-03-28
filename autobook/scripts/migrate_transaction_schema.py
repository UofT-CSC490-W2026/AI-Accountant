from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from db.connection import engine


def build_migration_plan(dialect_name: str, existing_columns: set[str]) -> list[str]:
    statements: list[str] = []

    if dialect_name != "postgresql":
        raise ValueError(
            "transaction schema migration currently supports PostgreSQL only; "
            f"got {dialect_name!r}"
        )

    if "amount_mentions" not in existing_columns:
        statements.append("ALTER TABLE transactions ADD COLUMN amount_mentions JSONB")
    if "date_mentions" not in existing_columns:
        statements.append("ALTER TABLE transactions ADD COLUMN date_mentions JSONB")
    if "party_mentions" not in existing_columns:
        statements.append("ALTER TABLE transactions ADD COLUMN party_mentions JSONB")
    if "quantity_mentions" not in existing_columns:
        statements.append("ALTER TABLE transactions ADD COLUMN quantity_mentions JSONB")

    # Safe to run multiple times on PostgreSQL.
    statements.append("ALTER TABLE transactions ALTER COLUMN amount DROP NOT NULL")

    return statements


def migrate_transactions_schema() -> list[str]:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "transactions" not in table_names:
        raise RuntimeError("transactions table does not exist; initialize the schema first")

    existing_columns = {column["name"] for column in inspector.get_columns("transactions")}
    statements = build_migration_plan(engine.dialect.name, existing_columns)

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    return statements


def main() -> None:
    statements = migrate_transactions_schema()
    if statements:
        print("Applied transaction schema migration:")
        for statement in statements:
            print(f"- {statement}")
    else:
        print("No transaction schema changes were needed.")


if __name__ == "__main__":
    main()
