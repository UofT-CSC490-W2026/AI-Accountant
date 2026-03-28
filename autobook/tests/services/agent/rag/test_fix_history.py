"""Tests for services/agent/rag/fix_history.py — retrieve_fix_history().

qdrant_client is not in dev deps, so we stub it in sys.modules.
vectordb.embeddings has module-level boto3 calls, so we stub that too.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub qdrant_client before any vectordb module is imported
# ---------------------------------------------------------------------------

_mock_qdrant = ModuleType("qdrant_client")
_mock_qdrant.QdrantClient = MagicMock
_mock_qdrant_models = ModuleType("qdrant_client.models")
_mock_qdrant_models.Distance = MagicMock()
_mock_qdrant_models.VectorParams = MagicMock()
_mock_qdrant.models = _mock_qdrant_models

sys.modules.setdefault("qdrant_client", _mock_qdrant)
sys.modules.setdefault("qdrant_client.models", _mock_qdrant_models)

_mock_lc_core = ModuleType("langchain_core")
_mock_lc_messages = ModuleType("langchain_core.messages")
_mock_lc_runnables = ModuleType("langchain_core.runnables")
_mock_lc_aws = ModuleType("langchain_aws")
_mock_lc_messages.SystemMessage = MagicMock
_mock_lc_messages.HumanMessage = MagicMock
_mock_lc_runnables.RunnableConfig = dict
_mock_lc_core.messages = _mock_lc_messages
_mock_lc_core.runnables = _mock_lc_runnables
_mock_lc_aws.ChatBedrockConverse = MagicMock

sys.modules.setdefault("langchain_core", _mock_lc_core)
sys.modules.setdefault("langchain_core.messages", _mock_lc_messages)
sys.modules.setdefault("langchain_core.runnables", _mock_lc_runnables)
sys.modules.setdefault("langchain_aws", _mock_lc_aws)

with patch("boto3.client", return_value=MagicMock()):
    from services.agent.rag.fix_history import retrieve_fix_history  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Build a minimal PipelineState dict for testing."""
    base = {
        "transaction_text": "Paid rent $2000",
        "user_context": {},
        "ml_enrichment": None,
        "iteration": 0,
        "output_approver": [
            {"reason": "COGS recorded as asset increase instead of expense"}
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("services.agent.rag.fix_history.get_qdrant_client")
@patch("services.agent.rag.fix_history.embed_text")
def test_cache_hit_returns_cached(mock_embed, mock_get_client):
    """If rag_cache_diagnostician exists in state, return it without querying."""
    cached = [{"rejection_reason": "some reason", "fix_plan": "some plan"}]
    state = _make_state(rag_cache_diagnostician=cached)

    result = retrieve_fix_history(state)

    assert result == cached
    mock_embed.assert_not_called()
    mock_get_client.assert_not_called()


@patch("services.agent.rag.fix_history.get_qdrant_client")
@patch("services.agent.rag.fix_history.embed_text")
def test_cache_miss_embeds_reason_and_queries(mock_embed, mock_get_client):
    """On cache miss, embeds approver's rejection reason and queries Qdrant."""
    fake_vector = [0.1] * 1536
    mock_embed.return_value = fake_vector

    mock_point = MagicMock()
    mock_point.payload = {"rejection_reason": "Similar rejection"}
    mock_results = MagicMock()
    mock_results.points = [mock_point]
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_results
    mock_get_client.return_value = mock_client

    state = _make_state()

    result = retrieve_fix_history(state)

    assert len(result) == 1
    assert result[0]["rejection_reason"] == "Similar rejection"
    mock_embed.assert_called_once_with("COGS recorded as asset increase instead of expense")


@patch("services.agent.rag.fix_history.get_qdrant_client")
@patch("services.agent.rag.fix_history.embed_text")
def test_uses_cached_rejection_embedding(mock_embed, mock_get_client):
    """If embedding_rejection is already in state, uses it instead of re-embedding."""
    fake_vector = [0.5] * 1536
    mock_results = MagicMock()
    mock_results.points = []
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_results
    mock_get_client.return_value = mock_client

    state = _make_state(embedding_rejection=fake_vector)

    result = retrieve_fix_history(state)

    assert result == []
    mock_embed.assert_not_called()


@patch("services.agent.rag.fix_history.get_qdrant_client")
@patch("services.agent.rag.fix_history.embed_text")
def test_no_approver_output_returns_empty(mock_embed, mock_get_client):
    """When approver output is missing for current iteration, returns []."""
    state = _make_state(output_approver=[], iteration=0)

    result = retrieve_fix_history(state)

    assert result == []


@patch("services.agent.rag.fix_history.get_qdrant_client")
@patch("services.agent.rag.fix_history.embed_text")
def test_exception_returns_empty_list(mock_embed, mock_get_client):
    """Any exception during retrieval returns an empty list."""
    mock_embed.side_effect = RuntimeError("Bedrock down")

    state = _make_state()

    result = retrieve_fix_history(state)

    assert result == []
