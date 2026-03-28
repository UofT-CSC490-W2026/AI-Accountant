from __future__ import annotations

from unittest.mock import patch

from queues.sqs import enqueue


def _capture_send():
    sent = []

    def fake_send(queue_url, payload):
        sent.append((queue_url, payload))
        return "msg-id"

    return sent, fake_send


def test_enqueue_normalization():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        result = enqueue.normalization(parse_id="p1", user_id="u1", source="manual")
    assert result == "msg-id"
    assert sent[0][1]["parse_id"] == "p1"


def test_enqueue_by_name():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.by_name("precedent", {"parse_id": "p1", "user_id": "u1"})
    assert len(sent) == 1


def test_enqueue_precedent():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.precedent({"parse_id": "p1", "user_id": "u1", "transaction_id": "t1", "normalized_description": "test"})
    assert len(sent) == 1


def test_enqueue_ml_inference():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.ml_inference({"parse_id": "p1", "user_id": "u1", "transaction_id": "t1", "precedent_match": {"matched": False}})
    assert len(sent) == 1


def test_enqueue_agent():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.agent({"parse_id": "p1", "user_id": "u1"})
    assert len(sent) == 1


def test_enqueue_resolution():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.resolution({"parse_id": "p1", "user_id": "u1", "confidence": {}, "explanation": "x", "clarification": {}})
    assert len(sent) == 1


def test_enqueue_posting():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.posting({"parse_id": "p1", "user_id": "u1", "confidence": {}})
    assert len(sent) == 1


def test_enqueue_flywheel():
    sent, fake = _capture_send()
    with patch("queues.sqs.enqueue.send", fake):
        enqueue.flywheel({"parse_id": "p1", "user_id": "u1", "transaction_id": "t1", "journal_entry_id": "j1"})
    assert len(sent) == 1
