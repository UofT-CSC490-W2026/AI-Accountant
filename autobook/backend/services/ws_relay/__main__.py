"""WS Relay Service — bridges Redis pub/sub to API Gateway WebSocket clients.

Subscribes to Redis channels and pushes events to all connected WebSocket
clients via the API Gateway Management API (postToConnection).
"""

import json
import logging
import os

import boto3
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ws-relay")

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved")


def main():
    redis_url = os.environ["REDIS_URL"]
    table_name = os.environ["WS_CONNECTIONS_TABLE"]
    apigw_endpoint = os.environ["WS_API_ENDPOINT"]

    logger.info("Starting WS Relay — Redis: %s, Table: %s, API GW: %s", redis_url, table_name, apigw_endpoint)

    r = redis.from_url(redis_url, decode_responses=True)
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=apigw_endpoint)

    pubsub = r.pubsub()
    pubsub.subscribe(*CHANNELS)
    logger.info("Subscribed to channels: %s", CHANNELS)

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        data = message["data"]
        logger.info("Event on channel %s: %s", message["channel"], data[:100])

        # Get all connected clients
        connections = table.scan(ProjectionExpression="connectionId")
        items = connections.get("Items", [])

        # Push to each client
        stale = []
        for item in items:
            conn_id = item["connectionId"]
            try:
                apigw.post_to_connection(ConnectionId=conn_id, Data=data.encode("utf-8"))
            except apigw.exceptions.GoneException:
                logger.info("Stale connection %s — removing", conn_id)
                stale.append(conn_id)
            except Exception:
                logger.exception("Failed to post to %s", conn_id)

        # Clean up stale connections
        for conn_id in stale:
            table.delete_item(Key={"connectionId": conn_id})


if __name__ == "__main__":
    main()
