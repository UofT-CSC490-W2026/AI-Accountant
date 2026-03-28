"""Tests for services/agent/rag/transaction.py — retrieve_transaction_examples().

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

# Stub langchain modules in case agent graph state pulls them transitively
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

# Patch boto3.client before vectordb.embeddings is imported (module-level call)
with patch("boto3.client", return_value=MagicMock()):
    from services.agent.rag.transaction import retrieve_transaction_examples  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    """Build a minimal PipelineState dict for testing."""
    base = {
        "transaction_text": "Paid rent $2000",
        "user_context": {"business_type": "general", "province": "ON", "ownership": "corporation"},
        "ml_enrichment": None,
        "iteration": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch("services.agent.rag.transaction.get_qdrant_client")
@patch("services.agent.rag.transaction.embed_text")
def test_cache_hit_returns_cached(mock_embed, mock_get_client):
    """If cache_key exists in state, return cached value without querying."""
    cached_data = [{"transaction_text": "previous", "debit_tuple": [1, 0, 0, 0, 0, 0]}]
    state = _make_state(rag_cache_debit_classifier=cached_data)

    result = retrieve_transaction_examples(state, "rag_cache_debit_classifier")

    assert result == cached_data
    mock_embed.assert_not_called()
    mock_get_client.assert_not_called()


@patch("services.agent.rag.transaction.get_qdrant_client")
@patch("services.agent.rag.transaction.embed_text")
def test_cache_miss_queries_qdrant(mock_embed, mock_get_client):
    """On cache miss, embeds transaction_text and queries Qdrant."""
    fake_vector = [0.1] * 1536
    mock_embed.return_value = fake_vector

    mock_point = MagicMock()
    mock_point.payload = {"transaction_text": "Similar tx", "debit_tuple": [0, 0, 1, 0, 0, 0]}
    mock_results = MagicMock()
    mock_results.points = [mock_point]
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_results
    mock_get_client.return_value = mock_client

    state = _make_state()

    result = retrieve_transaction_examples(state, "rag_cache_debit_classifier")

    assert len(result) == 1
    assert result[0]["transaction_text"] == "Similar tx"
    mock_embed.assert_called_once_with("Paid rent $2000")
    mock_client.query_points.assert_called_once()


@patch("services.agent.rag.transaction.get_qdrant_client")
@patch("services.agent.rag.transaction.embed_text")
def test_uses_cached_embedding_from_state(mock_embed, mock_get_client):
    """If embedding_transaction is already in state, uses it instead of re-embedding."""
    fake_vector = [0.5] * 1536
    mock_results = MagicMock()
    mock_results.points = []
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_results
    mock_get_client.return_value = mock_client

    state = _make_state(embedding_transaction=fake_vector)

    result = retrieve_transaction_examples(state, "rag_cache_debit_classifier")

    assert result == []
    mock_embed.assert_not_called()
    mock_client.query_points.assert_called_once()
    assert mock_client.query_points.call_args.kwargs["query"] == fake_vector


@patch("services.agent.rag.transaction.get_qdrant_client")
@patch("services.agent.rag.transaction.embed_text")
def test_exception_returns_empty_list(mock_embed, mock_get_client):
    """Any exception during retrieval returns an empty list."""
    mock_embed.side_effect = RuntimeError("Bedrock down")

    state = _make_state()

    result = retrieve_transaction_examples(state, "rag_cache_debit_classifier")

    assert result == []


@patch("services.agent.rag.transaction.get_qdrant_client")
@patch("services.agent.rag.transaction.embed_text")
def test_empty_collection_returns_empty_list(mock_embed, mock_get_client):
    """When Qdrant returns no points, result is an empty list."""
    mock_embed.return_value = [0.1] * 1536
    mock_results = MagicMock()
    mock_results.points = []
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_results
    mock_get_client.return_value = mock_client

    state = _make_state()

    result = retrieve_transaction_examples(state, "rag_cache_debit_classifier")

    assert result == []
