import logging
import os

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["WS_CONNECTIONS_TABLE"])


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    logger.info("WebSocket disconnect: %s", connection_id)
    table.delete_item(Key={"connectionId": connection_id})
    return {"statusCode": 200}
