from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import api.main as api_main
import api.routes.clarifications as clarifications_routes
import api.routes.parse as parse_routes
from auth import deps as auth_deps
from config import get_settings
from db.dao.chart_of_accounts import DEFAULT_COA
from db.dao.clarifications import ClarificationDAO
from db.dao.journal_entries import JournalEntryDAO
from db.dao.transactions import TransactionDAO
from db.models.user import User
import services.normalizer.service as normalizer_svc
import services.precedent.service as precedent_svc
import services.ml_inference.service as ml_svc
import services.posting.service as posting_svc
import services.resolution.service as resolution_svc
from services.precedent.logic import PrecedentCandidate
from services.shared import transaction_persistence


class DummyRedis:
    async def aclose(self) -> None:
        return None


class FakeDB:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def refresh(self, _obj) -> None:
        return None

    def close(self) -> None:
        return None


@dataclass
class Store:
    users_by_sub: dict[str, SimpleNamespace]
    users_by_email: dict[str, SimpleNamespace]
    external_users: dict[str, SimpleNamespace]
    transactions: dict[UUID, SimpleNamespace]
    journal_entries: dict[UUID, SimpleNamespace]
    clarifications: dict[UUID, SimpleNamespace]
    accounts: dict[UUID, list[SimpleNamespace]]


def _default_accounts(user_id: UUID) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            account_code=code,
            account_name=name,
            account_type=account_type,
        )
        for code, name, account_type in DEFAULT_COA
    ]


def _ensure_external_user(store: Store, external_user_id: str | None) -> SimpleNamespace:
    key = (external_user_id or "demo-user-1").strip() or "demo-user-1"
    for user in store.users_by_sub.values():
        if str(user.id) == key or user.cognito_sub == key or user.email == key:
            return user
    user = store.external_users.get(key)
    if user is None:
        user = SimpleNamespace(
            id=uuid4(),
            email=f"{key}@autobook.local",
            cognito_sub=key,
        )
        store.external_users[key] = user
        store.accounts[user.id] = _default_accounts(user.id)
    return user


def _make_fake_user_dao(store: Store):
    class FakeUserDAO:
        @staticmethod
        def get_or_create_from_cognito_claims(_db, cognito_sub: str, email: str | None) -> User:
            existing = store.users_by_sub.get(cognito_sub)
            if existing is not None:
                return existing
            resolved_email = email or f"{cognito_sub}@autobook.local"
            user = SimpleNamespace(
                id=uuid4(),
                cognito_sub=cognito_sub,
                email=resolved_email,
            )
            store.users_by_sub[cognito_sub] = user
            store.users_by_email[resolved_email] = user
            store.accounts[user.id] = _default_accounts(user.id)
            return user

    return FakeUserDAO


def _make_transaction_store(store: Store):
    def insert(
        db,
        user_id,
        description,
        normalized_description,
        amount,
        currency,
        date,
        source,
        counterparty,
        amount_mentions=None,
        date_mentions=None,
        party_mentions=None,
        quantity_mentions=None,
    ):
        transaction = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            description=description,
            normalized_description=normalized_description,
            amount=Decimal(str(amount)) if amount is not None else None,
            currency=currency,
            date=date,
            source=source,
            counterparty=counterparty,
            amount_mentions=amount_mentions,
            date_mentions=date_mentions,
            party_mentions=party_mentions,
            quantity_mentions=quantity_mentions,
            intent_label=None,
            entities=None,
            bank_category=None,
            cca_class_match=None,
            submitted_at=datetime.now(timezone.utc),
        )
        store.transactions[transaction.id] = transaction
        return transaction

    def get_by_id(_db, transaction_id):
        try:
            return store.transactions.get(UUID(str(transaction_id)))
        except (ValueError, TypeError):
            return None

    def update_normalized_fields(_db, transaction_id, **kwargs):
        transaction = store.transactions[transaction_id]
        for key, value in kwargs.items():
            if key == "amount" and value is not None:
                setattr(transaction, key, Decimal(str(value)))
            elif value is not None:
                setattr(transaction, key, value)
        return transaction

    def update_ml_enrichment(_db, transaction_id, intent_label, entities, bank_category, cca_class_match):
        transaction = store.transactions[transaction_id]
        transaction.intent_label = intent_label
        transaction.entities = entities
        transaction.bank_category = bank_category
        transaction.cca_class_match = cca_class_match
        return transaction

    return insert, get_by_id, update_normalized_fields, update_ml_enrichment


