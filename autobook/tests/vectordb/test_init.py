"""Tests for vectordb/init.py — Qdrant collection initialization with retry."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call


def test_main_success_first_attempt():
    mock_client = MagicMock()
    mock_client.get_collections.return_value = []

    with patch("vectordb.init.get_qdrant_client", return_value=mock_client) as mock_get, \
         patch("vectordb.init.init_collections") as mock_init:
        from vectordb.init import main
        main()

    mock_get.assert_called_once()
    mock_client.get_collections.assert_called_once()
    mock_init.assert_called_once_with(mock_client)


def test_main_retries_on_failure(monkeypatch):
    mock_client = MagicMock()
    attempt = {"count": 0}

    def flaky_get_collections():
        attempt["count"] += 1
        if attempt["count"] < 3:
            raise ConnectionError("not ready")
        return []

    mock_client.get_collections = flaky_get_collections

    with patch("vectordb.init.get_qdrant_client", return_value=mock_client), \
         patch("vectordb.init.init_collections") as mock_init, \
         patch("vectordb.init.time.sleep"):  # don't actually sleep
        from vectordb.init import main
        main()

    assert attempt["count"] == 3
    mock_init.assert_called_once_with(mock_client)


def test_main_exits_after_10_failures():
    import sys

    mock_client = MagicMock()
    mock_client.get_collections.side_effect = ConnectionError("not ready")

    with patch("vectordb.init.get_qdrant_client", return_value=mock_client), \
         patch("vectordb.init.time.sleep"), \
         patch.object(sys, "exit") as mock_exit:
        from vectordb.init import main
        try:
            main()
        except (SystemExit, TypeError):
            pass

    mock_exit.assert_called_once_with(1)
