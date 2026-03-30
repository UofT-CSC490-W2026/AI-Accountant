"""Tests for services/agent/aws.py — Lambda handler routing."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

import services.agent.aws as agent_aws


def _make_event(message: dict) -> dict:
    return {"Records": [{"body": json.dumps(message)}]}


BASE_MSG = {"parse_id": "p1", "user_id": "u1", "input_text": "Pay rent $2000"}


class TestHandlerRouting:
    def test_posts_when_confident(self, monkeypatch):
        result = {**BASE_MSG, "confidence": {"overall": 0.99}, "post_stages": ["llm"]}
        monkeypatch.setattr(agent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(agent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(agent_aws, "should_post", lambda stage, r: True)

        posted = []
        monkeypatch.setattr(agent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(agent_aws.sqs.enqueue, "posting", lambda r: posted.append(r))

        agent_aws.handler(_make_event(BASE_MSG), None)
        assert len(posted) == 1

    def test_clarification_routes_to_resolution(self, monkeypatch):
        result = {
            **BASE_MSG,
            "clarification": {"required": True},
            "post_stages": [],
        }
        monkeypatch.setattr(agent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(agent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(agent_aws, "should_post", lambda stage, r: False)

        resolution_msgs = []
        clarification_events = []
        monkeypatch.setattr(agent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(agent_aws.pub, "clarification_created", lambda **kw: clarification_events.append(kw))
        monkeypatch.setattr(agent_aws.sqs.enqueue, "resolution", lambda r: resolution_msgs.append(r))

        agent_aws.handler(_make_event(BASE_MSG), None)
        assert len(resolution_msgs) == 1
        assert clarification_events == []

    def test_fallthrough_to_next_stage(self, monkeypatch):
        result = {**BASE_MSG, "post_stages": []}
        monkeypatch.setattr(agent_aws, "execute", lambda msg: result)
        monkeypatch.setattr(agent_aws, "set_status_sync", lambda **kw: None)
        monkeypatch.setattr(agent_aws, "should_post", lambda stage, r: False)
        monkeypatch.setattr(agent_aws, "next_stage", lambda stage, r: None)

        pipeline_results = []
        monkeypatch.setattr(agent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(agent_aws.pub, "pipeline_result", lambda **kw: pipeline_results.append(kw))

        agent_aws.handler(_make_event(BASE_MSG), None)
        assert len(pipeline_results) == 1

    def test_error_sets_failed_status(self, monkeypatch):
        monkeypatch.setattr(agent_aws, "execute", MagicMock(side_effect=ValueError("boom")))

        statuses = []
        monkeypatch.setattr(agent_aws, "set_status_sync", lambda **kw: statuses.append(kw))
        monkeypatch.setattr(agent_aws.pub, "stage_started", lambda **kw: None)
        monkeypatch.setattr(agent_aws.pub, "pipeline_error", lambda **kw: None)

        with pytest.raises(ValueError, match="boom"):
            agent_aws.handler(_make_event(BASE_MSG), None)

        failed = [s for s in statuses if s.get("status") == "failed"]
        assert len(failed) == 1
        assert failed[0]["error"] == "boom"
