from __future__ import annotations

import pytest

from services.shared.routing import first_stage, next_stage, queue_url_for_stage, should_post


def test_first_stage_default():
    assert first_stage({}) == "precedent"


def test_first_stage_custom():
    assert first_stage({"stages": ["ml", "llm"]}) == "ml"


def test_first_stage_none():
    assert first_stage({"stages": []}) is None


def test_next_stage_precedent_to_ml():
    assert next_stage("precedent", {"stages": ["precedent", "ml", "llm"]}) == "ml"


def test_next_stage_ml_to_llm():
    assert next_stage("ml", {"stages": ["ml", "llm"]}) == "llm"


def test_next_stage_last():
    assert next_stage("llm", {"stages": ["llm"]}) is None


def test_next_stage_unknown():
    assert next_stage("unknown", {}) is None


def test_next_stage_skips_missing():
    assert next_stage("precedent", {"stages": ["precedent", "llm"]}) == "llm"


def test_should_post_true():
    msg = {"store": True, "post_stages": ["ml"], "confidence": {"overall": 0.97}}
    assert should_post("ml", msg) is True


def test_should_post_below_threshold():
    msg = {"store": True, "post_stages": ["ml"], "confidence": {"overall": 0.5}}
    assert should_post("ml", msg) is False


def test_should_post_store_false():
    msg = {"store": False, "post_stages": ["ml"], "confidence": {"overall": 0.97}}
    assert should_post("ml", msg) is False


def test_should_post_not_in_post_stages():
    msg = {"store": True, "post_stages": ["precedent"], "confidence": {"overall": 0.97}}
    assert should_post("ml", msg) is False


def test_queue_url_for_stage_known():
    url = queue_url_for_stage("precedent")
    assert url is not None


def test_queue_url_for_stage_unknown():
    with pytest.raises(ValueError, match="Unknown stage"):
        queue_url_for_stage("bogus")
