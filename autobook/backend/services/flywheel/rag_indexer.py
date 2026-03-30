"""Embed and upsert examples to Qdrant.

Called on T4 (human) resolutions only.
"""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def index_positive_example(message: dict) -> None:
    """Upsert a correct entry as a positive example for Generator RAG."""
    text = message.get("input_text") or message.get("description") or ""
    if not text:
        return

    proposed_entry = message.get("proposed_entry")
    if not proposed_entry:
        return

    try:
        from qdrant_client.models import PointStruct
        from vectordb.client import get_qdrant_client
        from vectordb.collections import TRANSACTION_EXAMPLES
        from vectordb.embeddings import embed_text

        vector = embed_text(text, input_type="search_document")
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "transaction_text": text,
                "journal_entry": proposed_entry,
                "user_context": message.get("user_context"),
                "intent_label": message.get("intent_label"),
                "origin_tier": message.get("origin_tier"),
            },
        )
        get_qdrant_client().upsert(
            collection_name=TRANSACTION_EXAMPLES,
            points=[point],
        )
    except Exception:
        logger.exception("Failed to index positive example for %s", message.get("parse_id"))


def index_correction_example(message: dict) -> None:
    """Upsert a correction example (wrong → right) for Evaluator RAG.

    Only call when the human edited the draft (correction, not just approval).
    """
    error_description = message.get("error_description")
    if not error_description:
        return

    try:
        from qdrant_client.models import PointStruct
        from vectordb.client import get_qdrant_client
        from vectordb.collections import CORRECTION_EXAMPLES
        from vectordb.embeddings import embed_text

        vector = embed_text(error_description, input_type="search_document")
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "original_transaction": message.get("input_text"),
                "original_draft": message.get("original_draft"),
                "error_description": error_description,
                "corrected_entry": message.get("proposed_entry"),
                "correction_source": message.get("correction_source", "user"),
            },
        )
        get_qdrant_client().upsert(
            collection_name=CORRECTION_EXAMPLES,
            points=[point],
        )
    except Exception:
        logger.exception("Failed to index correction example for %s", message.get("parse_id"))