def _make_journal_store(store: Store):
    def insert_with_lines(_db, user_id, entry, lines):
        if not lines:
            raise ValueError("journal entry must include at least one line")

        debit_total = Decimal("0")
        credit_total = Decimal("0")
        prepared_lines = []
        for index, line in enumerate(lines):
            line_type = str(line["type"]).lower()
            amount = Decimal(str(line["amount"]))
            if line_type == "debit":
                debit_total += amount
            elif line_type == "credit":
                credit_total += amount
            else:
                raise ValueError(f"line {index} has invalid type {line_type!r}")

            prepared_lines.append(
                SimpleNamespace(
                    account_code=line["account_code"],
                    account_name=line["account_name"],
                    type=line_type,
                    amount=amount,
                    line_order=line.get("line_order", index),
                )
            )

        if debit_total != credit_total:
            raise ValueError(
                f"journal entry does not balance: debits={debit_total} credits={credit_total}"
            )

        journal_entry = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            transaction_id=entry.get("transaction_id"),
            date=entry["date"],
            description=entry["description"],
            status=entry.get("status", "posted"),
            origin_tier=entry.get("origin_tier"),
            confidence=Decimal(str(entry.get("confidence"))) if entry.get("confidence") is not None else None,
            rationale=entry.get("rationale"),
            posted_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            lines=prepared_lines,
        )
        store.journal_entries[journal_entry.id] = journal_entry
        return journal_entry

    def list_by_user(_db, user_id, filters=None):
        filters = filters or {}
        entries = [entry for entry in store.journal_entries.values() if entry.user_id == user_id]
        if filters.get("status") is not None:
            entries = [entry for entry in entries if entry.status == filters["status"]]
        if filters.get("date_to") is not None:
            entries = [entry for entry in entries if str(entry.date) <= str(filters["date_to"])]
        return sorted(entries, key=lambda item: (str(item.date), str(item.created_at)), reverse=True)

    def compute_balances(_db, user_id):
        balances: dict[str, dict[str, Decimal | str]] = {}
        account_types = {a.account_code: a.account_type for a in store.accounts[user_id]}
        account_names = {a.account_code: a.account_name for a in store.accounts[user_id]}
        for entry in list_by_user(_db, user_id, filters={"status": "posted"}):
            for line in entry.lines:
                bucket = balances.setdefault(
                    line.account_code,
                    {"account_code": line.account_code, "account_name": account_names.get(line.account_code, line.account_name), "debit": Decimal("0"), "credit": Decimal("0")},
                )
                bucket[line.type] += line.amount
        results = []
        for account_code, bucket in balances.items():
            if account_types.get(account_code) in {"asset", "expense"}:
                balance = bucket["debit"] - bucket["credit"]
            else:
                balance = bucket["credit"] - bucket["debit"]
            results.append({"account_code": account_code, "account_name": bucket["account_name"], "balance": balance})
        return sorted(results, key=lambda item: item["account_code"])

    def compute_summary(_db, user_id):
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for entry in list_by_user(_db, user_id, filters={"status": "posted"}):
            for line in entry.lines:
                if line.type == "debit":
                    total_debits += line.amount
                else:
                    total_credits += line.amount
        return {"total_debits": total_debits, "total_credits": total_credits}

    return insert_with_lines, list_by_user, compute_balances, compute_summary


