from __future__ import annotations

from unittest.mock import patch

from queues.pubsub import pub


def _capture_publish():
    published = []

    def fake_publish_sync(channel, payload):
        published.append((channel, payload))

    return published, fake_publish_sync


def test_entry_posted():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.entry_posted(journal_entry_id="je-1", parse_id="p1", user_id="u1")
    assert published[0][0] == "entry.posted"
    assert published[0][1]["journal_entry_id"] == "je-1"


def test_clarification_created():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.clarification_created(parse_id="p1", user_id="u1")
    assert published[0][0] == "clarification.created"


def test_clarification_resolved():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.clarification_resolved(parse_id="p1", user_id="u1", status="resolved")
    assert published[0][0] == "clarification.resolved"
    assert published[0][1]["status"] == "resolved"


def test_stage_started():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.stage_started(parse_id="p1", user_id="u1", stage="normalizer")
    assert published[0][0] == "pipeline.stage_started"
    assert published[0][1]["stage"] == "normalizer"


def test_stage_skipped():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.stage_skipped(parse_id="p1", user_id="u1", stage="post-ml")
    assert published[0][0] == "pipeline.stage_skipped"


def test_pipeline_result():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.pipeline_result(parse_id="p1", user_id="u1", stage="ml", result={"ok": True})
    assert published[0][0] == "pipeline.result"
    assert published[0][1]["result"] == {"ok": True}


def test_pipeline_error():
    published, fake = _capture_publish()
    with patch.object(pub, "publish_sync", fake):
        pub.pipeline_error(parse_id="p1", user_id="u1", stage="ml", error="boom")
    assert published[0][0] == "pipeline.error"
    assert published[0][1]["error"] == "boom"
