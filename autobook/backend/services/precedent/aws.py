import json
import logging

from queues import sqs
from queues.pubsub import pub
from services.precedent.service import execute
from services.shared.parse_status import set_status_sync
from services.shared.routing import next_stage, should_post

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STAGE = "precedent"


def handler(event, context):
    for record in event["Records"]:
        message = json.loads(record["body"])
        try:
            set_status_sync(
                parse_id=message["parse_id"],
                user_id=message["user_id"],
                status="processing",
                stage=STAGE,
                input_text=message.get("input_text") or message.get("description"),
            )
            pub.stage_started(
                parse_id=message["parse_id"],
                user_id=message["user_id"],
                stage=STAGE,
            )
            result = execute(message)

            if should_post(STAGE, result):
                pub.stage_started(
                    parse_id=result["parse_id"],
                    user_id=result["user_id"],
                    stage="post-precedent",
                )
                sqs.enqueue.posting(result)
            else:
                if STAGE in result.get("post_stages", []):
                    pub.stage_skipped(
                        parse_id=result["parse_id"],
                        user_id=result["user_id"],
                        stage="post-precedent",
                    )
                nxt = next_stage(STAGE, result)
                if nxt:
                    sqs.enqueue.by_name(nxt, result)
                else:
                    pub.pipeline_result(
                        parse_id=result["parse_id"],
                        user_id=result["user_id"],
                        stage=STAGE,
                        result=result,
                    )
        except Exception as exc:
            logger.exception("Precedent failed for %s", message.get("parse_id"))
            if message.get("parse_id") and message.get("user_id"):
                set_status_sync(
                    parse_id=message["parse_id"],
                    user_id=message["user_id"],
                    status="failed",
                    stage=STAGE,
                    input_text=message.get("input_text") or message.get("description"),
                    error=str(exc),
                )
                pub.pipeline_error(
                    parse_id=message["parse_id"],
                    user_id=message["user_id"],
                    stage=STAGE,
                    error=str(exc),
                )
            raise
