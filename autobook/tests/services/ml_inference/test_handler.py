from __future__ import annotations

import json
from unittest.mock import patch

from services.ml_inference.aws import handler


def test_handler_delegates():
    processed = []

    def fake_execute(msg):
        processed.append(msg)
        return {**msg, "parse_id": msg["parse_id"], "user_id": msg["user_id"], "post_stages": []}

    with patch("services.ml_inference.aws.execute", side_effect=fake_execute), \
         patch("services.ml_inference.aws.set_status_sync"), \
         patch("services.ml_inference.aws.pub"), \
         patch("services.ml_inference.aws.should_post", return_value=False), \
         patch("services.ml_inference.aws.next_stage", return_value=None), \
         patch("services.ml_inference.aws.sqs"):
        handler(
            {"Records": [{"body": json.dumps({"parse_id": "p1", "input_text": "test", "user_id": "u1"})}]},
            None,
        )
    assert len(processed) == 1
    assert processed[0]["parse_id"] == "p1"
