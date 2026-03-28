from __future__ import annotations

from unittest.mock import patch

from queues.sqs import dequeue


def test_dequeue_normalization():
    with patch("queues.sqs.dequeue.receive", return_value={"parse_id": "p1"}):
        result = dequeue.normalization(wait_seconds=0)
    assert result["parse_id"] == "p1"


def test_dequeue_precedent():
    with patch("queues.sqs.dequeue.receive", return_value=None):
        assert dequeue.precedent(wait_seconds=0) is None


def test_dequeue_ml_inference():
    with patch("queues.sqs.dequeue.receive", return_value={"x": 1}):
        assert dequeue.ml_inference(wait_seconds=0) == {"x": 1}


def test_dequeue_agent():
    with patch("queues.sqs.dequeue.receive", return_value=None):
        assert dequeue.agent(wait_seconds=0) is None


def test_dequeue_resolution():
    with patch("queues.sqs.dequeue.receive", return_value=None):
        assert dequeue.resolution(wait_seconds=0) is None


def test_dequeue_posting():
    with patch("queues.sqs.dequeue.receive", return_value=None):
        assert dequeue.posting(wait_seconds=0) is None


def test_dequeue_flywheel():
    with patch("queues.sqs.dequeue.receive", return_value=None):
        assert dequeue.flywheel(wait_seconds=0) is None
