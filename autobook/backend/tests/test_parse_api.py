from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import parse as parse_route


def create_client() -> TestClient:
    app = FastAPI()
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
            "user_id": "demo-user-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["user_id"] == "demo-user-1"
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
        data={"user_id": "demo-user-1", "source": "csv_upload"},
        files={"file": ("march-bank.csv", b"date,description,amount", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["source"] == "csv_upload"
    assert captured[0][1]["filename"] == "march-bank.csv"
    assert captured[0][1]["user_id"] == "demo-user-1"


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
        data={"user_id": "demo-user-1"},
        files={"file": ("invoice-demo.pdf", b"fake-pdf-bytes", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["source"] == "pdf_upload"
    assert captured[0][1]["filename"] == "invoice-demo.pdf"
