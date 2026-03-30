from __future__ import annotations

from services.agent.graph.state import AGENT_NAMES, PipelineState, NOT_RUN, COMPLETE, RERUN


def test_agent_names():
    assert len(AGENT_NAMES) == 13
    assert "disambiguator" in AGENT_NAMES
    assert "ambiguity_detector" in AGENT_NAMES


def test_pipeline_state_is_typed_dict():
    assert "transaction_text" in PipelineState.__annotations__
    assert NOT_RUN == 0
    assert COMPLETE == 1
    assert RERUN == 2
