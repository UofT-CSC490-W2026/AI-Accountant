import json
import logging

from services.normalizer.process import process

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    for record in event["Records"]:
        process(json.loads(record["body"]))
