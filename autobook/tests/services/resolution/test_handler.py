from __future__ import annotations

import json
from unittest.mock import patch

from services.resolution.aws import handler


def test_handler_delegates():
    processed = []

    with patch("services.resolution.aws.execute", side_effect=lambda msg: processed.append(msg)), \
         patch("services.resolution.aws.set_status_sync"):
        handler(
            {"Records": [{"body": json.dumps({"parse_id": "p1", "input_text": "test", "user_id": "u1"})}]},
            None,
        )
    assert len(processed) == 1
    assert processed[0]["parse_id"] == "p1"
