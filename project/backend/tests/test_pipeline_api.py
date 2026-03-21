from __future__ import annotations


def create_user(client):
    response = client.post(
        "/api/users/",
        json={"email": "demo@example.com", "password_hash": "fake-hash"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_user_creation_seeds_default_accounts(client):
    user = create_user(client)

    response = client.get("/api/accounts/", params={"user_id": user["id"]})
    assert response.status_code == 200, response.text
    accounts = response.json()

    assert len(accounts) == 20
    assert any(account["account_code"] == "1000" for account in accounts)
    assert any(account["account_code"] == "1500" for account in accounts)


def test_transaction_journal_and_ledger_flow(client):
    user = create_user(client)

    transaction = client.post(
        "/api/transactions/",
        json={
            "user_id": user["id"],
            "description": "Bought a laptop for business",
            "amount": 2400.0,
            "currency": "CAD",
            "date": "2026-03-21",
            "source": "manual",
            "counterparty": "Best Buy",
        },
    )
    assert transaction.status_code == 201, transaction.text
    transaction_id = transaction.json()["id"]

    enriched = client.patch(
        f"/api/transactions/{transaction_id}/ml-enrichment",
        json={
            "intent_label": "equipment_purchase",
            "entities": {"vendor": "Best Buy"},
            "bank_category": "office_equipment",
            "cca_class_match": "50",
        },
    )
    assert enriched.status_code == 200, enriched.text
    assert enriched.json()["intent_label"] == "equipment_purchase"

    journal_entry = client.post(
        "/api/journal-entries/",
        json={
            "user_id": user["id"],
            "transaction_id": transaction_id,
            "date": "2026-03-21",
            "description": "Bought a laptop for business",
            "status": "posted",
            "origin_tier": 4,
            "confidence": 1.0,
            "rationale": "integration test",
            "lines": [
                {"account_code": "1500", "type": "debit", "amount": 2400.0},
                {"account_code": "1000", "type": "credit", "amount": 2400.0},
            ],
        },
    )
    assert journal_entry.status_code == 201, journal_entry.text

    ledger = client.get("/api/ledger/", params={"user_id": user["id"]})
    assert ledger.status_code == 200, ledger.text
    payload = ledger.json()

    assert len(payload["entries"]) == 1
    assert payload["summary"]["total_debits"] == "2400.00"
    assert payload["summary"]["total_credits"] == "2400.00"
    balances = {row["account_code"]: row["balance"] for row in payload["balances"]}
    assert balances["1500"] == "2400.00"
    assert balances["1000"] == "-2400.00"


def test_clarification_resolution_posts_entry(client):
    user = create_user(client)

    transaction = client.post(
        "/api/transactions/",
        json={
            "user_id": user["id"],
            "description": "Transferred money",
            "amount": 1500.0,
            "currency": "CAD",
            "date": "2026-03-21",
            "source": "manual",
            "counterparty": None,
        },
    )
    assert transaction.status_code == 201, transaction.text
    transaction_id = transaction.json()["id"]

    clarification = client.post(
        "/api/clarifications/",
        json={
            "user_id": user["id"],
            "transaction_id": transaction_id,
            "source_text": "Transferred money",
            "explanation": "Need destination account",
            "confidence": 0.62,
            "verdict": "fixable",
            "proposed_entry": {
                "date": "2026-03-21",
                "description": "Transfer resolved",
                "status": "posted",
                "origin_tier": 4,
                "confidence": 1.0,
                "rationale": "clarification resolved",
                "lines": [
                    {"account_code": "1500", "type": "debit", "amount": 1500.0},
                    {"account_code": "1000", "type": "credit", "amount": 1500.0},
                ],
            },
        },
    )
    assert clarification.status_code == 201, clarification.text
    task_id = clarification.json()["id"]

    pending = client.get("/api/clarifications/pending", params={"user_id": user["id"]})
    assert pending.status_code == 200
    assert len(pending.json()) == 1

    resolved = client.post(
        f"/api/clarifications/{task_id}/resolve",
        json={"action": "approve"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    ledger = client.get("/api/ledger/", params={"user_id": user["id"]})
    assert ledger.status_code == 200
    assert len(ledger.json()["entries"]) == 1


def test_posted_entry_is_immutable_via_api_side_effect_free_check(client):
    user = create_user(client)
    journal_entry = client.post(
        "/api/journal-entries/",
        json={
            "user_id": user["id"],
            "date": "2026-03-21",
            "description": "Initial posted entry",
            "status": "posted",
            "lines": [
                {"account_code": "1500", "type": "debit", "amount": 10.0},
                {"account_code": "1000", "type": "credit", "amount": 10.0},
            ],
        },
    )
    assert journal_entry.status_code == 201, journal_entry.text

    entry_id = journal_entry.json()["id"]
    fetched = client.get(f"/api/journal-entries/{entry_id}")
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Initial posted entry"


def test_users_are_isolated(client):
    user_one = create_user(client)
    response = client.post(
        "/api/users/",
        json={"email": "other@example.com", "password_hash": "fake-hash"},
    )
    assert response.status_code == 201, response.text
    user_two = response.json()

    created = client.post(
        "/api/journal-entries/",
        json={
            "user_id": user_one["id"],
            "date": "2026-03-21",
            "description": "User one entry",
            "status": "posted",
            "lines": [
                {"account_code": "1500", "type": "debit", "amount": 50.0},
                {"account_code": "1000", "type": "credit", "amount": 50.0},
            ],
        },
    )
    assert created.status_code == 201, created.text

    user_one_ledger = client.get("/api/ledger/", params={"user_id": user_one["id"]})
    user_two_ledger = client.get("/api/ledger/", params={"user_id": user_two["id"]})

    assert len(user_one_ledger.json()["entries"]) == 1
    assert len(user_two_ledger.json()["entries"]) == 0
