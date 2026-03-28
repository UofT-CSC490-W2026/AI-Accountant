"""Retriever for correction_examples collection.

Queries by embed(error_description). Used by Agents 0-5 on rerun
when the diagnostician identifies them as root cause.
Returns full payload — each agent's prompt picks the fields it needs.
"""
from services.agent.graph.state import PipelineState
from vectordb.client import get_qdrant_client
from vectordb.collections import CORRECTION_EXAMPLES
from vectordb.embeddings import embed_text

_TOP_K = 5


def retrieve_correction_examples(state: PipelineState, cache_key: str) -> list[dict]:
    """Retrieve similar past corrections from Qdrant.

    Args:
        state: Pipeline state — reads embedding_error (cached) or
               diagnosis fix_plans[].error (embeds if not cached).
        cache_key: Agent-specific cache key in state.

    Returns:
        List of payload dicts from top-k similar points. Empty list if
        collection has no data or no error embedding available.
    """
    cached = state.get(cache_key)
    if cached:
        return cached

    try:
        vector = state.get("embedding_error")
        if vector is None:
            i = state["iteration"]
            diag_outputs = state.get("output_diagnostician", [])
            if i >= len(diag_outputs) or not diag_outputs[i]:
                return []
            error_text = diag_outputs[i]["fix_plans"][0]["error"]
            vector = embed_text(error_text)

        results = get_qdrant_client().query_points(
            collection_name=CORRECTION_EXAMPLES,
            query=vector,
            limit=_TOP_K,
        )
        return [point.payload for point in results.points]
    except Exception:
        return []