def _make_clarification_store(store: Store):
    def insert(*, db=None, user_id, transaction_id, source_text, explanation, confidence, proposed_entry, verdict):
        task = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            transaction_id=transaction_id,
            source_text=source_text,
            explanation=explanation,
            confidence=Decimal(str(confidence)),
            proposed_entry=proposed_entry,
            evaluator_verdict=verdict,
            status="pending",
            created_at=datetime.now(timezone.utc),
            resolved_at=None,
        )
        store.clarifications[task.id] = task
        return task

    def list_pending(_db, user_id):
        return [t for t in store.clarifications.values() if t.user_id == user_id and t.status == "pending"]

    def resolve(_db, task_id, action, edited_entry=None):
        task = store.clarifications.get(task_id)
        if task is None:
            return None, None
        if action == "reject":
            task.status = "rejected"
            return task, None
        payload = edited_entry if edited_entry is not None else task.proposed_entry
        entry_payload = dict(payload.get("entry") or {})
        line_payload = list(payload.get("lines") or [])
        entry_payload.setdefault("transaction_id", task.transaction_id)
        entry_payload.setdefault("status", "posted")
        journal_entry = JournalEntryDAO.insert_with_lines(None, task.user_id, entry_payload, line_payload)
        task.status = "resolved"
        task.proposed_entry = {"entry": {**entry_payload, "journal_entry_id": str(journal_entry.id)}, "lines": line_payload}
        return task, journal_entry

    return insert, list_pending, resolve


def _make_precedent_loader(store: Store):
    def loader(message: dict):
        user = _ensure_external_user(store, message.get("user_id"))
        current_transaction_id = str(message.get("transaction_id") or "")
        candidates: list[PrecedentCandidate] = []
        for entry in sorted(store.journal_entries.values(), key=lambda item: item.created_at, reverse=True):
            if entry.user_id != user.id or str(entry.transaction_id or "") == current_transaction_id:
                continue
            transaction = store.transactions.get(entry.transaction_id)
            if transaction is None:
                continue
            candidates.append(
                PrecedentCandidate(
                    pattern_id=f"journal_entry:{entry.id}",
                    normalized_description=transaction.normalized_description,
                    amount=float(transaction.amount) if transaction.amount is not None else None,
                    counterparty=transaction.counterparty,
                    source=transaction.source,
                    lines=[
                        {"account_code": l.account_code, "account_name": l.account_name, "type": l.type, "amount": float(l.amount), "line_order": l.line_order}
                        for l in entry.lines
                    ],
                )
            )
        return candidates

    return loader


def _drain(queue_map: dict[str, list[dict]], settings) -> None:
    """Process all queued messages through the pipeline.

    Since routing (which queue to forward to) is now in aws.py handlers
    rather than in service execute() functions, this drain function
    implements the routing logic inline.
    """
    from accounting_engine.rules import build_rule_based_entry
    from services.shared.routing import should_post, first_stage, next_stage

    progressed = True
    while progressed:
        progressed = False

        # Normalizer
        while queue_map[settings.SQS_QUEUE_NORMALIZER]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_NORMALIZER].pop(0)
            result = normalizer_svc.execute(msg)
            nxt = first_stage(result)
            if nxt == "precedent":
                queue_map[settings.SQS_QUEUE_PRECEDENT].append(result)
            elif nxt == "ml":
                queue_map[settings.SQS_QUEUE_ML_INFERENCE].append(result)
            elif nxt == "llm":
                queue_map[settings.SQS_QUEUE_AGENT].append(result)

        # Precedent
        while queue_map[settings.SQS_QUEUE_PRECEDENT]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_PRECEDENT].pop(0)
            result = precedent_svc.execute(msg)
            if should_post("precedent", result):
                queue_map[settings.SQS_QUEUE_POSTING].append(result)
            else:
                nxt = next_stage("precedent", result)
                if nxt == "ml":
                    queue_map[settings.SQS_QUEUE_ML_INFERENCE].append(result)
                elif nxt == "llm":
                    queue_map[settings.SQS_QUEUE_AGENT].append(result)

        # ML inference
        while queue_map[settings.SQS_QUEUE_ML_INFERENCE]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_ML_INFERENCE].pop(0)
            result = ml_svc.execute(msg)
            if should_post("ml", result):
                queue_map[settings.SQS_QUEUE_POSTING].append(result)
            else:
                nxt = next_stage("ml", result)
                if nxt == "llm":
                    queue_map[settings.SQS_QUEUE_AGENT].append(result)

        # Agent (use rule engine as proxy — LLM pipeline requires live Bedrock)
        while queue_map[settings.SQS_QUEUE_AGENT]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_AGENT].pop(0)
            entry = build_rule_based_entry(msg, confidence=(msg.get("confidence") or {}).get("ml", 0.5), origin_tier=3)
            result = {
                **msg,
                "proposed_entry": entry.proposed_entry,
                "explanation": entry.explanation,
            }
            if not entry.requires_human_review:
                result["confidence"] = {**msg.get("confidence", {}), "overall": (msg.get("confidence") or {}).get("ml", 0.5)}
                result["clarification"] = {"required": False, "clarification_id": None, "reason": None, "status": None}
                queue_map[settings.SQS_QUEUE_POSTING].append(result)
            else:
                result["clarification"] = {"required": True, "clarification_id": None, "reason": entry.clarification_reason, "status": None}
                queue_map[settings.SQS_QUEUE_RESOLUTION].append(result)

        # Posting
        while queue_map[settings.SQS_QUEUE_POSTING]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_POSTING].pop(0)
            posting_svc.execute(msg)

        # Resolution
        while queue_map[settings.SQS_QUEUE_RESOLUTION]:
            progressed = True
            msg = queue_map[settings.SQS_QUEUE_RESOLUTION].pop(0)
            resolution_svc.execute(msg)


