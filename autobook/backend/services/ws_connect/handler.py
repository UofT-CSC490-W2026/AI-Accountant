import logging
import os

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["WS_CONNECTIONS_TABLE"])


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    query_params = event.get("queryStringParameters") or {}
    user_id = query_params.get("userId", "anonymous")
    logger.info("WebSocket connect: %s (user: %s)", connection_id, user_id)
    table.put_item(Item={"connectionId": connection_id, "userId": user_id})
    return {"statusCode": 200}
