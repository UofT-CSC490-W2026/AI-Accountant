import json
import logging

from queues import sqs
from queues.pubsub import pub
from services.precedent_v2.service import execute
from services.shared.parse_status import record_batch_result_sync, set_status_sync
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
                    if result.get("parent_parse_id"):
                        record_batch_result_sync(
                            parent_parse_id=result["parent_parse_id"],
                            child_parse_id=result["parse_id"],
                            user_id=result["user_id"],
                            statement_index=int(result.get("statement_index") or 0),
                            total_statements=int(result.get("statement_total") or 1),
                            status="resolved",
                            input_text=result.get("input_text"),
                        )
                    pub.pipeline_result(
                        parse_id=result["parse_id"],
                        user_id=result["user_id"],
                        stage=STAGE,
                        result=result,
                    )
        except Exception as exc:  # pragma: no cover
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
                if message.get("parent_parse_id"):
                    record_batch_result_sync(
                        parent_parse_id=message["parent_parse_id"],
                        child_parse_id=message["parse_id"],
                        user_id=message["user_id"],
                        statement_index=int(message.get("statement_index") or 0),
                        total_statements=int(message.get("statement_total") or 1),
                        status="failed",
                        input_text=message.get("input_text") or message.get("description"),
                        error=str(exc),
                    )
            raise