def test_local_smoke_flow_without_external_infra(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_DEMO_MODE", "true")
    get_settings.cache_clear()
    fake_db = FakeDB()
    settings = get_settings()
    queue_map: dict[str, list[dict]] = defaultdict(list)
    store = Store(
        users_by_sub={},
        users_by_email={},
        external_users={},
        transactions={},
        journal_entries={},
        clarifications={},
        accounts={},
    )

    fake_user_dao = _make_fake_user_dao(store)
    tx_insert, tx_get_by_id, tx_update_normalized, tx_update_ml = _make_transaction_store(store)
    je_insert, je_list, je_balances, je_summary = _make_journal_store(store)
    cl_insert, cl_list_pending, cl_resolve = _make_clarification_store(store)

    async def fake_get_redis(_url: str) -> DummyRedis:
        return DummyRedis()

    def fake_db_dependency():
        yield fake_db

    def noop_status_sync(**kw):
        return None

    def fake_normalization(**kwargs):
        queue_map[settings.SQS_QUEUE_NORMALIZER].append(kwargs)
        return "queued"

    # API-level patches
    monkeypatch.setattr(api_main, "get_redis", fake_get_redis)
    monkeypatch.setattr(auth_deps, "UserDAO", fake_user_dao)
    monkeypatch.setattr(auth_deps.AuthSessionDAO, "record_token", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(parse_routes.sqs.enqueue, "normalization", fake_normalization)
    monkeypatch.setattr(parse_routes, "set_status", AsyncMock())
    monkeypatch.setattr(clarifications_routes.pub, "clarification_resolved", lambda **kw: None)

    # Normalizer patches
    monkeypatch.setattr(normalizer_svc, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(normalizer_svc, "resolve_local_user", lambda _db, ext_id: _ensure_external_user(store, ext_id))
    monkeypatch.setattr(transaction_persistence, "resolve_local_user", lambda _db, ext_id: _ensure_external_user(store, ext_id))

    # Precedent patches
    monkeypatch.setattr(precedent_svc, "_load_candidates", _make_precedent_loader(store))

    # Posting patches
    monkeypatch.setattr(posting_svc, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(posting_svc, "set_status_sync", noop_status_sync)
    monkeypatch.setattr(posting_svc.pub, "entry_posted", lambda **kw: None)
    monkeypatch.setattr(posting_svc.sqs.enqueue, "flywheel", lambda msg: None)

    # Resolution patches
    monkeypatch.setattr(resolution_svc, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(resolution_svc, "set_status_sync", noop_status_sync)
    monkeypatch.setattr(resolution_svc.pub, "clarification_resolved", lambda **kw: None)
    monkeypatch.setattr(resolution_svc.sqs.enqueue, "posting", lambda msg: queue_map[settings.SQS_QUEUE_POSTING].append(msg))

    # DAO patches (shared across all services)
    monkeypatch.setattr(TransactionDAO, "insert", staticmethod(tx_insert))
    monkeypatch.setattr(TransactionDAO, "get_by_id", staticmethod(tx_get_by_id))
    monkeypatch.setattr(TransactionDAO, "update_normalized_fields", staticmethod(tx_update_normalized))
    monkeypatch.setattr(TransactionDAO, "update_ml_enrichment", staticmethod(tx_update_ml))
    monkeypatch.setattr(JournalEntryDAO, "insert_with_lines", staticmethod(je_insert))
    monkeypatch.setattr(JournalEntryDAO, "list_by_user", staticmethod(je_list))
    monkeypatch.setattr(JournalEntryDAO, "compute_balances", staticmethod(je_balances))
    monkeypatch.setattr(JournalEntryDAO, "compute_summary", staticmethod(je_summary))
    monkeypatch.setattr(ClarificationDAO, "insert", staticmethod(cl_insert))
    monkeypatch.setattr(ClarificationDAO, "list_pending", staticmethod(cl_list_pending))
    monkeypatch.setattr(ClarificationDAO, "resolve", staticmethod(cl_resolve))

    from db.dao.chart_of_accounts import ChartOfAccountsDAO
    monkeypatch.setattr(ChartOfAccountsDAO, "list_by_user", staticmethod(lambda _db, user_id: store.accounts[user_id]))

    api_main.app.dependency_overrides[auth_deps.get_db] = fake_db_dependency
    manager_headers = {"Authorization": "Bearer demo:manager@example.com"}

    with TestClient(api_main.app) as client:
        auth_me = client.get("/api/v1/auth/me", headers=manager_headers)
        assert auth_me.status_code == 200
        assert auth_me.json()["role"] == "manager"

        first_parse = client.post(
            "/api/v1/parse",
            headers=manager_headers,
            json={"input_text": "Bought a laptop from Apple for $2400", "source": "manual_text", "currency": "CAD"},
        )
        assert first_parse.status_code == 200
        _drain(queue_map, settings)

        ledger_after_first = client.get("/api/v1/ledger", headers=manager_headers)
        assert ledger_after_first.status_code == 200
        ledger_body = ledger_after_first.json()
        assert len(ledger_body["entries"]) == 1
        assert ledger_body["entries"][0]["origin_tier"] == 3

        second_parse = client.post(
            "/api/v1/parse",
            headers=manager_headers,
            json={"input_text": "Bought a laptop from Apple for $2400", "source": "manual_text", "currency": "CAD"},
        )
        assert second_parse.status_code == 200
        _drain(queue_map, settings)

        ledger_after_second = client.get("/api/v1/ledger", headers=manager_headers)
        assert ledger_after_second.status_code == 200
        second_entries = ledger_after_second.json()["entries"]
        assert len(second_entries) == 2
        assert all(entry["status"] == "posted" for entry in second_entries)

        ambiguous_parse = client.post(
            "/api/v1/parse",
            headers=manager_headers,
            json={"input_text": "Transferred $1500 to savings", "source": "manual_text", "currency": "CAD"},
        )
        assert ambiguous_parse.status_code == 200
        _drain(queue_map, settings)

        clarifications = client.get("/api/v1/clarifications", headers=manager_headers)
        assert clarifications.status_code == 200
        clarification_items = clarifications.json()["items"]
        assert len(clarification_items) == 1
        clarification_id = clarification_items[0]["clarification_id"]

        resolve = client.post(
            f"/api/v1/clarifications/{clarification_id}/resolve",
            headers=manager_headers,
            json={"action": "approve"},
        )
        assert resolve.status_code == 200

        final_ledger = client.get("/api/v1/ledger", headers=manager_headers)
        assert final_ledger.status_code == 200
        assert len(final_ledger.json()["entries"]) == 3

        statements = client.get("/api/v1/statements", headers=manager_headers)
        assert statements.status_code == 200
        assert statements.json()["statement_type"] == "balance_sheet"
        asset_rows = statements.json()["sections"][0]["rows"]
        assert any(row["label"] == "Equipment" and row["amount"] == 4800.0 for row in asset_rows)
        assert any(row["label"] == "Unknown Destination" and row["amount"] == 1500.0 for row in asset_rows)

    api_main.app.dependency_overrides.clear()
