from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# 3 collections by write event / retrieval intent
TRANSACTION_EXAMPLES = "transaction_examples"
CORRECTION_EXAMPLES = "correction_examples"
FIX_HISTORY = "fix_history"

COLLECTION_NAMES = [
    TRANSACTION_EXAMPLES,
    CORRECTION_EXAMPLES,
    FIX_HISTORY,
]

# Vector params shared by all collections: Cohere Embed v4, cosine similarity
_VECTOR_PARAMS = VectorParams(size=1536, distance=Distance.COSINE)

# Payload schemas (documentation — Qdrant is schema-less, these describe what each stores)
#
# transaction_examples:  transaction_text, enriched_text, debit_tuple, credit_tuple,
#                        journal_entry, user_context
#                        Written by: Flywheel (on successful posting)
#                        Query vector: embed(transaction_text)
#                        Consumers: Agents 0-6 (first run)
#
# correction_examples:   error_description, initial_tuple, corrected_tuple,
#                        wrong_entry, corrected_entry, reasoning
#                        Written by: Flywheel (on human override)
#                        Query vector: embed(error_description)
#                        Consumers: Agents 0-5 (rerun, root cause)
#
# fix_history:           rejection_reason, fix_plan, outcome, agents_involved
#                        Written by: Flywheel (on fix loop completion)
#                        Query vector: embed(rejection_reason)
#                        Consumers: Agent 7 (rejection only)


def init_collections(client: QdrantClient) -> None:
    for name in COLLECTION_NAMES:
        if not client.collection_exists(name):
            client.create_collection(
                collection_name=name,
                vectors_config=_VECTOR_PARAMS,
            )
