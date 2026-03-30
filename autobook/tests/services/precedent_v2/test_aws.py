"""Tests for services/precedent_v2/aws.py — Lambda handler routing.

Covers:
- Success path: should_post=True routes to posting queue
- Success path: should_post=False, next_stage exists routes to next stage
- Success path: should_post=False, no next stage emits pipeline_result
- Success path: post_stages skipped publishes stage_skipped
- Error path: publishes pipeline_error and sets status to failed
- Error path: re-raises exception after publishing
- Error path: missing parse_id/user_id skips status update
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import services.precedent_v2.aws as precedent_aws


def _make_event(*messages: dict) -> dict:
    return {"Records": [{"body": json.dumps(m)} for m in messages]}


BASE_MSG = {
    "parse_id": "p1",
    "user_id": "u1",
    "input_text": "Paid Apple $2000",
    "description": "Paid Apple $2000",
}


class TestHandlerSuccessPostRouting:
    """When should_post returns True, message goes to posting queue."""

    def test_posts_when_confident(self, monkeypatch):
        result = {
            **BASE_MSG,
            "confidence": {"overall": 0.99},
            "post_stages": ["precedent"],
        }
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: True)

        posted = []
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.sqs.enqueue, "posting", lambda r: posted.append(r))

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(posted) == 1
        assert posted[0]["parse_id"] == "p1"

    def test_post_publishes_post_precedent_stage_started(self, monkeypatch):
        result = {
            **BASE_MSG,
            "confidence": {"overall": 0.99},
            "post_stages": ["precedent"],
        }
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: True)

        stage_events = []
        monkeypatch.setattr(
            precedent_aws.pub, "stage_started", lambda **kw: stage_events.append(kw)
        )
        monkeypatch.setattr(precedent_aws.sqs.enqueue, "posting", lambda r: None)

        precedent_aws.handler(_make_event(BASE_MSG), None)
        # First call is for "precedent" stage start, second is for "post-precedent"
        post_events = [e for e in stage_events if e.get("stage") == "post-precedent"]
        assert len(post_events) == 1


class TestHandlerSuccessNextStageRouting:
    """When should_post is False and next_stage exists, routes to next stage."""

    def test_routes_to_next_stage(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": []}
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: "ml")

        enqueued = []
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(
            precedent_aws.sqs.enqueue, "by_name", lambda name, r: enqueued.append((name, r))
        )

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(enqueued) == 1
        assert enqueued[0][0] == "ml"

    def test_skipped_post_stage_publishes_stage_skipped(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": ["precedent"]}
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: "ml")

        skipped = []
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(
            precedent_aws.pub, "stage_skipped", lambda **kw: skipped.append(kw)
        )
        monkeypatch.setattr(precedent_aws.sqs.enqueue, "by_name", lambda name, r: None)

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(skipped) == 1
        assert skipped[0]["stage"] == "post-precedent"

    def test_no_skipped_event_when_not_in_post_stages(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": []}
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: "ml")

        skipped = []
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(
            precedent_aws.pub, "stage_skipped", lambda **kw: skipped.append(kw)
        )
        monkeypatch.setattr(precedent_aws.sqs.enqueue, "by_name", lambda name, r: None)

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(skipped) == 0


class TestHandlerSuccessTerminal:
    """When should_post=False and no next_stage, publishes pipeline_result."""

    def test_emits_pipeline_result_when_terminal(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": []}
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: None)

        pipeline_results = []
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(
            precedent_aws.pub, "pipeline_result", lambda **kw: pipeline_results.append(kw)
        )

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(pipeline_results) == 1
        assert pipeline_results[0]["parse_id"] == "p1"
        assert pipeline_results[0]["stage"] == "precedent"


class TestHandlerError:
    """Error path: sets status to failed, publishes pipeline_error, re-raises."""

    def test_error_sets_failed_status_and_publishes(self, monkeypatch):
        monkeypatch.setattr(
            precedent_aws, "execute", MagicMock(side_effect=ValueError("boom"))
        )

        statuses = []
        errors = []
        monkeypatch.setattr(
            precedent_aws, "set_status_sync", lambda **kw: statuses.append(kw)
        )
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(
            precedent_aws.pub, "pipeline_error", lambda **kw: errors.append(kw)
        )

        with pytest.raises(ValueError, match="boom"):
            precedent_aws.handler(_make_event(BASE_MSG), None)

        failed = [s for s in statuses if s.get("status") == "failed"]
        assert len(failed) == 1
        assert failed[0]["error"] == "boom"
        assert failed[0]["stage"] == "precedent"

        assert len(errors) == 1
        assert errors[0]["error"] == "boom"
        assert errors[0]["stage"] == "precedent"

    def test_error_reraises(self, monkeypatch):
        monkeypatch.setattr(
            precedent_aws, "execute", MagicMock(side_effect=RuntimeError("kaboom"))
        )
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.pub, "pipeline_error", lambda **kw: None)

        with pytest.raises(RuntimeError, match="kaboom"):
            precedent_aws.handler(_make_event(BASE_MSG), None)

    def test_error_skips_failed_status_when_no_user_id(self, monkeypatch):
        """If user_id is missing, the initial set_status_sync raises KeyError.

        The except block guards with message.get("parse_id") and message.get("user_id"),
        so the failed-status write is skipped. The KeyError is still re-raised.
        """
        statuses = []
        errors = []
        monkeypatch.setattr(
            precedent_aws, "set_status_sync", lambda **kw: statuses.append(kw)
        )
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.pub, "pipeline_error", lambda **kw: errors.append(kw))

        msg_no_user = {"parse_id": "p1"}
        with pytest.raises(KeyError):
            precedent_aws.handler(_make_event(msg_no_user), None)

        # The failed-status update and pipeline_error should NOT be called
        # because the guard checks message.get("user_id") which is falsy.
        failed = [s for s in statuses if s.get("status") == "failed"]
        assert len(failed) == 0
        assert len(errors) == 0


class TestHandlerProcessingStatus:
    """Handler sets status to processing and publishes stage_started at start."""

    def test_sets_processing_status_before_execute(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": []}
        monkeypatch.setattr(precedent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: None)

        statuses = []
        monkeypatch.setattr(
            precedent_aws, "set_status_sync", lambda **kw: statuses.append(kw)
        )
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.pub, "pipeline_result", lambda **kw: None)

        precedent_aws.handler(_make_event(BASE_MSG), None)
        assert len(statuses) == 1
        assert statuses[0]["status"] == "processing"
        assert statuses[0]["stage"] == "precedent"
        assert statuses[0]["parse_id"] == "p1"


class TestHandlerMultipleRecords:
    """Handler processes all records in the SQS batch."""

    def test_processes_all_records(self, monkeypatch):
        executed = []

        def fake_execute(msg):
            executed.append(msg["parse_id"])
            return {**msg, "post_stages": []}

        monkeypatch.setattr(precedent_aws, "execute", fake_execute)
        monkeypatch.setattr(precedent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(precedent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(precedent_aws, "next_stage", lambda stage, r: None)
        monkeypatch.setattr(precedent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(precedent_aws.pub, "pipeline_result", lambda **kw: None)

        msg1 = {**BASE_MSG, "parse_id": "p1"}
        msg2 = {**BASE_MSG, "parse_id": "p2"}
        precedent_aws.handler(_make_event(msg1, msg2), None)
        assert executed == ["p1", "p2"]
