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
            "source": "manual",
            "currency": "CAD",
            "user_id": "demo-user-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["user_id"] == "demo-user-1"
    assert captured[0][1]["input_text"] == "Paid contractor 600"


def test_parse_upload_enqueues_filename_and_user_id(monkeypatch):
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
        files={"file": ("receipt-demo.png", b"fake-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured[0][1]["source"] == "upload"
    assert captured[0][1]["filename"] == "receipt-demo.png"
    assert captured[0][1]["user_id"] == "demo-user-1"
