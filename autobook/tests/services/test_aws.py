from __future__ import annotations

import json
from unittest.mock import patch, MagicMock


def test_handler_delegates():
    """Test that agent aws handler parses SQS records and delegates to execute."""
    processed = []

    def fake_execute(msg):
        processed.append(msg)
        return {**msg, "parse_id": msg["parse_id"], "user_id": msg["user_id"], "post_stages": []}

    # Patch the graph module to avoid LangGraph compilation at import time
    with patch.dict("sys.modules", {"services.agent.graph.graph": MagicMock()}):
        with patch("services.agent.aws.execute", side_effect=fake_execute), \
             patch("services.agent.aws.set_status_sync"), \
             patch("services.agent.aws.pub"), \
             patch("services.agent.aws.should_post", return_value=False), \
             patch("services.agent.aws.next_stage", return_value=None), \
             patch("services.agent.aws.sqs"):
            from services.agent.aws import handler
            handler(
                {"Records": [{"body": json.dumps({"parse_id": "p1", "input_text": "test", "user_id": "u1"})}]},
                None,
            )
    assert len(processed) == 1
    assert processed[0]["parse_id"] == "p1"
