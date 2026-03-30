from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.dao.chart_of_accounts import ChartOfAccountsDAO, DEFAULT_COA
from db.connection import set_current_user_context
from db.models.account import ChartOfAccounts
from db.models.journal import JournalEntry, JournalLine


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _infer_account_type(account_code: str) -> str:
    for default_code, _, account_type in DEFAULT_COA:
        if default_code == account_code:
            return account_type
    prefix = (account_code or "")[:1]
    return {
        "1": "asset",
        "2": "liability",
        "3": "equity",
        "4": "revenue",
    }.get(prefix, "expense")


class JournalEntryDAO:
    @staticmethod
    def insert_with_lines(
        db: Session,
        user_id,
        entry: Mapping[str, object],
        lines: Sequence[Mapping[str, object]],
    ) -> JournalEntry:
        set_current_user_context(db, user_id)
        ChartOfAccountsDAO.seed_defaults(db, user_id)
        if not lines:
            raise ValueError("journal entry must include at least one line")

        debit_total = Decimal("0")
        credit_total = Decimal("0")
        prepared_lines: list[JournalLine] = []

        for index, line in enumerate(lines):
            line_type = str(line["type"]).lower()
            if line_type not in {"debit", "credit"}:
                raise ValueError(f"line {index} has invalid type {line_type!r}")
            amount = _to_decimal(line["amount"])
            if amount <= 0:
                raise ValueError(f"line {index} amount must be positive")

            account_code = str(line["account_code"])
            account = db.execute(
                select(ChartOfAccounts).where(
                    ChartOfAccounts.user_id == user_id,
                    ChartOfAccounts.account_code == account_code,
                )
            ).scalar_one_or_none()
            if account is None:
                raise ValueError(f"unknown account code {account_code!r} for user {user_id}")

            if line_type == "debit":
                debit_total += amount
            else:
                credit_total += amount

            prepared_lines.append(
                JournalLine(
                    account_code=account.account_code,
                    account_name=str(line.get("account_name") or account.account_name),
                    type=line_type,
                    amount=amount,
                    line_order=int(line.get("line_order", index)),
                )
            )

        if debit_total != credit_total:
            raise ValueError(
                f"journal entry does not balance: debits={debit_total} credits={credit_total}"
            )

        status = str(entry.get("status", "draft")).lower()
        if status not in {"draft", "posted"}:
            raise ValueError(f"invalid journal entry status {status!r}")

        posted_at = entry.get("posted_at")
        if status == "posted" and posted_at is None:
            posted_at = datetime.now(timezone.utc)

        entry_date = entry["date"]
        if isinstance(entry_date, str):
            entry_date = date.fromisoformat(entry_date)

        journal_entry = JournalEntry(
            user_id=user_id,
            transaction_id=entry.get("transaction_id"),
            date=entry_date,
            description=str(entry["description"]),
            status=status,
            origin_tier=entry.get("origin_tier"),
            confidence=entry.get("confidence"),
            rationale=entry.get("rationale"),
            posted_at=posted_at,
            lines=prepared_lines,
        )
        db.add(journal_entry)
        db.flush()
        return journal_entry

    @staticmethod
    def list_by_user(db: Session, user_id, filters: Mapping[str, object] | None = None) -> list[JournalEntry]:
        set_current_user_context(db, user_id)
        filters = filters or {}
        stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.date.desc(), JournalEntry.created_at.desc())
        )
        if filters.get("date_from") is not None:
            stmt = stmt.where(JournalEntry.date >= filters["date_from"])
        if filters.get("date_to") is not None:
            stmt = stmt.where(JournalEntry.date <= filters["date_to"])
        if filters.get("status") is not None:
            stmt = stmt.where(JournalEntry.status == filters["status"])
        if filters.get("account") is not None:
            stmt = stmt.join(JournalEntry.lines).where(
                JournalLine.account_code == filters["account"]
            )
        return list(db.execute(stmt).scalars().unique().all())

    @staticmethod
    def get_by_id(db: Session, journal_entry_id) -> JournalEntry | None:
        stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.id == journal_entry_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def compute_balances(
        db: Session,
        user_id,
        filters: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]:
        set_current_user_context(db, user_id)
        filters = {"status": "posted", **(filters or {})}
        account_lookup = {
            account.account_code: account
            for account in ChartOfAccountsDAO.list_by_user(db, user_id)
        }
        stmt = (
            select(
                JournalLine.account_code,
                func.max(JournalLine.account_name),
                JournalLine.type,
                func.sum(JournalLine.amount),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(
                JournalEntry.user_id == user_id,
            )
            .group_by(
                JournalLine.account_code,
                JournalLine.type,
            )
        )
        if filters.get("date_from") is not None:
            stmt = stmt.where(JournalEntry.date >= filters["date_from"])
        if filters.get("date_to") is not None:
            stmt = stmt.where(JournalEntry.date <= filters["date_to"])
        if filters.get("status") is not None:
            stmt = stmt.where(JournalEntry.status == filters["status"])
        grouped: dict[str, dict[str, object]] = {}
        for account_code, account_name, line_type, total in db.execute(stmt):
            normalized_line_type = str(line_type or "").strip().lower()
            if normalized_line_type not in {"debit", "credit"}:
                continue
            account = account_lookup.get(account_code)
            bucket = grouped.setdefault(
                account_code,
                {
                    "account_code": account_code,
                    "account_name": (account.account_name if account is not None else account_name) or account_code,
                    "account_type": account.account_type if account is not None else _infer_account_type(str(account_code)),
                    "debit_total": Decimal("0"),
                    "credit_total": Decimal("0"),
                },
            )
            bucket[f"{normalized_line_type}_total"] = _to_decimal(total or 0)

        balances: list[dict[str, object]] = []
        for account in grouped.values():
            debit_total = _to_decimal(account["debit_total"])
            credit_total = _to_decimal(account["credit_total"])
            account_type = str(account["account_type"]).strip().lower()
            if account_type in {"asset", "expense"}:
                balance = debit_total - credit_total
            else:
                balance = credit_total - debit_total
            balances.append(
                {
                    "account_code": account["account_code"],
                    "account_name": account["account_name"],
                    "account_type": account_type,
                    "debit_total": debit_total,
                    "credit_total": credit_total,
                    "balance": balance,
                }
            )
        return sorted(balances, key=lambda item: str(item["account_code"]))

    @staticmethod
    def compute_summary(
        db: Session,
        user_id,
        filters: Mapping[str, object] | None = None,
    ) -> dict[str, Decimal]:
        set_current_user_context(db, user_id)
        filters = {"status": "posted", **(filters or {})}
        stmt = (
            select(JournalLine.type, func.sum(JournalLine.amount))
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalEntry.user_id == user_id)
            .group_by(JournalLine.type)
        )
        if filters.get("date_from") is not None:
            stmt = stmt.where(JournalEntry.date >= filters["date_from"])
        if filters.get("date_to") is not None:
            stmt = stmt.where(JournalEntry.date <= filters["date_to"])
        if filters.get("status") is not None:
            stmt = stmt.where(JournalEntry.status == filters["status"])
        totals = {"total_debits": Decimal("0"), "total_credits": Decimal("0")}
        for line_type, amount in db.execute(stmt):
            normalized_line_type = str(line_type or "").strip().lower()
            if normalized_line_type not in {"debit", "credit"}:
                continue
            key = "total_debits" if normalized_line_type == "debit" else "total_credits"
            totals[key] = _to_decimal(amount or 0)
        return totals
