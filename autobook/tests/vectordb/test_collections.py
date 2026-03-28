"""Tests for vectordb/collections.py — init_collections().

qdrant_client is not in dev deps, so we stub it in sys.modules before import.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub qdrant_client before vectordb.collections is imported
# ---------------------------------------------------------------------------

_mock_qdrant = ModuleType("qdrant_client")
_mock_qdrant.QdrantClient = MagicMock
_mock_qdrant_models = ModuleType("qdrant_client.models")
_mock_qdrant_models.Distance = MagicMock()
_mock_qdrant_models.VectorParams = MagicMock()
_mock_qdrant.models = _mock_qdrant_models

sys.modules.setdefault("qdrant_client", _mock_qdrant)
sys.modules.setdefault("qdrant_client.models", _mock_qdrant_models)

from vectordb.collections import (  # noqa: E402
    COLLECTION_NAMES,
    CORRECTION_EXAMPLES,
    FIX_HISTORY,
    TRANSACTION_EXAMPLES,
    init_collections,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_init_collections_creates_all_three_when_none_exist():
    """All 3 collections are created when none exist."""
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    init_collections(mock_client)

    assert mock_client.collection_exists.call_count == 3
    assert mock_client.create_collection.call_count == 3

    created_names = [c.kwargs["collection_name"] for c in mock_client.create_collection.call_args_list]
    assert created_names == [TRANSACTION_EXAMPLES, CORRECTION_EXAMPLES, FIX_HISTORY]


def test_init_collections_skips_existing():
    """Collections that already exist are not re-created."""
    mock_client = MagicMock()
    # First exists, second doesn't, third exists
    mock_client.collection_exists.side_effect = [True, False, True]

    init_collections(mock_client)

    assert mock_client.create_collection.call_count == 1
    mock_client.create_collection.assert_called_once()
    assert mock_client.create_collection.call_args.kwargs["collection_name"] == CORRECTION_EXAMPLES


def test_init_collections_all_exist_creates_none():
    """When all 3 collections exist, no create calls are made."""
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    init_collections(mock_client)

    assert mock_client.create_collection.call_count == 0


def test_collection_names_has_three_entries():
    """COLLECTION_NAMES constant has exactly 3 entries."""
    assert len(COLLECTION_NAMES) == 3


def test_collection_names_values():
    """COLLECTION_NAMES contains the expected collection name strings."""
    assert TRANSACTION_EXAMPLES == "transaction_examples"
    assert CORRECTION_EXAMPLES == "correction_examples"
    assert FIX_HISTORY == "fix_history"
    assert COLLECTION_NAMES == [
        "transaction_examples",
        "correction_examples",
        "fix_history",
    ]
