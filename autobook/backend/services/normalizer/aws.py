import json
import logging

from queues import sqs
from queues.pubsub import pub
from services.normalizer.service import execute
from services.shared.parse_status import set_status_sync
from services.shared.routing import first_stage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    for record in event["Records"]:
        message = json.loads(record["body"])
        try:
            set_status_sync(
                parse_id=message["parse_id"],
                user_id=message["user_id"],
                status="processing",
                stage="normalizer",
                input_text=message.get("input_text") or message.get("filename"),
            )
            pub.stage_started(
                parse_id=message["parse_id"],
                user_id=message["user_id"],
                stage="normalizer",
            )
            result = execute(message)

            nxt = first_stage(result)
            if nxt:
                sqs.enqueue.by_name(nxt, result)
            else:
                pub.pipeline_result(
                    parse_id=result["parse_id"],
                    user_id=result["user_id"],
                    stage="normalizer",
                    result=result,
                )
        except Exception as exc:
            logger.exception("Normalizer failed for %s", message.get("parse_id"))
            if message.get("parse_id") and message.get("user_id"):
                set_status_sync(
                    parse_id=message["parse_id"],
                    user_id=message["user_id"],
                    status="failed",
                    stage="normalizer",
                    input_text=message.get("input_text") or message.get("filename"),
                    error=str(exc),
                )
                pub.pipeline_error(
                    parse_id=message["parse_id"],
                    user_id=message["user_id"],
                    stage="normalizer",
                    error=str(exc),
                )
            raise
