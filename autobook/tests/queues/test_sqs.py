from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from queues.sqs.client import send, receive


@pytest.fixture
def sqs_queue():
    with mock_aws():
        client = boto3.client("sqs", region_name="ca-central-1")
        queue = client.create_queue(QueueName="test-queue")
        queue_url = queue["QueueUrl"]
        yield client, queue_url


def test_sqs_enqueue(sqs_queue, monkeypatch):
    client, queue_url = sqs_queue
    monkeypatch.setattr("queues.sqs.client._client", client)

    msg_id = send(queue_url, {"parse_id": "p1"})
    assert msg_id is not None

    resp = client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    body = json.loads(resp["Messages"][0]["Body"])
    assert body["parse_id"] == "p1"


def test_sqs_dequeue_empty(sqs_queue, monkeypatch):
    client, queue_url = sqs_queue
    monkeypatch.setattr("queues.sqs.client._client", client)

    result = receive(queue_url, wait_seconds=0)
    assert result is None


def test_sqs_dequeue_message(sqs_queue, monkeypatch):
    client, queue_url = sqs_queue
    monkeypatch.setattr("queues.sqs.client._client", client)

    client.send_message(QueueUrl=queue_url, MessageBody=json.dumps({"parse_id": "p2"}))
    result = receive(queue_url, wait_seconds=0)
    assert result is not None
    assert result["parse_id"] == "p2"
