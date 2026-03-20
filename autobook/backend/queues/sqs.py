import json
import logging

import boto3

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
sqs = boto3.client(
    "sqs",
    region_name=settings.AWS_DEFAULT_REGION,
    **({"endpoint_url": settings.SQS_ENDPOINT_URL} if settings.SQS_ENDPOINT_URL else {}),
)


def enqueue(queue_url: str, payload: dict) -> str:
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload),
    )
    return response["MessageId"]


def dequeue(queue_url: str, wait_seconds: int = 20) -> dict | None:
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
    )
    messages = response.get("Messages", [])
    if not messages:
        return None

    msg = messages[0]
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
    return json.loads(msg["Body"])
