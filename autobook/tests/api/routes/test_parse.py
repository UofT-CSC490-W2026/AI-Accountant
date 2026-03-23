from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import parse as parse_route
from auth.schemas import UserRole


def create_client() -> TestClient:
    app = FastAPI()
    fake_auth_context = SimpleNamespace(
        user=SimpleNamespace(id="user-auth-1"),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="default",
    )
    app.dependency_overrides[parse_route.get_current_user] = lambda: fake_auth_context
    app.include_router(parse_route.router)
    return TestClient(app)


def test_parse_enqueues_manual_input_with_user_id(monkeypatch):
    client = create_client()
    captured: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        parse_route,
        "enqueue",
        lambda queue_url, payload: captured.append((queue_url, payload)),
    )

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
    assert captured[0][1]["user_id"] == "user-auth-1"
    assert captured[0][1]["input_text"] == "Paid contractor 600"


def test_parse_upload_enqueues_filename_user_id_and_explicit_source(monkeypatch):
    client = create_client()
    captured: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        parse_route,
        "enqueue",
        lambda queue_url, payload: captured.append((queue_url, payload)),
    )

    response = client.post(
        "/api/v1/parse/upload",
        data={"source": "csv_upload"},
        files={"file": ("march-bank.csv", b"date,description,amount", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["source"] == "csv_upload"
    assert captured[0][1]["filename"] == "march-bank.csv"
    assert captured[0][1]["user_id"] == "user-auth-1"


def test_parse_upload_inferrs_pdf_source_when_metadata_missing(monkeypatch):
    client = create_client()
    captured: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        parse_route,
        "enqueue",
        lambda queue_url, payload: captured.append((queue_url, payload)),
    )

    response = client.post(
        "/api/v1/parse/upload",
        files={"file": ("invoice-demo.pdf", b"fake-pdf-bytes", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["source"] == "pdf_upload"
    assert captured[0][1]["filename"] == "invoice-demo.pdf"
