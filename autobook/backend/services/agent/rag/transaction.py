"""Retriever for transaction_examples collection.

Queries by embed(transaction_text). Used by Agents 0-6 on first run.
Returns full payload — each agent's prompt picks the fields it needs.
"""
from services.agent.graph.state import PipelineState
from vectordb.client import get_qdrant_client
from vectordb.collections import TRANSACTION_EXAMPLES
from vectordb.embeddings import embed_text

_TOP_K = 5


def retrieve_transaction_examples(state: PipelineState, cache_key: str) -> list[dict]:
    """Retrieve similar past transactions from Qdrant.

    Args:
        state: Pipeline state — reads embedding_transaction (cached) or
               transaction_text (embeds and should be cached by caller).
        cache_key: Agent-specific cache key in state (e.g. "rag_cache_debit_classifier").

    Returns:
        List of payload dicts from top-k similar points. Empty list if
        collection has no data.
    """
    cached = state.get(cache_key)
    if cached:
        return cached

    try:
        vector = state.get("embedding_transaction")
        if vector is None:
            text = state["transaction_text"]
            vector = embed_text(text)

        results = get_qdrant_client().query_points(
            collection_name=TRANSACTION_EXAMPLES,
            query=vector,
            limit=_TOP_K,
        )
        return [point.payload for point in results.points]
    except Exception:
        return []
