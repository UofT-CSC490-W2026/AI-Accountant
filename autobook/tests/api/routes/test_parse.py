from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import parse as parse_route
from auth.schemas import UserRole


def create_client() -> TestClient:
    app = FastAPI()
    app.state.redis = SimpleNamespace()
    fake_auth_context = SimpleNamespace(
        user=SimpleNamespace(id="user-auth-1"),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="default",
    )
    app.dependency_overrides[parse_route.get_current_user] = lambda: fake_auth_context
    app.include_router(parse_route.router)
    return TestClient(app)


def test_parse_enqueues_manual_input_with_default_pipeline_settings(monkeypatch):
    client = create_client()
    captured: list[dict] = []

    async def fake_set_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        parse_route.sqs.enqueue,
        "normalization",
        lambda **payload: captured.append(payload),
    )
    monkeypatch.setattr(parse_route, "set_status", fake_set_status)

    response = client.post(
        "/api/v1/parse",
        json={
            "input_text": "Paid contractor 600",
            "source": "manual_text",
            "currency": "CAD",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["statement_count"] == 1
    assert captured[0]["user_id"] == "user-auth-1"
    assert captured[0]["input_text"] == "Paid contractor 600"
    assert captured[0]["stages"] == ["precedent", "ml", "llm"]
    assert captured[0]["store"] is True
    assert captured[0]["post_stages"] == ["precedent", "ml", "llm"]


def test_parse_splits_semicolon_delimited_input_into_statement_batch(monkeypatch):
    client = create_client()
    captured: list[dict] = []
    statuses: list[dict] = []

    async def fake_set_status(*_args, **kwargs):
        statuses.append(kwargs)
        return None

    monkeypatch.setattr(
        parse_route.sqs.enqueue,
        "normalization",
        lambda **payload: captured.append(payload),
    )
    monkeypatch.setattr(parse_route, "set_status", fake_set_status)

    response = client.post(
        "/api/v1/parse",
        json={
            "input_text": "Bought a laptop for $2400; Paid rent $2000",
            "source": "manual_text",
            "currency": "CAD",
        },
    )

    assert response.status_code == 200
    assert response.json()["statement_count"] == 2
    assert len(captured) == 2
    assert captured[0]["parse_id"].endswith("_s1")
    assert captured[0]["parent_parse_id"] == response.json()["parse_id"]
    assert captured[0]["input_text"] == "Bought a laptop for $2400"
    assert captured[1]["input_text"] == "Paid rent $2000"
    assert statuses[0]["batch"]["total_statements"] == 2


def test_parse_upload_enqueues_filename_user_id_and_pipeline_options(monkeypatch):
    client = create_client()
    captured: list[dict] = []

    async def fake_set_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        parse_route.sqs.enqueue,
        "normalization",
        lambda **payload: captured.append(payload),
    )
    monkeypatch.setattr(parse_route, "set_status", fake_set_status)

    response = client.post(
        "/api/v1/parse/upload",
        data={
            "source": "csv_upload",
            "store": "true",
            "stages": ["precedent", "ml", "llm"],
            "post_stages": ["precedent", "ml", "llm"],
        },
        files={
            "file": (
                "march-bank.csv",
                b"description,amount,currency\nBought a laptop,2400,CAD\nPaid rent,2000,CAD\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["statement_count"] == 2
    assert len(captured) == 2
    assert captured[0]["source"] == "csv_upload"
    assert captured[0]["filename"] == "march-bank.csv"
    assert captured[0]["user_id"] == "user-auth-1"
    assert captured[0]["stages"] == ["precedent", "ml", "llm"]
    assert captured[0]["post_stages"] == ["precedent", "ml", "llm"]
    assert captured[0]["input_text"] == "Bought a laptop for $2400"
    assert captured[0]["amount"] == 2400.0
    assert captured[1]["input_text"] == "Paid rent for $2000"


def test_parse_upload_infers_pdf_source_when_metadata_missing(monkeypatch):
    client = create_client()
    captured: list[dict] = []

    async def fake_set_status(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        parse_route.sqs.enqueue,
        "normalization",
        lambda **payload: captured.append(payload),
    )
    monkeypatch.setattr(parse_route, "set_status", fake_set_status)

    response = client.post(
        "/api/v1/parse/upload",
        files={
            "file": (
                "invoice-demo.pdf",
                b"%PDF-1.4\nBT\n(Bought a laptop for $2400) Tj\nET\nBT\n(Paid rent $2000) Tj\nET",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["statement_count"] == 2
    assert captured[0]["source"] == "pdf_upload"
    assert captured[0]["filename"] == "invoice-demo.pdf"
    assert captured[0]["post_stages"] == ["precedent", "ml", "llm"]
    assert captured[0]["input_text"] == "Bought a laptop for $2400"
    assert captured[1]["input_text"] == "Paid rent $2000"
