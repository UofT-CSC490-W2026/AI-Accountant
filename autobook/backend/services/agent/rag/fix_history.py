"""Retriever for fix_history collection.

Queries by embed(rejection_reason). Used by Agent 7 on rejection only.
Returns full payload — diagnostician prompt picks the fields it needs.
"""
from services.agent.graph.state import PipelineState
from vectordb.client import get_qdrant_client
from vectordb.collections import FIX_HISTORY
from vectordb.embeddings import embed_text

_TOP_K = 5


def retrieve_fix_history(state: PipelineState) -> list[dict]:
    """Retrieve similar past fix plans from Qdrant.

    Args:
        state: Pipeline state — reads embedding_rejection (cached) or
               approval.reason (embeds if not cached).

    Returns:
        List of payload dicts from top-k similar points. Empty list if
        collection has no data or no rejection available.
    """
    cached = state.get("rag_cache_diagnostician")
    if cached:
        return cached

    try:
        vector = state.get("embedding_rejection")
        if vector is None:
            i = state["iteration"]
            approver_outputs = state.get("output_approver", [])
            if i >= len(approver_outputs) or not approver_outputs[i]:
                return []
            vector = embed_text(approver_outputs[i]["reason"])

        results = get_qdrant_client().query_points(
            collection_name=FIX_HISTORY,
            query=vector,
            limit=_TOP_K,
        )
        return [point.payload for point in results.points]
    except Exception:
        return []
