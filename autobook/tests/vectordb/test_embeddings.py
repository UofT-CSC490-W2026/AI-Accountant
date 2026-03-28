"""Tests for vectordb/embeddings.py — embed_text() and embed_texts().

The module creates ``_bedrock = boto3.client(...)`` at import time.
boto3 is a real project dependency so import succeeds, but we must
patch the module-level ``_bedrock`` object so tests never hit AWS.
"""
import json
from unittest.mock import MagicMock, patch

import vectordb.embeddings as emb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_bedrock_response(embeddings: list[list[float]]) -> dict:
    """Build a mock Bedrock invoke_model response."""
    body = MagicMock()
    body.read.return_value = json.dumps(
        {"embeddings": {"float": embeddings}}
    ).encode()
    return {"body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_embed_texts_calls_invoke_model():
    """embed_texts sends correct payload to Bedrock and parses response."""
    mock_bedrock = MagicMock()
    fake_embeddings = [[0.1] * 1536, [0.2] * 1536]
    mock_bedrock.invoke_model.return_value = _mock_bedrock_response(fake_embeddings)

    with patch.object(emb, "_bedrock", mock_bedrock):
        result = emb.embed_texts(["hello", "world"], input_type="search_query")

    assert result == fake_embeddings
    mock_bedrock.invoke_model.assert_called_once()

    call_kwargs = mock_bedrock.invoke_model.call_args.kwargs
    assert call_kwargs["modelId"] == "global.cohere.embed-v4:0"
    assert call_kwargs["contentType"] == "application/json"
    assert call_kwargs["accept"] == "*/*"

    body = json.loads(call_kwargs["body"])
    assert body["texts"] == ["hello", "world"]
    assert body["input_type"] == "search_query"
    assert body["embedding_types"] == ["float"]


def test_embed_text_returns_first_vector():
    """embed_text wraps a single string in a list and returns the first result."""
    mock_bedrock = MagicMock()
    fake_embedding = [0.5] * 1536
    mock_bedrock.invoke_model.return_value = _mock_bedrock_response([fake_embedding])

    with patch.object(emb, "_bedrock", mock_bedrock):
        result = emb.embed_text("single text")

    assert result == fake_embedding

    body = json.loads(mock_bedrock.invoke_model.call_args.kwargs["body"])
    assert body["texts"] == ["single text"]


def test_embed_texts_search_document_input_type():
    """embed_texts passes search_document input_type correctly."""
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _mock_bedrock_response([[0.1] * 1536])

    with patch.object(emb, "_bedrock", mock_bedrock):
        emb.embed_texts(["doc text"], input_type="search_document")

    body = json.loads(mock_bedrock.invoke_model.call_args.kwargs["body"])
    assert body["input_type"] == "search_document"


def test_embed_text_default_input_type_is_search_query():
    """embed_text defaults to input_type='search_query'."""
    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = _mock_bedrock_response([[0.2] * 1536])

    with patch.object(emb, "_bedrock", mock_bedrock):
        emb.embed_text("query text")

    body = json.loads(mock_bedrock.invoke_model.call_args.kwargs["body"])
    assert body["input_type"] == "search_query"


def test_embed_texts_batch_preserves_order():
    """embed_texts returns vectors in the same order as input texts."""
    mock_bedrock = MagicMock()
    vecs = [[float(i)] * 10 for i in range(3)]
    mock_bedrock.invoke_model.return_value = _mock_bedrock_response(vecs)

    with patch.object(emb, "_bedrock", mock_bedrock):
        result = emb.embed_texts(["a", "b", "c"])

    assert len(result) == 3
    assert result[0][0] == 0.0
    assert result[1][0] == 1.0
    assert result[2][0] == 2.0
