"""Tests for vectordb/client.py — get_qdrant_client().

qdrant_client is not in dev deps, so we stub it in sys.modules before import.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub qdrant_client before vectordb.client is imported
# ---------------------------------------------------------------------------

_mock_qdrant = ModuleType("qdrant_client")
_mock_qdrant.QdrantClient = MagicMock
_mock_qdrant_models = ModuleType("qdrant_client.models")
_mock_qdrant_models.Distance = MagicMock()
_mock_qdrant_models.VectorParams = MagicMock()
_mock_qdrant.models = _mock_qdrant_models

sys.modules.setdefault("qdrant_client", _mock_qdrant)
sys.modules.setdefault("qdrant_client.models", _mock_qdrant_models)

from vectordb.client import get_qdrant_client  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("vectordb.client.QdrantClient")
@patch("vectordb.client.get_settings")
def test_get_qdrant_client_calls_qdrant_with_settings(mock_get_settings, mock_qdrant_cls):
    """QdrantClient is constructed with URL and API key from settings."""
    mock_settings = MagicMock()
    mock_settings.QDRANT_URL = "http://qdrant:6333"
    mock_settings.QDRANT_API_KEY = "test-api-key"
    mock_get_settings.return_value = mock_settings

    result = get_qdrant_client()

    mock_qdrant_cls.assert_called_once_with(
        url="http://qdrant:6333",
        api_key="test-api-key",
    )
    assert result is mock_qdrant_cls.return_value


@patch("vectordb.client.QdrantClient")
@patch("vectordb.client.get_settings")
def test_get_qdrant_client_none_api_key(mock_get_settings, mock_qdrant_cls):
    """QdrantClient works with None API key (local dev)."""
    mock_settings = MagicMock()
    mock_settings.QDRANT_URL = "http://localhost:6333"
    mock_settings.QDRANT_API_KEY = None
    mock_get_settings.return_value = mock_settings

    get_qdrant_client()

    mock_qdrant_cls.assert_called_once_with(
        url="http://localhost:6333",
        api_key=None,
    )
