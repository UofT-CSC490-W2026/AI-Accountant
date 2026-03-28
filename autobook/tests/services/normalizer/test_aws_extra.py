from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from services.normalizer.aws import handler


def test_handler_error_path():
    def boom(msg):
        raise RuntimeError("normalizer failed")

    with patch("services.normalizer.aws.execute", side_effect=boom), \
         patch("services.normalizer.aws.set_status_sync") as mock_status, \
         patch("services.normalizer.aws.pub") as mock_pub, \
         patch("services.normalizer.aws.first_stage"), \
         patch("services.normalizer.aws.sqs"):
        with pytest.raises(RuntimeError, match="normalizer failed"):
            handler(
                {"Records": [{"body": json.dumps({"parse_id": "p1", "input_text": "test", "user_id": "u1"})}]},
                None,
            )
    # Should have called set_status_sync with status=failed
    calls = [c for c in mock_status.call_args_list if c.kwargs.get("status") == "failed"]
    assert len(calls) == 1


def test_handler_store_true_publishes_store_stage():
    def fake_execute(msg):
        return {**msg, "parse_id": msg["parse_id"], "user_id": msg["user_id"]}

    stage_calls = []
    with patch("services.normalizer.aws.execute", side_effect=fake_execute), \
         patch("services.normalizer.aws.set_status_sync"), \
         patch("services.normalizer.aws.pub") as mock_pub, \
         patch("services.normalizer.aws.first_stage", return_value=None), \
         patch("services.normalizer.aws.sqs"):
        mock_pub.stage_started = lambda **kw: stage_calls.append(kw)
        mock_pub.pipeline_result = lambda **kw: None
        handler(
            {"Records": [{"body": json.dumps({"parse_id": "p1", "input_text": "test", "user_id": "u1", "store": True})}]},
            None,
        )
    stages = [c["stage"] for c in stage_calls]
    assert "store" in stages
